from sorena.voice import pipeline


def test_split_sentences_splits_on_terminal_punctuation():
    text = "Hello there. How are you? I am fine!"
    assert pipeline.split_sentences(text) == ["Hello there.", "How are you?", "I am fine!"]


def test_split_sentences_returns_whole_text_if_no_terminal_punctuation():
    text = "no punctuation here"
    assert pipeline.split_sentences(text) == ["no punctuation here"]


def test_split_sentences_drops_empty_fragments():
    text = "One.   Two."
    assert pipeline.split_sentences(text) == ["One.", "Two."]


def test_speak_streaming_synthesizes_and_plays_each_sentence(monkeypatch):
    synthesize_calls = []
    play_calls = []

    monkeypatch.setattr(
        pipeline.tts, "synthesize", lambda text: synthesize_calls.append(text) or (text, 16000)
    )
    monkeypatch.setattr(pipeline.tts, "play", lambda audio, sr: play_calls.append((audio, sr)))

    pipeline.speak_streaming("One. Two. Three.")

    assert synthesize_calls == ["One.", "Two.", "Three."]
    assert play_calls == [("One.", 16000), ("Two.", 16000), ("Three.", 16000)]


def test_speak_naive_synthesizes_full_text_once(monkeypatch):
    synthesize_calls = []
    play_calls = []

    monkeypatch.setattr(
        pipeline.tts, "synthesize", lambda text: synthesize_calls.append(text) or (text, 16000)
    )
    monkeypatch.setattr(pipeline.tts, "play", lambda audio, sr: play_calls.append((audio, sr)))

    pipeline.speak_naive("One. Two. Three.")

    assert synthesize_calls == ["One. Two. Three."]
    assert play_calls == [("One. Two. Three.", 16000)]


def test_run_voice_turn_skips_transcription_when_no_speech(monkeypatch):
    monkeypatch.setattr(pipeline.wakeword, "listen_for_wakeword", lambda: 0.05)
    monkeypatch.setattr(pipeline.stt, "record", lambda seconds: "audio")
    monkeypatch.setattr(pipeline.vad, "has_speech", lambda audio: False)

    spoke = []
    monkeypatch.setattr(pipeline.tts, "speak", lambda text: spoke.append(text))

    def fail_transcribe(audio):
        raise AssertionError("should not transcribe when VAD detects no speech")

    monkeypatch.setattr(pipeline.stt, "transcribe", fail_transcribe)

    result = pipeline.run_voice_turn()

    assert result["transcript"] is None
    assert spoke == ["I didn't hear anything."]


def test_run_voice_turn_full_happy_path(monkeypatch):
    monkeypatch.setattr(pipeline.wakeword, "listen_for_wakeword", lambda: 0.05)
    monkeypatch.setattr(pipeline.stt, "record", lambda seconds: "audio")
    monkeypatch.setattr(pipeline.vad, "has_speech", lambda audio: True)
    monkeypatch.setattr(pipeline.stt, "transcribe", lambda audio: "what time is it")
    monkeypatch.setattr(pipeline.agent, "run", lambda message: "It is noon.")
    monkeypatch.setattr(pipeline, "speak_streaming", lambda text: 0.2)

    result = pipeline.run_voice_turn()

    assert result["transcript"] == "what time is it"
    assert result["reply"] == "It is noon."
    assert result["time_to_first_audio"] == 0.2
