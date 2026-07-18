"""Scores ONE real 1.5s recording -- the exact WINDOW_SECONDS/sd.rec() capture
listen_for_wakeword() actually polls with in production, unlike
diagnose_wakeword_recorded.py's more forgiving 3.0s stt.record() window. Run
this a few times saying "hey sorena" to check whether the shorter, non-
overlapping production window is truncating/splitting the phrase in a way
the 3s diagnostic didn't reveal."""

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly

from sorena.voice import wakeword

model = wakeword._get_model()
device = wakeword._wasapi_input_device()
device_rate = int(sd.query_devices(device)["default_samplerate"])
window_samples = int(wakeword.WINDOW_SECONDS * device_rate)

print(f"Recording {wakeword.WINDOW_SECONDS}s (production window size) -- say 'hey sorena' now...")
audio = sd.rec(window_samples, samplerate=device_rate, channels=1, dtype="float32", device=device)
sd.wait()
audio = audio.flatten()

resampled = resample_poly(audio, wakeword.SAMPLE_RATE, device_rate).astype(np.float32)
chunk_int16 = (resampled * 32767).astype(np.int16)

best = 0.0
for start in range(0, len(chunk_int16) - wakeword.CHUNK_SAMPLES + 1, wakeword.CHUNK_SAMPLES):
    frame = chunk_int16[start : start + wakeword.CHUNK_SAMPLES]
    scores = model.predict(frame)
    best = max(best, scores[wakeword.WAKEWORD_NAME])

print(f"score (short window): {best:.4f}")
