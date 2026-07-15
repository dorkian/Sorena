import time

import numpy as np
import sounddevice as sd
from openwakeword.utils import download_models
from scipy.signal import resample_poly

from sorena.voice.wakeword import (
    CHUNK_SAMPLES,
    OVERLAP_SECONDS,
    READ_SECONDS,
    SAMPLE_RATE,
    WAKEWORD_NAME,
    _get_model,
    _wasapi_input_device,
)

download_models([WAKEWORD_NAME])
model = _get_model()
device = _wasapi_input_device()
device_rate = int(sd.query_devices(device)["default_samplerate"])
read_samples = int(READ_SECONDS * device_rate)
overlap_samples = int(OVERLAP_SECONDS * device_rate)
history = np.zeros(overlap_samples, dtype=np.float32)

print(f"device={sd.query_devices(device)['name']} native_rate={device_rate}")
print("Printing live scores for 15 seconds -- say 'hey jarvis' a few times...")

end_at = time.time() + 15
with sd.InputStream(
    samplerate=device_rate, channels=1, dtype="float32", blocksize=read_samples, device=device
) as stream:
    while time.time() < end_at:
        audio, _ = stream.read(read_samples)
        audio = audio[:, 0]
        peak = np.abs(audio).max()

        windowed = np.concatenate([history, audio])
        history = audio[-overlap_samples:]
        resampled = resample_poly(windowed, SAMPLE_RATE, device_rate).astype(np.float32)
        drop_samples = round(len(resampled) * overlap_samples / len(windowed))
        resampled = resampled[drop_samples:]
        chunk_int16 = (resampled * 32767).astype(np.int16)

        best = 0.0
        for start in range(0, len(chunk_int16) - CHUNK_SAMPLES + 1, CHUNK_SAMPLES):
            frame = chunk_int16[start : start + CHUNK_SAMPLES]
            scores = model.predict(frame)
            best = max(best, scores[WAKEWORD_NAME])
        print(f"score={best:.4f}  peak_amplitude={peak:.4f}")
