# Phase 4 — Voice Pipeline

**Status:** Complete (v0.4.0)
**Depends on:** Phase 2 (agent loop) — Phase 3 optional but not required
**Target duration:** 1–2 weeks
**Release tag:** v0.4.0

## Goal
Give the agent a voice: local wake-word detection, speech-to-text, and streaming text-to-speech, all running on CPU with no cloud dependency. This phase has the biggest demo factor of the whole project.

## Skill learned
Real-time audio + local inference. A differentiator for edge/embedded AI roles, and genuinely impressive to show live.

## Deliverables
- STT: whisper.cpp or faster-whisper running locally on CPU
- TTS: Piper for local speech synthesis
- Wake word: openWakeWord for hands-free activation
- Streaming response: TTS starts on the first completed sentence instead of waiting for the full LLM response — real latency engineering, not just gluing libraries together
- Voice activity detection (VAD) so the mic doesn't transcribe silence/noise continuously

## Definition of Done
- [x] Saying the wake word triggers listening within a bounded, measured latency (log and report the number)
- [x] A spoken question is transcribed correctly for a benchmark set of ≥10 test utterances (manually verified)
- [x] Time-to-first-audio (wake word → first spoken syllable of the response) is measurably lower with streaming TTS than with a naive "wait for full response" baseline — both numbers reported in README
- [x] VAD correctly ignores silence/background noise in a manual test (mic open, no speech, no false transcription)
- [x] Full loop works end-to-end: wake word → listen → transcribe → agent loop (Phase 2) → stream TTS response, hands-free
- [x] README demo: real captured transcript of the full voice interaction (screen recording swapped for a captured transcript, consistent with Phase 2/3)
- [x] Repo tagged `v0.4.0`

## Efficient Learning Path
- whisper.cpp (or faster-whisper) README — just the quickstart and model-size tradeoff table (tiny/base/small) so you can justify your CPU/latency choice
- Piper's README + voice model list — pick one voice, don't audition all of them
- openWakeWord README quickstart — the pretrained models are enough, don't train a custom wake word for v1
- One short explainer on VAD (webrtcvad or Silero VAD docs) — you need the concept and one library call, not a DSP course
- Skim a single blog post on streaming TTS / sentence-chunked synthesis for the pattern (buffer sentences, synthesize as they complete) — this is the one genuinely non-obvious technique in this phase, worth 20 minutes of focused reading

**Methodology:** get each piece working standalone and manually verified (mic → whisper → text in terminal; text → Piper → audio out) before wiring them together. Debugging a broken pipeline of 4 unfamiliar audio libraries at once is the slow path.

## Concepts to be able to explain in interview
VAD, audio buffering, latency budgets, local vs. cloud inference tradeoffs.
