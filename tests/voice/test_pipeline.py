import threading

import pytest

from sorena.voice import pipeline


@pytest.fixture(autouse=True)
def _no_real_face_server(monkeypatch):
    # face.start() binds a real port; keep pipeline tests offline/fast.
    monkeypatch.setattr(pipeline.face, "start", lambda: None)
    monkeypatch.setattr(pipeline.face, "push_state", lambda *a, **k: None)


def test_split_sentences_splits_on_terminal_punctuation():
    text = "Hello there. How are you? I am fine!"
    assert pipeline.split_sentences(text) == ["Hello there.", "How are you?", "I am fine!"]


def test_split_sentences_returns_whole_text_if_no_terminal_punctuation():
    text = "no punctuation here"
    assert pipeline.split_sentences(text) == ["no punctuation here"]


def test_split_sentences_drops_empty_fragments():
    text = "One.   Two."
    assert pipeline.split_sentences(text) == ["One.", "Two."]


def test_strip_markdown_removes_bold_and_italic():
    assert pipeline.strip_markdown_for_speech("This is **bold** and *italic* text.") == (
        "This is bold and italic text."
    )
    assert (
        pipeline.strip_markdown_for_speech("__bold__ and _italic_ too.") == "bold and italic too."
    )


def test_strip_markdown_removes_headers():
    assert pipeline.strip_markdown_for_speech("## Section\nBody text.") == "Section\nBody text."
    assert pipeline.strip_markdown_for_speech("# Title") == "Title"


def test_strip_markdown_removes_bullets_but_keeps_numbered_list_numbers():
    result = pipeline.strip_markdown_for_speech("- item one\n- item two\n1. First\n2. Second")
    assert result == "item one\nitem two\n1. First\n2. Second"


def test_strip_markdown_unwraps_links_to_their_text():
    result = pipeline.strip_markdown_for_speech("See [the docs](https://example.com/docs) here.")
    assert result == "See the docs here."


def test_strip_markdown_unwraps_inline_code():
    assert (
        pipeline.strip_markdown_for_speech("Run `pytest -q` to test.") == "Run pytest -q to test."
    )


def test_strip_markdown_replaces_fenced_code_blocks_with_placeholder():
    text = "Here:\n```python\nprint('hi')\n```\nDone."
    assert pipeline.strip_markdown_for_speech(text) == "Here:\n(code omitted)\nDone."


def test_strip_markdown_removes_horizontal_rules():
    result = pipeline.strip_markdown_for_speech("Before\n---\nAfter")
    assert "---" not in result
    assert "Before" in result and "After" in result


def test_strip_markdown_removes_blockquote_markers():
    assert pipeline.strip_markdown_for_speech("> quoted wisdom") == "quoted wisdom"


def test_strip_markdown_handles_realistic_mixed_reply():
    reply = (
        "## Match Score\n"
        "**Overall: 86/100**\n"
        "- Strong Python skills\n"
        "- Missing `LangGraph` experience\n"
        "See [the posting](https://example.com/job) for details."
    )
    result = pipeline.strip_markdown_for_speech(reply)
    assert "#" not in result
    assert "*" not in result
    assert "`" not in result
    assert "[" not in result and "](" not in result
    assert "Match Score" in result
    assert "Overall: 86/100" in result
    assert "Strong Python skills" in result
    assert "LangGraph" in result
    assert "the posting" in result


