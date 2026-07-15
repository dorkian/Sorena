import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from scipy.signal import resample_poly

SAMPLE_RATE = 16000
MODEL_SIZE = "base.en"

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


def transcribe(audio: np.ndarray) -> str:
    segments, _ = _get_model().transcribe(audio, language="en")
    return " ".join(segment.text.strip() for segment in segments)
