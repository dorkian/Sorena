from piper import SynthesisConfig

from sorena.voice.tts import speak

speak(
    "Hello, I am Sorena, your local voice assistant.",
    SynthesisConfig(length_scale=0.9, volume=1.2),
)
