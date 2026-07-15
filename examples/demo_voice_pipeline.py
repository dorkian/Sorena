from sorena.voice.pipeline import run_voice_turn

result = run_voice_turn()

print()
print("=== turn summary ===")
print(f"wake word latency: {result['wake_latency'] * 1000:.1f} ms")
print(f"you said: {result['transcript']}")
print(f"agent replied: {result['reply']}")
if result.get("time_to_first_audio") is not None:
    print(f"time-to-first-audio: {result['time_to_first_audio'] * 1000:.0f} ms")
