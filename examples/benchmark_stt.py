from sorena.voice.stt import record, transcribe

N = 10
results = []

for i in range(1, N + 1):
    input(f"[{i}/{N}] Press Enter, then speak for 5 seconds...")
    audio = record(5.0)
    text = transcribe(audio)
    print(f"  -> {text}\n")
    results.append(text)

print("=== Summary ===")
for i, text in enumerate(results, 1):
    print(f"{i}. {text}")
