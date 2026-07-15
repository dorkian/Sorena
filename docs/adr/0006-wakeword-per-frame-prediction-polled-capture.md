# 0006 — Wake word: per-frame prediction, polled capture over continuous streaming

**Status:** Accepted

## Context
The initial `openWakeWord` integration fed each captured audio window to
`Model.predict()` as one large array per call. This produced a score of
`0.0` on every live attempt, including on a *synthesized* "hey jarvis" clip
generated with Sorena's own Piper TTS — audio with no real-world noise,
mic quality, or resampling concerns at all.

Feeding the exact same synthesized audio to `predict()` as sequential
1280-sample (80ms) frames — the model's native frame size — scored `0.99+`.
`predict()`'s internal batching logic for large single calls (grouping
samples into a `n_prepared_samples // 1280` loop) is not equivalent to the
model's intended per-frame streaming use; only genuinely sequential 80ms
calls produce reliable scores.

With per-frame prediction fixed, a second, separate problem remained: a
continuously-open `sd.InputStream`, read in 500ms windows with overlap-
discard resampling (to avoid `resample_poly`'s lack of filter continuity
across independent calls — see ADR 0005's resampling approach), still
scored real live speech at ~0.008 max — indistinguishable from noise. The
identical windowed/overlap-discard code path scored a synthesized clip at
0.998, so the windowing logic itself was verified correct. Recording the
same phrase with a single short `sd.rec()` call (the same one-shot pattern
already proven reliable for `stt.record()`) instead scored **0.38** for real
live speech — roughly 50x higher than the continuous-stream result for what
should be a comparable utterance.

## Decision
- **Per-frame prediction**: `wakeword._best_score()` always feeds audio to
  `Model.predict()` in individual 1280-sample frames, taking the max score
  across frames, never as one large call.
- **Polled capture, not continuous streaming**: `listen_for_wakeword()` loops
  on short (`WINDOW_SECONDS = 1.5`), independent `sd.rec()` calls — the same
  capture pattern as `stt.record()` — rather than keeping a `sd.InputStream`
  open indefinitely.
- **Threshold tuned to measured reality, not the library default**:
  `THRESHOLD = 0.3`, set below the real measured live-voice score (0.38) and
  well above the measured noise floor (~0.008), rather than the commonly
  cited default of 0.5, which this voice/mic/model combination never
  reliably crosses.

## Consequences
- Wake-to-listening latency is now bounded by `WINDOW_SECONDS` (1.5s) +
  inference time (~5ms), not a small fraction of a second — a real,
  measured, and honestly reported number (see README), but slower than a
  continuously-open stream would ideally be.
- The root cause of the continuous-stream degradation (vs. one-shot capture)
  was not fully isolated — buffer timing and possible driver-level AGC
  behavior on this Realtek SST hardware are suspected but unconfirmed.
  Revisit if a future machine/mic makes continuous streaming worth
  retrying, or if `WINDOW_SECONDS`-driven latency becomes a real problem.
- `THRESHOLD = 0.3` is tuned to *this* voice, mic, and room. A different
  speaker may need a different threshold — this is a known, inherent
  limitation of small pretrained wake-word models on atypical voices, which
  is exactly why the spec explicitly scopes out training a custom wake word
  for v1.
