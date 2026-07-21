import numpy as np

from sorena.voice import tts


def test_get_voice_loads_the_correct_model_per_language_and_caches(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "VOICE_DIR", tmp_path)
    tts._voices.clear()
    for name in tts.VOICE_NAMES.values():
        (tmp_path / f"{name}.onnx").touch()
    loaded = []
    monkeypatch.setattr(tts.PiperVoice, "load", lambda path: loaded.append(path.name) or path.name)

    en_voice = tts._get_voice("en")
    it_voice = tts._get_voice("it")
    tts._get_voice("en")  # already cached -- must not reload

    assert en_voice == f"{tts.VOICE_NAMES['en']}.onnx"
    assert it_voice == f"{tts.VOICE_NAMES['it']}.onnx"
    assert loaded == [f"{tts.VOICE_NAMES['en']}.onnx", f"{tts.VOICE_NAMES['it']}.onnx"]
    tts._voices.clear()  # don't leak state into other tests


def test_get_voice_downloads_the_missing_model_for_that_language(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "VOICE_DIR", tmp_path)
    tts._voices.clear()
    downloaded = []

    def fake_download(name, directory):
        downloaded.append(name)
        (directory / f"{name}.onnx").touch()

    monkeypatch.setattr(tts, "download_voice", fake_download)
    monkeypatch.setattr(tts.PiperVoice, "load", lambda path: path.name)

    tts._get_voice("it")

    assert downloaded == [tts.VOICE_NAMES["it"]]
    tts._voices.clear()


def test_synthesize_requests_the_voice_for_the_given_language(monkeypatch):
    class FakeChunk:
        audio_float_array = np.zeros(4, dtype=np.float32)
        sample_rate = 16000

    class FakeVoice:
        def synthesize(self, text, syn_config=None):
            return [FakeChunk()]

    requested = []
    monkeypatch.setattr(
        tts, "_get_voice", lambda language="en": requested.append(language) or FakeVoice()
    )
    monkeypatch.setattr(tts, "_wasapi_output_device", lambda: 0)
    monkeypatch.setattr(tts.sd, "query_devices", lambda device: {"default_samplerate": 16000})

    tts.synthesize("ciao", language="it")

    assert requested == ["it"]


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
