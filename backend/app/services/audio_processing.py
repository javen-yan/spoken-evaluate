"""Audio pre-processing utilities used by the evaluation pipeline."""

from __future__ import annotations

import io
from dataclasses import dataclass
from urllib.parse import quote_plus

import numpy as np
from fastapi import UploadFile
import httpx
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

    def __init__(self, target_sample_rate: int = 16_000, http_timeout: float = 10.0) -> None:
        self.target_sample_rate = target_sample_rate
        self._http_timeout = http_timeout

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


        return self._from_bytes(raw_bytes)

    async def load_reference_from_youdao(self, text: str, voice_type: int = 2) -> AudioData:
        """Download and normalise reference audio from the Youdao dictionary service."""

        cleaned_text = (text or "").strip()
        if not cleaned_text:
            raise AudioProcessingError("标准文本不能为空，无法获取参考音频。")

        if voice_type not in (1, 2):
            raise ValueError("type must be 1 (UK English) or 2 (US English)")

        encoded_text = quote_plus(cleaned_text)
        url = f"https://dict.youdao.com/dictvoice?audio={encoded_text}&type={voice_type}"

        try:
            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                response = await client.get(url)
        except httpx.RequestError as exc:  # pragma: no cover - network failures
            raise AudioProcessingError("有道标准音频下载失败，请检查网络连接。") from exc

        if response.status_code != 200 or not response.content:
            raise AudioProcessingError("有道返回的标准音频为空或状态码异常，无法进行评估。")

        return self._from_bytes(response.content)

    def _from_bytes(self, raw_bytes: bytes) -> AudioData:
        if not raw_bytes:
            raise AudioProcessingError("提供的音频数据为空，无法进行评估。")

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
