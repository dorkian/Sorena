from sorena.voice import tts


def test_request_stop_sets_flag_and_calls_sd_stop(monkeypatch):
    tts.clear_stop()
    stop_calls = []
    monkeypatch.setattr(tts.sd, "stop", lambda: stop_calls.append(True))

    tts.request_stop()

    assert tts.stop_requested() is True
    assert stop_calls == [True]


def test_clear_stop_resets_flag():
    tts._stop_requested.set()

    tts.clear_stop()

    assert tts.stop_requested() is False


def test_play_skips_sd_play_when_stop_already_requested(monkeypatch):
    tts._stop_requested.set()
    play_calls = []
    monkeypatch.setattr(tts.sd, "play", lambda *a, **k: play_calls.append(True))
    monkeypatch.setattr(tts.sd, "wait", lambda: None)

    tts.play("fake-audio", 16000)

    assert play_calls == []
    tts.clear_stop()  # don't leak state into other tests


def test_play_plays_normally_when_no_stop_requested(monkeypatch):
    tts.clear_stop()
    play_calls = []
    monkeypatch.setattr(tts.sd, "play", lambda *a, **k: play_calls.append(a))
    monkeypatch.setattr(tts.sd, "wait", lambda: None)
    monkeypatch.setattr(tts, "_wasapi_output_device", lambda: 0)

    tts.play("fake-audio", 16000)

    assert play_calls == [("fake-audio",)]
