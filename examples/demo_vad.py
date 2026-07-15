from sorena.voice.stt import record
from sorena.voice.vad import has_speech

print("Recording 5 seconds -- stay silent...")
silence = record(5.0)
print(f"has_speech (silence): {has_speech(silence)}")

print()
print("Recording 5 seconds -- say something...")
speech = record(5.0)
print(f"has_speech (speech): {has_speech(speech)}")