def test_run_voice_turn_strips_markdown_before_speaking_but_not_before_pushing_turn(monkeypatch):
    monkeypatch.setattr(pipeline.wakeword, "listen_for_wakeword", lambda: 0.05)
    monkeypatch.setattr(pipeline.stt, "record_until_silence", lambda: "audio")
    monkeypatch.setattr(pipeline.vad, "has_speech", lambda audio: True)
    monkeypatch.setattr(pipeline.stt, "transcribe", lambda audio, language="en": "how did I do")
    monkeypatch.setattr(
        pipeline.agent,
        "run",
        lambda message, memory=None, system_prompt=None, tool_names=None: "You scored **86/100**.",
    )

    spoken = []
    monkeypatch.setattr(
        pipeline, "speak_streaming", lambda text, language="en": spoken.append(text) or 0.2
    )

    pushed_turns = []
    monkeypatch.setattr(
        pipeline.face,
        "push_turn",
        lambda role, text, agent=None: pushed_turns.append((role, text)),
    )

    pipeline.run_voice_turn()

    assert spoken == ["You scored 86/100."]
    assert ("assistant", "You scored **86/100**.") in pushed_turns


def test_speak_streaming_synthesizes_and_plays_each_sentence(monkeypatch):
    synthesize_calls = []
    play_calls = []

    monkeypatch.setattr(
        pipeline.tts,
        "synthesize",
        lambda text, language="en": synthesize_calls.append(text) or (text, 16000),
    )
    monkeypatch.setattr(pipeline.tts, "play", lambda audio, sr: play_calls.append((audio, sr)))

    pipeline.speak_streaming("One. Two. Three.")

    assert synthesize_calls == ["One.", "Two.", "Three."]
    assert play_calls == [("One.", 16000), ("Two.", 16000), ("Three.", 16000)]


def test_speak_streaming_raises_instead_of_hanging_on_synthesis_failure(monkeypatch):
    # Regression test: synthesize_worker runs on a background thread. Before
    # the fix, an exception there (e.g. a real onnxruntime OOM seen in
    # production) killed the thread without ever queuing the None sentinel,
    # leaving the consumer loop blocked on audio_queue.get() forever -- a
    # permanent hang, not a crash. Run speak_streaming on its own thread with
    # a bounded join so a regression back to that hang fails this test
    # quickly instead of freezing the whole suite.
    def fake_synthesize(text, language="en"):
        if text == "Two.":
            raise RuntimeError("simulated onnxruntime allocation failure")
        return (text, 16000)

    monkeypatch.setattr(pipeline.tts, "synthesize", fake_synthesize)
    monkeypatch.setattr(pipeline.tts, "play", lambda audio, sr: None)

    outcome = {}

    def run():
        try:
            outcome["result"] = pipeline.speak_streaming("One. Two. Three.")
        except Exception as exc:
            outcome["error"] = exc

    caller = threading.Thread(target=run, daemon=True)
    caller.start()
    caller.join(timeout=5)

    assert not caller.is_alive(), "speak_streaming hung instead of raising"
    assert isinstance(outcome.get("error"), RuntimeError)
    assert "simulated onnxruntime allocation failure" in str(outcome["error"])


def test_speak_streaming_stops_early_when_stop_is_requested_mid_turn(monkeypatch):
    # A click/tap on the orb while speaking sends "stop" -> tts.request_stop()
    # (face.py). Regression guard for speak_streaming's two check points: the
    # synth worker must stop producing further sentences, and the consumer
    # must stop playing queued ones, instead of running the rest of the
    # reply to completion.
    synthesize_calls = []
    play_calls = []
    one_played = threading.Event()

    def fake_synthesize(text, language="en"):
        synthesize_calls.append(text)
        if text == "Two.":
            # Real playback blocks (sd.wait()), so "One." is already playing
            # by the time "Two." finishes synthesizing. The fakes here are
            # instant, so without this wait the worker thread could race
            # ahead and set the stop flag before the consumer thread gets
            # scheduled at all -- forcing the same before/after ordering
            # the real blocking playback guarantees.
            assert one_played.wait(timeout=2), "consumer never played 'One.' before 'Two.' synth"
            pipeline.tts.request_stop()
        return (text, 16000)

    def fake_play(audio, sr):
        play_calls.append((audio, sr))
        if audio == "One.":
            one_played.set()

    monkeypatch.setattr(pipeline.tts, "synthesize", fake_synthesize)
    monkeypatch.setattr(pipeline.tts, "play", fake_play)
    monkeypatch.setattr(pipeline.tts.sd, "stop", lambda: None)  # no real audio hardware in a test

    pipeline.speak_streaming("One. Two. Three.")

    assert synthesize_calls == ["One.", "Two."]
    assert play_calls == [("One.", 16000)]


