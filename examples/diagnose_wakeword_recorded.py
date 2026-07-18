import wave

import numpy as np

from sorena.voice import wakeword
from sorena.voice.stt import SAMPLE_RATE, record
from sorena.voice.wakeword import CHUNK_SAMPLES, _get_model

# must read wakeword.WAKEWORD_NAME as a live module attribute, not import it
# by value -- _get_model() reassigns it as a side effect (default "hey_jarvis"
# -> "hey_sorena" once a custom model exists), and a `from ... import
# WAKEWORD_NAME` above would have captured the stale pre-call value instead.
model = _get_model()

print("Recording 3 seconds -- say 'hey sorena' clearly...")
audio = record(3.0)

pcm = (audio * 32767).astype(np.int16)
with wave.open("wakeword_test.wav", "wb") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(SAMPLE_RATE)
    f.writeframes(pcm.tobytes())
print("saved wakeword_test.wav -- play it back to confirm it sounds clean")

best = 0.0
for start in range(0, len(pcm) - CHUNK_SAMPLES + 1, CHUNK_SAMPLES):
    frame = pcm[start : start + CHUNK_SAMPLES]
    scores = model.predict(frame)
    best = max(best, scores[wakeword.WAKEWORD_NAME])

print(f"best wake word score on your recorded voice: {best:.4f}")
