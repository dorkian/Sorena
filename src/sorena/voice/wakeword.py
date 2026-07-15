import numpy as np
import sounddevice as sd
from openwakeword.model import Model
from openwakeword.utils import download_models
from scipy.signal import resample_poly

WAKEWORD_NAME = "hey_jarvis"
SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # openWakeWord's native 80ms frame size at 16kHz
WINDOW_SECONDS = 1.5  # length of each polled recording -- see listen_for_wakeword
THRESHOLD = 0.3  # tuned against real measured live-voice scores -- see listen_for_wakeword

_model: Model | None = None


def _wasapi_input_device() -> int:
    for api in sd.query_hostapis():
        if api["name"] == "Windows WASAPI":
            return api["default_input_device"]
    return sd.default.device[0]


def _get_model() -> Model:
    global _model
    if _model is None:
        download_models([WAKEWORD_NAME])
        _model = Model(wakeword_models=[WAKEWORD_NAME], inference_framework="onnx")
    return _model


def _best_score(chunk_int16: np.ndarray, model: Model) -> tuple[float, float]:
    """Feeds chunk_int16 to predict() in individual 1280-sample (80ms) frames,
    not as one large call -- verified directly: a synthesized "hey jarvis"
    clip fed as a single big array scored 0.0, while the same audio fed as
    sequential 1280-sample frames scored 0.99+. predict()'s internal batching
    for large single calls isn't equivalent to the model's intended per-frame
    streaming use. Returns (best_score, processing_latency_seconds) across
    all frames."""
    best_score = 0.0
    best_latency = 0.0
    for start in range(0, len(chunk_int16) - CHUNK_SAMPLES + 1, CHUNK_SAMPLES):
        frame = chunk_int16[start : start + CHUNK_SAMPLES]
        scores, timing = model.predict(frame, timing=True)
        if scores[WAKEWORD_NAME] > best_score:
            best_score = scores[WAKEWORD_NAME]
            best_latency = timing["models"]["preprocessor"] + timing["models"][WAKEWORD_NAME]
    return best_score, best_latency


def listen_for_wakeword() -> float:
    """Blocks until the wake word is detected. Returns the model's processing
    latency (seconds) for the detecting frame -- combined with WINDOW_SECONDS,
    this bounds the wake-to-listening latency: window length + inference time.

    Polls with short, independent sd.rec() recordings (the same pattern
    already proven reliable for stt.record()), rather than a continuously-
    open InputStream with per-chunk resampling. The continuous-stream
    approach was tried first and worked well on synthesized speech (0.99+
    confidence) but badly underperformed on real live speech (0.008 max,
    vs. 0.38 for the same phrase captured via a single sd.rec() call,
    confirmed by direct comparison). Something about sustained continuous
    capture -- buffer timing, or driver-level behavior on this Realtek SST
    hardware -- degrades real speech in a way a short, clean, one-shot
    recording doesn't. THRESHOLD is set below that measured 0.38 (and well
    above the ~0.008 noise floor), since 0.5 is too optimistic for real
    voices on this hardware/model combination -- pretrained wake-word
    models have real accuracy limits on atypical voices/environments,
    which is exactly why the spec scopes out training a custom one for v1."""
    model = _get_model()
    device = _wasapi_input_device()
    device_rate = int(sd.query_devices(device)["default_samplerate"])
    window_samples = int(WINDOW_SECONDS * device_rate)

    while True:
        audio = sd.rec(
            window_samples, samplerate=device_rate, channels=1, dtype="float32", device=device
        )
        sd.wait()
        audio = audio.flatten()

        resampled = resample_poly(audio, SAMPLE_RATE, device_rate).astype(np.float32)
        chunk_int16 = (resampled * 32767).astype(np.int16)

        score, latency = _best_score(chunk_int16, model)
        if score > THRESHOLD:
            return latency
