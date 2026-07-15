from sorena.voice.stt import record, transcribe

print("Recording 5 seconds... speak now")
audio = record(5.0)
print("Transcribing...")
text = transcribe(audio)
print(f"You said: {text}")
