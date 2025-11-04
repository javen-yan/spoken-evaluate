"""Wrapper around OpenAI Whisper for optional speech recognition."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..schemas import TranscriptResult

try:  # pragma: no cover - optional dependency
    import torch
    import whisper
except Exception:  # pragma: no cover - gracefully degrade when whisper/torch are unavailable
    torch = None
    whisper = None


class WhisperNotAvailable(RuntimeError):
    """Raised when Whisper cannot be used but recognition is requested."""


@dataclass(slots=True)
class WhisperConfig:
    model_size: str = "base"
    device: Optional[str] = None
    language: Optional[str] = None


class SpeechRecognizer:
    """Provides a best-effort transcription for diagnostic purposes."""

    def __init__(self, config: WhisperConfig | None = None) -> None:
        self.config = config or WhisperConfig()
        self._model = None
        self._lock = asyncio.Lock()

    async def _ensure_model(self):
        if whisper is None:
            raise WhisperNotAvailable("Whisper 尚未安装，无法启用语音识别。")

        async with self._lock:
            if self._model is None:
                device = self.config.device
                if device is None:
                    if torch is not None and torch.cuda.is_available():
                        device = "cuda"
                    else:
                        device = "cpu"
                loop = asyncio.get_running_loop()
                self._model = await loop.run_in_executor(
                    None, lambda: whisper.load_model(self.config.model_size, device=device)
                )
        return self._model

    async def transcribe(self, audio: np.ndarray, sample_rate: int) -> Optional[TranscriptResult]:
        if os.environ.get("DISABLE_WHISPER", "").lower() in {"1", "true"}:
            return None

        try:
            model = await self._ensure_model()
        except WhisperNotAvailable:
            return None

        audio = audio.astype(np.float32)
        if sample_rate != 16_000:
            audio = whisper.pad_or_trim(whisper.audio.resample(audio, sample_rate, 16_000))
        else:
            audio = whisper.pad_or_trim(audio)

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: model.transcribe(audio=audio, language=self.config.language, fp16=False),
        )

        confidence = None
        if segments := result.get("segments"):
            # Estimate a simple confidence score based on average probability
            probs = [segment.get("avg_logprob", -9.0) for segment in segments]
            confidence = float(np.clip(np.exp(np.mean(probs)), 0.0, 1.0))

        return TranscriptResult(
            text=result.get("text", "").strip(),
            language=result.get("language"),
            confidence=confidence,
        )


__all__ = [
    "SpeechRecognizer",
    "WhisperConfig",
    "WhisperNotAvailable",
]
