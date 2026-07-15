import wave

import numpy as np
import sounddevice as sd

from sorena.voice.stt import SAMPLE_RATE, record

print("default input device:", sd.query_devices(kind="input")["name"])

audio = record(5.0)
print(f"max amplitude: {np.abs(audio).max():.4f}  (should be well above 0.05 while speaking)")
print(f"rms: {np.sqrt(np.mean(audio**2)):.4f}")

pcm = (audio * 32767).astype(np.int16)
with wave.open("mic_test.wav", "wb") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(SAMPLE_RATE)
    f.writeframes(pcm.tobytes())
print("saved mic_test.wav -- play it back and listen to what actually got captured")
