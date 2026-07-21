"""Hands-free mock interview practice with Rostam (the Interviewer), in
English or Italian -- see docs/adr/0013-bilingual-en-it-voice-support.md.

Unlike examples/demo_voice_pipeline.py (one isolated turn), this loops
run_voice_turn() while reusing one ConversationMemory across turns, so
Rostam remembers its own previous question when it scores your answer
instead of starting a blank conversation on every wake-word turn.

Say "hey sorena" before each answer -- every voice turn is wake-word-gated,
same as the rest of the pipeline; this script doesn't change that.
"""

from sorena.agents import interviewer
from sorena.agents.personas import PERSONAS
from sorena.memory import ConversationMemory
from sorena.voice.pipeline import run_voice_turn

LANGUAGES = {"en": "English", "it": "Italian"}

language = ""
while language not in LANGUAGES:
    language = input("Practice in English or Italian? [en/it]: ").strip().lower()

persona = PERSONAS["interviewer"]
face_info = {"name": persona.name, "color": persona.color, "icon": persona.icon}
memory = ConversationMemory()

print(
    f"\nReady -- say 'hey sorena' to start your {LANGUAGES[language]} mock interview with Rostam."
)
print("Repeat the wake word before each answer. Ctrl+C to stop.\n")

while True:
    try:
        result = run_voice_turn(
            system_prompt=interviewer.SYSTEM_PROMPT,
            tool_names=interviewer.TOOL_NAMES,
            persona=face_info,
            language=language,
            memory=memory,
        )
    except KeyboardInterrupt:
        print("\nInterview practice stopped.")
        break

    if result["transcript"]:
        print(f"you: {result['transcript']}")
        print(f"rostam: {result['reply']}\n")
