import pytest

from sorena.voice import wakeword


@pytest.fixture(autouse=True)
def _reset_model_cache(monkeypatch):
    # _get_model() caches into this module-level global -- without resetting
    # it, whichever test runs first would pin the model/name for every test
    # after it, regardless of CUSTOM_MODEL_PATH.
    monkeypatch.setattr(wakeword, "_model", None)


class FakeModel:
    def __init__(self, wakeword_models, inference_framework):
        self.wakeword_models = wakeword_models
        self.inference_framework = inference_framework


def test_get_model_uses_pretrained_hey_jarvis_when_no_custom_model(monkeypatch, tmp_path):
    monkeypatch.setattr(wakeword, "CUSTOM_MODEL_PATH", tmp_path / "does_not_exist.onnx")
    monkeypatch.setattr(wakeword, "download_models", lambda names: None)
    monkeypatch.setattr(wakeword, "Model", FakeModel)

    model = wakeword._get_model()

    assert wakeword.WAKEWORD_NAME == "hey_jarvis"
    assert model.wakeword_models == ["hey_jarvis"]


def test_get_model_uses_custom_hey_sorena_model_when_present(monkeypatch, tmp_path):
    custom_path = tmp_path / "hey_sorena.onnx"
    custom_path.write_bytes(b"not a real onnx file -- Model is mocked, contents unused")
    monkeypatch.setattr(wakeword, "CUSTOM_MODEL_PATH", custom_path)
    monkeypatch.setattr(wakeword, "Model", FakeModel)

    model = wakeword._get_model()

    assert wakeword.WAKEWORD_NAME == "hey_sorena"
    assert model.wakeword_models == [str(custom_path)]


def test_get_model_caches_across_calls(monkeypatch, tmp_path):
    monkeypatch.setattr(wakeword, "CUSTOM_MODEL_PATH", tmp_path / "does_not_exist.onnx")
    monkeypatch.setattr(wakeword, "download_models", lambda names: None)
    calls = []
    monkeypatch.setattr(wakeword, "Model", lambda **kw: calls.append(kw) or FakeModel(**kw))

    first = wakeword._get_model()
    second = wakeword._get_model()

    assert first is second
    assert len(calls) == 1
