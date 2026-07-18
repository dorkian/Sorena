# 0012 — Custom `hey_sorena` wake word: adopted, threshold re-validated against real voice

**Status:** Accepted

## Context
`training/hey_sorena_training.ipynb` (openWakeWord's automated training
pipeline, `target_phrase = "hey sorena"`, `n_samples = 1000`,
`steps = 10000`) produced `hey_sorena.onnx`. Training's own held-out
validation reported: accuracy 0.7325, **recall 0.468**, false positives/hour
0.0.

Structural checks passed cleanly: valid ONNX, input `[1, 16, 96]` / output
`[1, 1]` (openWakeWord's standard wake-word-classifier shape), loads through
`openwakeword.Model` without error. Synthesized-TTS scoring (Piper) showed
clean separation: two "hey sorena" clips scored 0.65 and 0.89, three
unrelated phrases scored 0.001–0.003 — but ADR 0006 already established that
synthesized scores don't predict real-microphone scores for this hardware,
so this alone wasn't sufficient to adopt the model or pick a threshold.

Real live-voice measurement (via `examples/diagnose_wakeword_recorded.py`, a
one-shot 3s `sd.rec()` capture, the same pattern ADR 0006 established, on the
same Realtek SST WASAPI device) gave:
- "hey sorena": **0.3856**, 0.0014, 0.0011 (three genuine attempts)
- unrelated speech: **0.0490** (one negative control)

`THRESHOLD` was initially left at hey_jarvis's `0.3` on this data. Deployed
in the real pipeline (`start.bat` / `sorena.main`), it then failed to wake on
repeated live attempts. Root-caused with a second diagnostic
(`examples/diagnose_wakeword_short_window.py`) that instead mirrors
`listen_for_wakeword()`'s actual production capture -- a 1.5s
`WINDOW_SECONDS` window, not the 3s diagnostic window -- to check whether the
shorter, non-overlapping polling window was truncating/splitting the phrase.
Five more real "hey sorena" attempts on that exact production window gave
**0.8384**, 0.2687, 0.0378, 0.0064, 0.0009 -- the short window's peak
(0.8384) beat the 3s window's peak (0.3856), ruling out window-truncation as
the cause. Across all nine real "hey sorena" attempts (both window sizes),
only **2 of 9** crossed `0.3`, and a third (0.2687) missed narrowly --
consistent with the model's own reported 0.468 training recall, not an
artifact of window size or capture method. Most misses were near-zero, not
near-miss, meaning weak recall is the dominant failure mode even after
lowering the threshold.

## Decision
- **Adopt `hey_sorena.onnx`** as the default wake word: `_get_model()`
  already preferred `CUSTOM_MODEL_PATH` when present (ADR/step from the
  original multi-agent plan), and the model now ships in the repo
  (`models/wakeword/hey_sorena.onnx`, ~200KB, exempted from `.gitignore`'s
  `models/` rule the same way the previous placeholder path was).
- **Lower `THRESHOLD` to `0.2`**, down from hey_jarvis's `0.3` (ADR 0006).
  This catches the 0.2687 near-miss while staying ~4x above the one measured
  negative sample (0.0490) -- a smaller safety margin than hey_jarvis's ~37x
  (ADR 0006), but the best available given only one real negative
  measurement so far. Window size was ruled out as a contributing cause (see
  Context), so no `WINDOW_SECONDS` change was made -- there's no evidence a
  longer window (with its direct latency cost) would help, and the 1.5s
  window already produced the single best real score observed.
- **Accept the remaining recall gap rather than lowering the threshold
  further.** Most misses (5 of 9) scored near the noise floor (<0.04), far
  below any threshold that would also stay safely above the one negative
  sample -- these are not threshold-tunable. The real fix is a better-trained
  model (more samples and/or more training steps than the notebook's
  `n_samples=1000`/`steps=10000`), not a lower detection bar.

## Consequences
- Users should expect to sometimes repeat "hey sorena" -- roughly 2-3 real
  attempts in 9 crossed even the lowered threshold, a known, measured
  limitation (recall 0.468), not a bug. If it's unacceptable in practice,
  retrain with a larger `n_samples`/`steps` config in
  `training/hey_sorena_training.ipynb` and re-measure with
  `diagnose_wakeword_recorded.py` / `diagnose_wakeword_short_window.py`
  before touching `THRESHOLD` again.
- `examples/diagnose_wakeword_recorded.py` and `examples/diagnose_wakeword.py`
  both imported `WAKEWORD_NAME` by value at module load time, before
  `_get_model()`'s side effect of reassigning it from `"hey_jarvis"` to
  `"hey_sorena"` -- invisible while both branches resolved to the same name,
  it surfaced as a `KeyError` the moment a custom model actually existed.
  Fixed in `diagnose_wakeword_recorded.py` (and its new sibling
  `diagnose_wakeword_short_window.py`) by reading `wakeword.WAKEWORD_NAME`
  live off the module after calling `_get_model()`, instead of importing it
  by value. `diagnose_wakeword.py` had the same latent bug but was already
  broken independently (it predated ADR 0006's polled-capture rewrite and
  imported names — `OVERLAP_SECONDS`, `READ_SECONDS` — that no longer
  existed); deleted rather than fixed, since it was fully superseded by
  `diagnose_wakeword_recorded.py` and `diagnose_wakeword_short_window.py`.
- `sorena.main`'s startup message ("Listening for 'hey Jarvis'.") was stale
  text left over from before the hey_sorena swap -- fixed alongside this to
  say "hey Sorena", and every other user-facing "hey jarvis" reference in the
  repo (demo scripts, README instructions, web UI copy) was swept in the
  same pass.
- This measurement is specific to the voice, mic, and room it was taken in,
  same caveat as ADR 0006 -- a different speaker/setup may need reweighing.
