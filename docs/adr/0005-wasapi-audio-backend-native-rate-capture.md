# 0005 — Pin audio I/O to WASAPI, capture/play at the device's native rate

**Status:** Accepted

## Context
`sounddevice`'s "default" input/output device on this machine resolves through
the MME host API (an old Windows audio backend), not WASAPI. Recording
through MME produced continuous audible clicking artifacts — a well-known
MME/PortAudio failure mode under any system load, and this machine had heavy
background load throughout Phase 4's development (uv, node, multiple Python
processes). The clicking wasn't cosmetic: Whisper transcribed the corrupted
audio as coherent-sounding but completely wrong sentences (a 10-utterance
benchmark scored ~40% before this fix, ~100% after).

Separately, asking PortAudio to open a stream directly at a non-native rate
(e.g. 16000 Hz on a device whose native rate is 48000 Hz) fails outright on
WASAPI (`PortAudioError: Invalid sample rate [PaErrorCode -9997]`) — WASAPI's
shared-mode internal resampler isn't exposed at this API level the way it is
inside the OS audio engine for other consumers.

## Decision
Every audio I/O module (`stt.py`, `tts.py`, `wakeword.py`) explicitly resolves
the WASAPI host API's default device (`sd.query_hostapis()` →
`"Windows WASAPI"` → `default_input_device`/`default_output_device`) instead
of trusting `sounddevice`'s ambiguous global default. Streams are opened at
the device's own native rate (queried via `sd.query_devices(device)`), and
audio is resampled in software afterward with `scipy.signal.resample_poly`
to match whatever a model/API actually needs (16kHz for Whisper and
openWakeWord, the device's rate for Piper output).

## Consequences
- Fixes real, measured accuracy loss (40% → 100% on the STT benchmark) and a
  wake-word detection failure mode that looked like a completely different
  bug at first (see ADR 0006 for the rest of that story).
- Windows-specific and driver-specific (Realtek SST here) — a different
  machine's audio stack might not need any of this. Acceptable given the
  project's established Windows-only stance (ADR 0002/0003).
- `scipy` became a direct dependency (previously only pulled in transitively
  by `openwakeword`) — declared explicitly in `pyproject.toml` rather than
  relied on implicitly.
