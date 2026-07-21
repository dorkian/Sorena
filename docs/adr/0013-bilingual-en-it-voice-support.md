# 0013 — Bilingual (EN/IT) voice support: explicit language param, not auto-detect

**Status:** Accepted

## Context
Ash's upcoming technical interview is conducted in Italian, and he wants to
rehearse it hands-free with the Interviewer (Rostam, `interviewer.py`)
end-to-end -- wake word, transcription, and spoken feedback all in Italian,
not just the text-chat path (which already worked in Italian for free, since
the LLM providers in `SORENA_PROVIDER_CHAIN` are already fluent -- no code
change needed there).

Each pipeline stage had a different relationship to language:
- **LLM** (`interviewer.py`'s prompt, `router.chat`): already multilingual,
  needs only an explicit instruction not to drift back to English mid-session
  once Ash opens in Italian.
- **STT** (`stt.py`): hardcoded to `faster-whisper`'s `base.en` (an
  English-only model variant) and `language="en"`. Needed a real change.
- **TTS** (`tts.py`): hardcoded to one Piper voice, `en_US-danny-low`. Needed
  a second, Italian voice.
- **Wake word** (`wakeword.py`) and **VAD** (`vad.py`): unaffected --
  `openWakeWord`'s custom `hey_sorena` model is acoustic pattern-matching
  against its own training samples, not language identification, and
  `silero-vad` only classifies speech-vs-silence. Neither needed a change.

## Decision
- **`language` is an explicit `"en"`/`"it"` parameter, not auto-detected.**
  Threaded through `stt.transcribe()`, `tts.synthesize()`/`speak()`,
  `pipeline.speak_streaming()`/`speak_naive()`, and
  `pipeline.run_voice_turn()`, all defaulting to `"en"` so every existing
  caller (`main.py`'s loop, `examples/demo_voice_pipeline.py`) is unaffected.
  Whisper *can* auto-detect language, but it needs enough audio to do it
  confidently, adding latency and risk on exactly the short, wake-word-gated
  utterances this pipeline captures -- and STT needs to know the language
  *before* transcribing to pick the right model behavior, so there's nothing
  reliable to detect from yet at that point. Matches the rest of this
  codebase's existing preference for explicit, caller-supplied parameters
  over inferred ones (e.g. `model_override`, `system_prompt`/`tool_names`
  scoping).
- **STT**: switched `MODEL_SIZE` from `base.en` to the multilingual `base`
  variant, since one process needs to handle both languages. This is
  slightly less sharp on English-only audio than the `.en` variant would be
  -- running two loaded Whisper models simultaneously for that difference
  wasn't worth the extra memory and load time for a two-language use case.
- **TTS**: added a second Piper voice, `it_IT-riccardo-x_low`, matching
  `en_US-danny-low`'s "fast/low-latency" quality tier rather than a slower,
  higher-quality one -- consistent with the existing voice's own tradeoff.
  `_get_voice()` now caches one `PiperVoice` per language in a dict instead
  of a single module-level instance, downloading each on first use exactly
  like the original single-voice path did.
- **`run_voice_turn()` also gained a `memory: ConversationMemory | None`
  param**, discovered as a blocking gap while wiring this: every voice turn
  is wake-word-gated and independently calls `agent.run()` with no `memory`
  passed, so it silently starts a *fresh* conversation each time. Harmless
  for single-shot Q&A, but it means Rostam would forget its own previous
  question by the time it needs to score the answer -- an interview can't
  function turn-by-turn without continuity. Passing the same
  `ConversationMemory` instance across repeated `run_voice_turn()` calls
  (new example: `examples/interview_practice.py`) fixes this; default
  `None` still creates a fresh one per call, so every other caller keeps its
  current (correct, for their use case) behavior.
- **`interviewer.py`'s `SYSTEM_PROMPT`** gained one explicit instruction: if
  Ash opens in Italian, conduct the whole session -- questions, follow-ups,
  feedback, and the notes passed to `save_interview_score` -- in Italian, and
  stay there rather than code-switching mid-session.

## Consequences
- Practicing hands-free requires knowing the language up front (asked once
  at the start of `examples/interview_practice.py`), not switchable
  mid-session -- if Ash wants to change language, he restarts the practice
  session. This is a deliberate simplification, not a limitation discovered
  after the fact: mid-session switching would need re-detecting language on
  every turn, reintroducing the latency/reliability problem explicit
  parameters were chosen to avoid.
- `it_IT-riccardo-x_low` downloads on first use (a few MB via
  `download_voice`, same mechanism as the original English voice) --
  requires network access the first time Italian TTS runs.
- Text-chat mode (`web/index.html` / `face.py`) needed no changes and
  already supports Italian -- this ADR only concerns the voice pipeline.
- Every voice-mode specialist session that needs multi-turn continuity (not
  just the Interviewer) should now pass its own `ConversationMemory` the same
  way `interview_practice.py` does, rather than relying on
  `run_voice_turn()`'s default fresh-memory-per-call behavior.
