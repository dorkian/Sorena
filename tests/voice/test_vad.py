import numpy as np

from sorena.voice import vad


def test_has_speech_true_when_timestamps_found(monkeypatch):
    monkeypatch.setattr(vad, "_model", "fake-model")
    monkeypatch.setattr(
        vad,
        "get_speech_timestamps",
        lambda tensor, model, sampling_rate: [{"start": 0, "end": 100}],
    )

    assert vad.has_speech(np.zeros(16000, dtype=np.float32)) is True


def test_has_speech_false_when_no_timestamps(monkeypatch):
    monkeypatch.setattr(vad, "_model", "fake-model")
    monkeypatch.setattr(vad, "get_speech_timestamps", lambda tensor, model, sampling_rate: [])

    assert vad.has_speech(np.zeros(16000, dtype=np.float32)) is False
