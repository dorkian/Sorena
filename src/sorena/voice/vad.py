import numpy as np
import torch
from silero_vad import get_speech_timestamps, load_silero_vad

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = load_silero_vad()
    return _model


def has_speech(audio: np.ndarray, sample_rate: int = 16000) -> bool:
    tensor = torch.from_numpy(audio)
    timestamps = get_speech_timestamps(tensor, _get_model(), sampling_rate=sample_rate)
    return len(timestamps) > 0
