import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from scipy.signal import resample_poly

SAMPLE_RATE = 16000
# multilingual, not "base.en" -- transcribe() needs to handle both English
# and Italian (see docs/adr/0013-bilingual-en-it-voice-support.md). Slightly
# less sharp on English-only audio than the .en variant, but running two
# loaded models for one process wasn't worth it for that difference.
MODEL_SIZE = "base"

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def _wasapi_input_device() -> int:
    for api in sd.query_hostapis():
        if api["name"] == "Windows WASAPI":
            return api["default_input_device"]
    return sd.default.device[0]


def record(seconds: float = 5.0) -> np.ndarray:
    device = _wasapi_input_device()
    device_rate = int(sd.query_devices(device)["default_samplerate"])
    audio = sd.rec(
        int(seconds * device_rate),
        samplerate=device_rate,
        channels=1,
        dtype="float32",
        device=device,
    )
    sd.wait()
    audio = audio.flatten()
    if device_rate != SAMPLE_RATE:
        audio = resample_poly(audio, SAMPLE_RATE, device_rate).astype(np.float32)
    return audio


# ponytail: rough default for a typical mic at normal input gain -- like the
# wake word THRESHOLD (see wakeword.py), this is a hardware calibration knob,
# not a universal constant. It only decides when record_until_silence()
# stops polling; vad.has_speech()'s silero model (run once, below, on the
# full buffer) is still what actually judges "was there speech at all," so a
# wrong value here costs responsiveness, not correctness. Retune against
# your own mic/room if it cuts off real speech or never detects silence.
SILENCE_RMS_THRESHOLD = 0.01


def _rms(chunk: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(chunk, dtype=np.float64))))


def record_until_silence(
    max_seconds: float = 60.0, silence_seconds: float = 5.0, chunk_seconds: float = 0.5
) -> np.ndarray:
    """Keeps recording until `silence_seconds` of continuous silence follows
    the first detected speech, instead of record()'s fixed window -- a short
    mid-sentence pause no longer eats into a fixed budget and truncates
    whatever comes after it. `max_seconds` is a safety cap so background
    noise that never quiets down can't listen forever.

    Polls short discrete sd.rec() calls rather than one continuous stream --
    the same pattern already proven reliable for wake word detection on this
    hardware (see wakeword.listen_for_wakeword's docstring). Silence between
    chunks is a cheap RMS check, not vad.has_speech() -- an early version
    called that (torch/silero-vad) on every chunk, and a long enough
    utterance (many chunks -> many rapid back-to-back model calls) crashed
    with `mkl_malloc: failed to allocate memory`. vad.has_speech() still
    runs, just once, on the complete buffer -- unchanged from before this
    function existed."""
    device = _wasapi_input_device()
    device_rate = int(sd.query_devices(device)["default_samplerate"])
    chunk_samples = int(chunk_seconds * device_rate)

    chunks: list[np.ndarray] = []
    heard_speech = False
    silence_elapsed = 0.0
    total_elapsed = 0.0

    while total_elapsed < max_seconds:
        raw = sd.rec(
            chunk_samples, samplerate=device_rate, channels=1, dtype="float32", device=device
        )
        sd.wait()
        raw = raw.flatten()
        chunks.append(raw)
        total_elapsed += chunk_seconds

        if _rms(raw) >= SILENCE_RMS_THRESHOLD:
            heard_speech = True
            silence_elapsed = 0.0
        elif heard_speech:
            silence_elapsed += chunk_seconds
            if silence_elapsed >= silence_seconds:
                break

    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    if device_rate != SAMPLE_RATE:
        audio = resample_poly(audio, SAMPLE_RATE, device_rate).astype(np.float32)
    return audio


def transcribe(audio: np.ndarray, language: str = "en") -> str:
    segments, _ = _get_model().transcribe(audio, language=language)
    return " ".join(segment.text.strip() for segment in segments)
