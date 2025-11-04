"""Audio pre-processing utilities used by the evaluation pipeline."""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from fastapi import UploadFile
from pydub import AudioSegment


@dataclass(slots=True)
class AudioData:
    """Represents a loaded audio payload."""

    samples: np.ndarray
    sample_rate: int
    duration: float
    rms: float


class AudioProcessingError(RuntimeError):
    """Raised when an audio asset cannot be processed."""


class AudioProcessingService:
    """High-level audio processing helper built on top of pydub and numpy."""

    def __init__(self, target_sample_rate: int = 16_000) -> None:
        self.target_sample_rate = target_sample_rate

    async def load_upload(self, upload: UploadFile) -> AudioData:
        """Load an uploaded audio file, resample and normalise it.

        Parameters
        ----------
        upload:
            The FastAPI ``UploadFile`` instance to be processed.

        Returns
        -------
        AudioData
            Normalised mono audio data sampled at the configured ``target_sample_rate``.
        """

        raw_bytes = await upload.read()
        if not raw_bytes:
            raise AudioProcessingError("上传的音频文件为空，无法进行评估。")

        try:
            segment = AudioSegment.from_file(io.BytesIO(raw_bytes))
        except Exception as exc:  # pragma: no cover - delegated to ffmpeg/backends
            raise AudioProcessingError("无法解析音频文件，请确认格式是否受支持。") from exc

        segment = segment.set_channels(1).set_frame_rate(self.target_sample_rate)
        duration_seconds = len(segment) / 1000.0

        samples = np.array(segment.get_array_of_samples(), dtype=np.float32)

        # Determine the peak value based on the bit depth to normalise between -1 and 1
        sample_width = segment.sample_width * 8
        max_int_value = float(2 ** (sample_width - 1))
        if max_int_value <= 0:
            raise AudioProcessingError("音频采样精度异常，无法计算样本幅度。")

        samples /= max(max_int_value, 1.0)
        rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0

        return AudioData(samples=samples, sample_rate=self.target_sample_rate, duration=duration_seconds, rms=rms)


def compute_energy_ratio(reference: AudioData, user: AudioData) -> float:
    """Return the relative energy ratio between two audio tracks."""

    if reference.rms == 0:
        return 0.0
    ratio = user.rms / reference.rms
    # Keep the ratio within a reasonable range to avoid exploding metrics
    return float(max(0.0, min(ratio, 10.0)))


__all__ = [
    "AudioData",
    "AudioProcessingError",
    "AudioProcessingService",
    "compute_energy_ratio",
]
