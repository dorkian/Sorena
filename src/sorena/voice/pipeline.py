import queue
import re
import threading
import time

from sorena import agent, face
from sorena.memory import ConversationMemory
from sorena.voice import stt, tts, vad, wakeword

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

NO_SPEECH_MESSAGE = {"en": "I didn't hear anything.", "it": "Non ho sentito nulla."}

# Markdown an LLM reply routinely contains, stripped before TTS so Piper
# speaks the words, not the literal symbols ("asterisk asterisk bold
# asterisk asterisk"). The chat UI gets the raw reply and renders the
# markdown itself instead -- only the spoken path needs this.
_MD_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_MD_HEADER = re.compile(r"^#{1,6}[ \t]+", re.MULTILINE)
_MD_HR = re.compile(r"^[ \t]*[-*_]{3,}[ \t]*$", re.MULTILINE)
_MD_BLOCKQUOTE = re.compile(r"^[ \t]*>[ \t]?", re.MULTILINE)
_MD_BULLET = re.compile(r"^[ \t]*[*\-+][ \t]+", re.MULTILINE)
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_INLINE_CODE = re.compile(r"`([^`]+)`")
_MD_BOLD = re.compile(r"\*\*([^*]+)\*\*|__([^_]+)__")
_MD_ITALIC = re.compile(r"\*([^*]+)\*|_([^_]+)_")


def strip_markdown_for_speech(text: str) -> str:
    """Best-effort markdown-to-plain-text for TTS input. Not a full parser
    -- just the constructs an LLM reply actually produces (bold/italic,
    headers, bullets, links, inline/fenced code, horizontal rules)."""
    text = _MD_CODE_FENCE.sub("(code omitted)", text)
    text = _MD_HR.sub("", text)
    text = _MD_HEADER.sub("", text)
    text = _MD_BLOCKQUOTE.sub("", text)
    text = _MD_BULLET.sub("", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_INLINE_CODE.sub(r"\1", text)
    text = _MD_BOLD.sub(lambda m: m.group(1) or m.group(2), text)
    text = _MD_ITALIC.sub(lambda m: m.group(1) or m.group(2), text)
    return text


def split_sentences(text: str) -> list[str]:
    sentences = [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()]
    return sentences or [text]


def speak_streaming(text: str, language: str = "en") -> float:
    """Synthesizes and plays sentence by sentence, overlapping synthesis of the
    next sentence with playback of the current one on a background thread.
    Returns time-to-first-audio in seconds.

    Stoppable mid-turn: a single click/tap on the orb while speaking sends
    a "stop" WS message (face.py's _handler) that calls tts.request_stop(),
    which both cuts off whatever's playing right now (sd.stop()) and sets a
    flag this loop checks -- the worker stops synthesizing further sentences
    and the consumer stops playing queued ones instead of running the rest
    of the reply to completion."""
    tts.clear_stop()
    sentences = split_sentences(text)
    audio_queue: queue.Queue = queue.Queue()
    start = time.perf_counter()
    first_audio_at: list[float] = []

    def synthesize_worker() -> None:
        # An unhandled exception here (e.g. onnxruntime OOM on a Conv node --
        # seen in practice) would otherwise kill this thread silently without
        # ever queuing the None sentinel, leaving the consumer loop below
        # blocked on audio_queue.get() forever -- a permanent hang, not a
        # crash, indistinguishable from one to the user. Catch, queue the
        # exception itself so the consumer can raise it in the caller's
        # thread, and always send the sentinel via `finally`.
        try:
            for sentence in sentences:
                if tts.stop_requested():
                    break
                audio_queue.put(tts.synthesize(sentence, language=language))
        except Exception as exc:
            audio_queue.put(exc)
        finally:
            audio_queue.put(None)

    worker = threading.Thread(target=synthesize_worker, daemon=True)
    worker.start()

    while True:
        item = audio_queue.get()
        if item is None:
            break
        if isinstance(item, Exception):
            worker.join()
            raise item
        if tts.stop_requested():
            break
        if not first_audio_at:
            first_audio_at.append(time.perf_counter())
        audio, sample_rate = item
        tts.play(audio, sample_rate)

    worker.join()
    return first_audio_at[0] - start if first_audio_at else 0.0


def speak_naive(text: str, language: str = "en") -> float:
    """Baseline: synthesize the entire response as one clip, then play it.
    Returns time-to-first-audio in seconds, for comparison against
    speak_streaming()."""
    start = time.perf_counter()
    audio, sample_rate = tts.synthesize(text, language=language)
    first_audio_at = time.perf_counter()
    tts.play(audio, sample_rate)
    return first_audio_at - start


def run_voice_turn(
    system_prompt: str | None = None,
    tool_names: list[str] | None = None,
    persona: dict | None = None,
    language: str = "en",
    memory: ConversationMemory | None = None,
) -> dict:
    """One full hands-free turn: wake word -> VAD-gated listen -> transcribe
    -> agent loop (Phase 2) -> streaming TTS response. Pushes state to the
    orb face (idle/listening/speaking) as the turn progresses -- see
    src/sorena/face.py and ADR 0009.

    `system_prompt`/`tool_names` scope this turn to one specialist (e.g. the
    Interviewer) exactly like agent.run() and orchestrator.run() already do
    for text mode -- omit both for the default, unscoped assistant. `persona`
    is that specialist's face info ({"name", "color", "icon"}, see
    sorena.agents.personas) so the orb tints/labels itself accordingly while
    this turn is active. `language` is an explicit "en"/"it" choice (see
    docs/adr/0013-bilingual-en-it-voice-support.md) -- not auto-detected,
    since STT needs to know which language it's listening for before it can
    transcribe accurately, so there's nothing to detect from yet. `memory` is
    optional and unused by the default single-shot callers (main.py's loop,
    examples/demo_voice_pipeline.py) -- pass the same ConversationMemory
    across repeated calls to hold one continuous conversation instead of a
    fresh, context-free one on every wake-word turn (see
    examples/interview_practice.py, which needs that for the interviewer to
    remember its own previous question when scoring the answer)."""
    face.start()
    wake_latency = wakeword.listen_for_wakeword()

    face.push_state("listening", agent=persona)
    audio = stt.record_until_silence()
    if not vad.has_speech(audio):
        face.push_state("idle", agent=persona)
        tts.speak(NO_SPEECH_MESSAGE[language], language=language)
        return {"wake_latency": wake_latency, "transcript": None, "reply": None}

    face.push_state("thinking", agent=persona)
    transcript = stt.transcribe(audio, language=language)
    face.push_turn("user", transcript, agent=persona)
    reply = agent.run(transcript, memory=memory, system_prompt=system_prompt, tool_names=tool_names)
    face.push_turn("assistant", reply, agent=persona)

    face.push_state("speaking", agent=persona)
    time_to_first_audio = speak_streaming(strip_markdown_for_speech(reply), language=language)
    face.push_state("idle", agent=persona)

    return {
        "wake_latency": wake_latency,
        "transcript": transcript,
        "reply": reply,
        "time_to_first_audio": time_to_first_audio,
    }
