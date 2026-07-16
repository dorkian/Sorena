import queue
import re
import threading
import time

from sorena import agent, face
from sorena.voice import stt, tts, vad, wakeword

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    sentences = [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()]
    return sentences or [text]


def speak_streaming(text: str) -> float:
    """Synthesizes and plays sentence by sentence, overlapping synthesis of the
    next sentence with playback of the current one on a background thread.
    Returns time-to-first-audio in seconds."""
    sentences = split_sentences(text)
    audio_queue: queue.Queue = queue.Queue()
    start = time.perf_counter()
    first_audio_at: list[float] = []

    def synthesize_worker() -> None:
        for sentence in sentences:
            audio_queue.put(tts.synthesize(sentence))
        audio_queue.put(None)

    worker = threading.Thread(target=synthesize_worker, daemon=True)
    worker.start()

    while True:
        item = audio_queue.get()
        if item is None:
            break
        if not first_audio_at:
            first_audio_at.append(time.perf_counter())
        audio, sample_rate = item
        tts.play(audio, sample_rate)

    worker.join()
    return first_audio_at[0] - start if first_audio_at else 0.0


def speak_naive(text: str) -> float:
    """Baseline: synthesize the entire response as one clip, then play it.
    Returns time-to-first-audio in seconds, for comparison against
    speak_streaming()."""
    start = time.perf_counter()
    audio, sample_rate = tts.synthesize(text)
    first_audio_at = time.perf_counter()
    tts.play(audio, sample_rate)
    return first_audio_at - start


def run_voice_turn() -> dict:
    """One full hands-free turn: wake word -> VAD-gated listen -> transcribe
    -> agent loop (Phase 2) -> streaming TTS response. Pushes state to the
    orb face (idle/listening/speaking) as the turn progresses -- see
    src/sorena/face.py and ADR 0009."""
    face.start()
    wake_latency = wakeword.listen_for_wakeword()

    face.push_state("listening")
    audio = stt.record(5.0)
    if not vad.has_speech(audio):
        face.push_state("idle")
        tts.speak("I didn't hear anything.")
        return {"wake_latency": wake_latency, "transcript": None, "reply": None}

    face.push_state("idle")  # thinking -- idle's violet->cyan palette covers this
    transcript = stt.transcribe(audio)
    reply = agent.run(transcript)

    face.push_state("speaking")
    time_to_first_audio = speak_streaming(reply)
    face.push_state("idle")

    return {
        "wake_latency": wake_latency,
        "transcript": transcript,
        "reply": reply,
        "time_to_first_audio": time_to_first_audio,
    }
