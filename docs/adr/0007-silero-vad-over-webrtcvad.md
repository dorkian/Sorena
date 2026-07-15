# 0007 — VAD: silero-vad, not webrtcvad

**Status:** Accepted

## Context
The spec suggested `webrtcvad` or Silero as VAD options. `webrtcvad` ships
source-only on PyPI (no Windows wheel), meaning it needs a C compiler to
build from source on Windows — the same class of problem that dropped Ollama
from the provider chain in ADR 0002. `silero-vad` ships a clean
platform-independent wheel (`py3-none-any`) with no native build step,
confirmed installable before any code was written against it.

## Decision
Use the standalone `silero-vad` PyPI package (`load_silero_vad()` +
`get_speech_timestamps()`) for `src/sorena/voice/vad.py`, not `webrtcvad`.

## Consequences
- No Windows build-toolchain dependency, consistent with every other
  dependency choice in this project (ADR 0002, 0003).
- `openWakeWord` also happens to bundle its own Silero VAD ONNX model
  internally (downloaded alongside its wake-word models, used for its own
  optional `vad_threshold` gating) — this is a separate, internal use and
  was not reused for Sorena's own VAD module; `vad.py` uses the standalone
  `silero-vad` package directly for a simpler, independently testable API.
