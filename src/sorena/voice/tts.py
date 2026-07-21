import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from piper import PiperVoice, SynthesisConfig
from piper.download_voices import download_voice
from scipy.signal import resample_poly

# see docs/adr/0013-bilingual-en-it-voice-support.md
VOICE_NAMES = {
    "en": "en_US-danny-low",
    "it": "it_IT-riccardo-x_low",
}
VOICE_DIR = Path(__file__).parent.parent.parent.parent / "models" / "piper"

_voices: dict[str, PiperVoice] = {}

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


def _get_voice(language: str = "en") -> PiperVoice:
    if language not in _voices:
        voice_name = VOICE_NAMES[language]
        model_path = VOICE_DIR / f"{voice_name}.onnx"
        if not model_path.exists():
            VOICE_DIR.mkdir(parents=True, exist_ok=True)
            download_voice(voice_name, VOICE_DIR)
        _voices[language] = PiperVoice.load(model_path)
    return _voices[language]


def synthesize(
    text: str, language: str = "en", config: SynthesisConfig | None = None
) -> tuple[np.ndarray, int]:
    voice = _get_voice(language)
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


def speak(text: str, language: str = "en", config: SynthesisConfig | None = None) -> None:
    clear_stop()
    audio, sample_rate = synthesize(text, language, config)
    play(audio, sample_rate)
