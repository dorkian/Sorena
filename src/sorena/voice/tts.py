import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from piper import PiperVoice, SynthesisConfig
from piper.download_voices import download_voice
from scipy.signal import resample_poly

VOICE_NAME = "en_US-danny-low"
VOICE_DIR = Path(__file__).parent.parent.parent.parent / "models" / "piper"

_voice: PiperVoice | None = None

# Set by request_stop() (e.g. a single click/tap on the orb while it's
# speaking, wired through face.py's "stop" WS message) to interrupt
# playback immediately -- checked before each play() call, and sd.stop()
# additionally cuts off audio already playing rather than waiting for it to
# finish first.
_stop_requested = threading.Event()


def request_stop() -> None:
    _stop_requested.set()
    sd.stop()


def clear_stop() -> None:
    _stop_requested.clear()


def stop_requested() -> bool:
    return _stop_requested.is_set()


def _wasapi_output_device() -> int:
    for api in sd.query_hostapis():
        if api["name"] == "Windows WASAPI":
            return api["default_output_device"]
    return sd.default.device[1]


def _get_voice() -> PiperVoice:
    global _voice
    if _voice is None:
        model_path = VOICE_DIR / f"{VOICE_NAME}.onnx"
        if not model_path.exists():
            VOICE_DIR.mkdir(parents=True, exist_ok=True)
            download_voice(VOICE_NAME, VOICE_DIR)
        _voice = PiperVoice.load(model_path)
    return _voice


def synthesize(text: str, config: SynthesisConfig | None = None) -> tuple[np.ndarray, int]:
    voice = _get_voice()
    chunks = list(voice.synthesize(text, syn_config=config))
    audio = np.concatenate([c.audio_float_array for c in chunks])
    voice_rate = chunks[0].sample_rate

    device_rate = int(sd.query_devices(_wasapi_output_device())["default_samplerate"])
    if voice_rate != device_rate:
        audio = resample_poly(audio, device_rate, voice_rate).astype(np.float32)

    return audio, device_rate


def play(audio: np.ndarray, sample_rate: int) -> None:
    if _stop_requested.is_set():
        return  # a stop arrived before this clip started -- don't start it
    sd.play(audio, samplerate=sample_rate, device=_wasapi_output_device())
    sd.wait()


def speak(text: str, config: SynthesisConfig | None = None) -> None:
    clear_stop()
    audio, sample_rate = synthesize(text, config)
    play(audio, sample_rate)
