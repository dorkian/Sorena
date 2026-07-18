from pathlib import Path

import numpy as np
import sounddevice as sd
from openwakeword.model import Model
from openwakeword.utils import download_models
from scipy.signal import resample_poly

# training/hey_sorena_training.ipynb produces a custom model at this path; a
# trained one now ships in the repo (models/wakeword/hey_sorena.onnx, see
# .gitignore's exception for it) so _get_model() picks it over openWakeWord's
# pretrained hey_jarvis model by default -- see ADR 0012.
CUSTOM_MODEL_PATH = (
    Path(__file__).parent.parent.parent.parent / "models" / "wakeword" / "hey_sorena.onnx"
)
PRETRAINED_WAKEWORD_NAME = "hey_jarvis"
WAKEWORD_NAME = (
    PRETRAINED_WAKEWORD_NAME  # resolved for real by _get_model(); read it after calling that
)
SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # openWakeWord's native 80ms frame size at 16kHz
WINDOW_SECONDS = 1.5  # length of each polled recording -- see listen_for_wakeword
# 0.2, lowered from hey_jarvis's original 0.3 (ADR 0006) after hey_sorena's
# real live-voice measurements (ADR 0012) showed only 2 of 9 genuine "hey
# sorena" attempts crossed 0.3, including a near-miss at 0.2687 -- consistent
# with the model's own reported 0.468 training recall, not a threshold-tuning
# problem. 0.2 catches that near-miss while staying ~4x above the one
# measured negative sample (0.0490). Window size (1.5s vs a 3s comparison)
# was ruled out as the cause -- the short window scored the single highest
# real result (0.8384) across all trials. Weak recall is still the dominant
# failure mode even at 0.2 (most low scores were near-zero, not near-miss) --
# see diagnose_wakeword_recorded.py to re-measure, and ADR 0012 for why the
# real fix is retraining with more data/steps, not a lower threshold still.
THRESHOLD = 0.2

_model: Model | None = None


def _wasapi_input_device() -> int:
    for api in sd.query_hostapis():
        if api["name"] == "Windows WASAPI":
            return api["default_input_device"]
    return sd.default.device[0]


def _get_model() -> Model:
    global _model, WAKEWORD_NAME
    if _model is None:
        if CUSTOM_MODEL_PATH.exists():
            WAKEWORD_NAME = "hey_sorena"
            _model = Model(wakeword_models=[str(CUSTOM_MODEL_PATH)], inference_framework="onnx")
        else:
            WAKEWORD_NAME = PRETRAINED_WAKEWORD_NAME
            download_models([PRETRAINED_WAKEWORD_NAME])
            _model = Model(wakeword_models=[PRETRAINED_WAKEWORD_NAME], inference_framework="onnx")
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
    recording doesn't. That 0.38/0.008 pair was measured against the
    pretrained hey_jarvis model (ADR 0006); hey_sorena's own THRESHOLD was
    re-measured the same way once it replaced hey_jarvis as the default (see
    ADR 0012) -- re-measure again with diagnose_wakeword_recorded.py /
    diagnose_wakeword_short_window.py after any future retrain."""
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