def test_speak_naive_synthesizes_full_text_once(monkeypatch):
    synthesize_calls = []
    play_calls = []

    monkeypatch.setattr(
        pipeline.tts,
        "synthesize",
        lambda text, language="en": synthesize_calls.append(text) or (text, 16000),
    )
    monkeypatch.setattr(pipeline.tts, "play", lambda audio, sr: play_calls.append((audio, sr)))

    pipeline.speak_naive("One. Two. Three.")

    assert synthesize_calls == ["One. Two. Three."]
    assert play_calls == [("One. Two. Three.", 16000)]


def test_run_voice_turn_skips_transcription_when_no_speech(monkeypatch):
    monkeypatch.setattr(pipeline.wakeword, "listen_for_wakeword", lambda: 0.05)
    monkeypatch.setattr(pipeline.stt, "record_until_silence", lambda: "audio")
    monkeypatch.setattr(pipeline.vad, "has_speech", lambda audio: False)

    spoke = []
    monkeypatch.setattr(pipeline.tts, "speak", lambda text, language="en": spoke.append(text))

    def fail_transcribe(audio, language="en"):
        raise AssertionError("should not transcribe when VAD detects no speech")

    monkeypatch.setattr(pipeline.stt, "transcribe", fail_transcribe)

    result = pipeline.run_voice_turn()

    assert result["transcript"] is None
    assert spoke == ["I didn't hear anything."]


def test_run_voice_turn_full_happy_path(monkeypatch):
    monkeypatch.setattr(pipeline.wakeword, "listen_for_wakeword", lambda: 0.05)
    monkeypatch.setattr(pipeline.stt, "record_until_silence", lambda: "audio")
    monkeypatch.setattr(pipeline.vad, "has_speech", lambda audio: True)
    monkeypatch.setattr(pipeline.stt, "transcribe", lambda audio, language="en": "what time is it")
    monkeypatch.setattr(
        pipeline.agent,
        "run",
        lambda message, memory=None, system_prompt=None, tool_names=None: "It is noon.",
    )
    monkeypatch.setattr(pipeline, "speak_streaming", lambda text, language="en": 0.2)

    result = pipeline.run_voice_turn()

    assert result["transcript"] == "what time is it"
    assert result["reply"] == "It is noon."
    assert result["time_to_first_audio"] == 0.2


def test_run_voice_turn_passes_system_prompt_and_tool_names_to_agent(monkeypatch):
    monkeypatch.setattr(pipeline.wakeword, "listen_for_wakeword", lambda: 0.05)
    monkeypatch.setattr(pipeline.stt, "record_until_silence", lambda: "audio")
    monkeypatch.setattr(pipeline.vad, "has_speech", lambda audio: True)
    monkeypatch.setattr(pipeline.stt, "transcribe", lambda audio, language="en": "quiz me")
    monkeypatch.setattr(pipeline, "speak_streaming", lambda text, language="en": 0.2)

    captured = {}

    def fake_agent_run(message, memory=None, system_prompt=None, tool_names=None):
        captured["system_prompt"] = system_prompt
        captured["tool_names"] = tool_names
        return "reply"

    monkeypatch.setattr(pipeline.agent, "run", fake_agent_run)

    pipeline.run_voice_turn(system_prompt="you are Rostam", tool_names=["save_interview_score"])

    assert captured["system_prompt"] == "you are Rostam"
    assert captured["tool_names"] == ["save_interview_score"]


