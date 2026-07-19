import numpy as np

from sorena.voice import stt


def _mock_device(monkeypatch, sample_rate=16000):
    monkeypatch.setattr(stt, "_wasapi_input_device", lambda: 0)
    monkeypatch.setattr(stt.sd, "query_devices", lambda device: {"default_samplerate": sample_rate})
    monkeypatch.setattr(stt.sd, "wait", lambda: None)


def _loud_chunk(n):
    # well above SILENCE_RMS_THRESHOLD
    return np.full((n, 1), 0.5, dtype=np.float32)


def _quiet_chunk(n):
    return np.zeros((n, 1), dtype=np.float32)


def test_record_until_silence_stops_after_silence_follows_speech(monkeypatch):
    _mock_device(monkeypatch)
    # speech, speech, then silence -- should stop once silence_elapsed
    # reaches silence_seconds (2 chunks at chunk_seconds=0.5 -> 1.0s).
    fakes = iter([_loud_chunk, _loud_chunk, _quiet_chunk, _quiet_chunk, _quiet_chunk, _quiet_chunk])
    rec_calls = []

    def fake_rec(n, **kwargs):
        rec_calls.append(n)
        return next(fakes)(n)

    monkeypatch.setattr(stt.sd, "rec", fake_rec)

    audio = stt.record_until_silence(max_seconds=60.0, silence_seconds=1.0, chunk_seconds=0.5)

    # 2 speech chunks + 2 silence chunks (1.0s / 0.5s) = 4 total, then stop
    assert len(rec_calls) == 4
    assert len(audio) == sum(rec_calls)


def test_record_until_silence_ignores_leading_silence_before_any_speech(monkeypatch):
    _mock_device(monkeypatch)
    # silence, silence, speech, then silence long enough to stop -- the
    # leading silence must not count toward the stop condition.
    fakes = iter([_quiet_chunk, _quiet_chunk, _loud_chunk, _quiet_chunk, _quiet_chunk])
    monkeypatch.setattr(stt.sd, "rec", lambda n, **kwargs: next(fakes)(n))

    audio = stt.record_until_silence(max_seconds=60.0, silence_seconds=1.0, chunk_seconds=0.5)

    assert len(audio) > 0  # ran past the leading silence instead of stopping immediately


def test_record_until_silence_caps_at_max_seconds_if_speech_never_stops(monkeypatch):
    _mock_device(monkeypatch)
    rec_calls = []

    def fake_rec(n, **kwargs):
        rec_calls.append(n)
        return _loud_chunk(n)

    monkeypatch.setattr(stt.sd, "rec", fake_rec)

    stt.record_until_silence(max_seconds=1.0, silence_seconds=5.0, chunk_seconds=0.5)

    # 1.0s / 0.5s chunks = 2 -- must not loop forever even though it's
    # continuously loud.
    assert len(rec_calls) == 2


def test_record_until_silence_never_calls_vad_has_speech(monkeypatch):
    # Regression guard: an earlier version called vad.has_speech() (torch/
    # silero-vad) on every chunk, and enough chunks in a row (a long enough
    # utterance) crashed with "mkl_malloc: failed to allocate memory" from
    # rapid repeated model invocations. The per-chunk check must stay a
    # cheap RMS comparison -- vad.has_speech() belongs only to the single,
    # once-per-turn call in pipeline.run_voice_turn().
    _mock_device(monkeypatch)
    monkeypatch.setattr(stt.sd, "rec", lambda n, **kwargs: _loud_chunk(n))

    def fail_if_called(*a, **k):
        raise AssertionError("record_until_silence must not call vad.has_speech")

    monkeypatch.setattr("sorena.voice.vad.has_speech", fail_if_called)

    stt.record_until_silence(max_seconds=1.0, silence_seconds=5.0, chunk_seconds=0.5)
