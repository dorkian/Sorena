from sorena.voice import tts
from sorena.voice.pipeline import speak_naive, speak_streaming

TEXT = (
    "The current UTC time is two thirty one PM. "
    "The weather today is expected to be partly cloudy with a high near seventy degrees. "
    "There is a low chance of rain in the evening. "
    "Let me know if you would like more details."
)

# warm up the lazily-loaded Piper model first -- otherwise whichever path runs
# first unfairly absorbs the one-time model-load cost in its measurement
tts.synthesize("warming up")

print("=== naive: synthesize whole response, then play ===")
naive_latency = speak_naive(TEXT)
print(f"time-to-first-audio (naive): {naive_latency * 1000:.0f} ms")

print()
print("=== streaming: synthesize + play sentence by sentence ===")
streaming_latency = speak_streaming(TEXT)
print(f"time-to-first-audio (streaming): {streaming_latency * 1000:.0f} ms")

print()
speedup = naive_latency / streaming_latency if streaming_latency else float("inf")
print(f"streaming is {speedup:.1f}x faster to first audio")
