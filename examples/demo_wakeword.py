from sorena.voice.wakeword import WINDOW_SECONDS, listen_for_wakeword

WINDOW_MS = WINDOW_SECONDS * 1000

print("Say 'hey sorena' to trigger wake word detection...")
inference_latency_s = listen_for_wakeword()
bounded_latency_ms = WINDOW_MS + inference_latency_s * 1000

print("Wake word detected!")
print(f"  inference latency: {inference_latency_s * 1000:.1f} ms")
print(f"  recording window: {WINDOW_MS:.0f} ms")
print(f"  bounded wake-to-listening latency: {bounded_latency_ms:.1f} ms")