def test_run_voice_turn_pushes_persona_to_the_face_at_every_state(monkeypatch):
    monkeypatch.setattr(pipeline.wakeword, "listen_for_wakeword", lambda: 0.05)
    monkeypatch.setattr(pipeline.stt, "record_until_silence", lambda: "audio")
    monkeypatch.setattr(pipeline.vad, "has_speech", lambda audio: True)
    monkeypatch.setattr(pipeline.stt, "transcribe", lambda audio, language="en": "hi")
    monkeypatch.setattr(
        pipeline.agent,
        "run",
        lambda message, memory=None, system_prompt=None, tool_names=None: "hello",
    )
    monkeypatch.setattr(pipeline, "speak_streaming", lambda text, language="en": 0.2)

    pushed_agents = []
    monkeypatch.setattr(
        pipeline.face,
        "push_state",
        lambda state, agent=None: pushed_agents.append(agent),
    )

    persona = {"name": "Rostam", "color": "#D9534F", "icon": "interviewer.svg"}
    pipeline.run_voice_turn(persona=persona)

    assert pushed_agents == [persona] * 4  # listening, thinking, speaking, idle


def test_run_voice_turn_passes_language_to_stt_and_tts(monkeypatch):
    monkeypatch.setattr(pipeline.wakeword, "listen_for_wakeword", lambda: 0.05)
    monkeypatch.setattr(pipeline.stt, "record_until_silence", lambda: "audio")
    monkeypatch.setattr(pipeline.vad, "has_speech", lambda audio: True)
    monkeypatch.setattr(
        pipeline.agent,
        "run",
        lambda message, memory=None, system_prompt=None, tool_names=None: "risposta",
    )

    captured = {}
    monkeypatch.setattr(
        pipeline.stt,
        "transcribe",
        lambda audio, language="en": captured.setdefault("stt_language", language) or "domanda",
    )
    monkeypatch.setattr(
        pipeline,
        "speak_streaming",
        lambda text, language="en": captured.setdefault("tts_language", language) or 0.2,
    )

    pipeline.run_voice_turn(language="it")

    assert captured["stt_language"] == "it"
    assert captured["tts_language"] == "it"


def test_run_voice_turn_no_speech_message_is_localized(monkeypatch):
    monkeypatch.setattr(pipeline.wakeword, "listen_for_wakeword", lambda: 0.05)
    monkeypatch.setattr(pipeline.stt, "record_until_silence", lambda: "audio")
    monkeypatch.setattr(pipeline.vad, "has_speech", lambda audio: False)

    spoke = []
    monkeypatch.setattr(
        pipeline.tts, "speak", lambda text, language="en": spoke.append((text, language))
    )

    pipeline.run_voice_turn(language="it")

    assert spoke == [("Non ho sentito nulla.", "it")]


def test_run_voice_turn_passes_the_shared_memory_through_to_agent_run(monkeypatch):
    # Every voice turn is wake-word-gated on its own -- without passing the
    # same ConversationMemory across turns, a specialist like the Interviewer
    # would forget its own previous question by the time it needs to score
    # the answer. Regression guard for that continuity (see
    # examples/interview_practice.py).
    monkeypatch.setattr(pipeline.wakeword, "listen_for_wakeword", lambda: 0.05)
    monkeypatch.setattr(pipeline.stt, "record_until_silence", lambda: "audio")
    monkeypatch.setattr(pipeline.vad, "has_speech", lambda audio: True)
    monkeypatch.setattr(pipeline.stt, "transcribe", lambda audio, language="en": "hi")
    monkeypatch.setattr(pipeline, "speak_streaming", lambda text, language="en": 0.2)

    captured = {}

    def fake_agent_run(message, memory=None, system_prompt=None, tool_names=None):
        captured["memory"] = memory
        return "hello"

    monkeypatch.setattr(pipeline.agent, "run", fake_agent_run)

    shared_memory = pipeline.ConversationMemory()
    pipeline.run_voice_turn(memory=shared_memory)

    assert captured["memory"] is shared_memory
