"""FastAPI entrypoint for the spoken evaluation service."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .schemas import EvaluationResponse, HealthResponse
from .services.audio_processing import AudioProcessingError, AudioProcessingService
from .services.evaluator import AudioEvaluator
from .services.speech_recognizer import SpeechRecognizer, WhisperConfig

logger = logging.getLogger(__name__)


def _load_allowed_origins() -> list[str]:
    env_value = os.environ.get("SPOKEN_EVALUATE_CORS", "*")
    if env_value == "*":
        return ["*"]
    return [item.strip() for item in env_value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_audio_processing_service() -> AudioProcessingService:
    target_sr = int(os.environ.get("SPOKEN_EVALUATE_SAMPLE_RATE", "16000"))
    return AudioProcessingService(target_sample_rate=target_sr)


@lru_cache(maxsize=1)
def get_audio_evaluator() -> AudioEvaluator:
    return AudioEvaluator()


@lru_cache(maxsize=1)
def get_speech_recognizer() -> SpeechRecognizer:
    model_size = os.environ.get("SPOKEN_EVALUATE_WHISPER_MODEL", "base")
    language = os.environ.get("SPOKEN_EVALUATE_LANGUAGE")
    device = os.environ.get("SPOKEN_EVALUATE_DEVICE")
    return SpeechRecognizer(WhisperConfig(model_size=model_size, device=device, language=language))


app = FastAPI(title="Spoken Evaluation Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_load_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Liveness probe endpoint."""

    return HealthResponse()


@app.post("/api/evaluate", response_model=EvaluationResponse, tags=["evaluation"])
async def evaluate_pronunciation(
    reference_text: Annotated[str, Form(...)],
    reference_audio: Annotated[UploadFile, File(...)],
    user_audio: Annotated[UploadFile, File(...)],
    audio_service: AudioProcessingService = Depends(get_audio_processing_service),
    evaluator: AudioEvaluator = Depends(get_audio_evaluator),
    recognizer: SpeechRecognizer = Depends(get_speech_recognizer),
) -> EvaluationResponse:
    """Compare user pronunciation against a provided reference sample."""

    try:
        reference = await audio_service.load_upload(reference_audio)
        user = await audio_service.load_upload(user_audio)
    except AudioProcessingError as exc:
        logger.exception("Failed to parse audio input")
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await reference_audio.close()
        await user_audio.close()

    response = evaluator.evaluate(reference_text, reference, user)

    try:
        transcript = await recognizer.transcribe(user.samples, user.sample_rate)
    except Exception as exc:  # pragma: no cover - best effort logging
        logger.warning("Whisper transcription failed: %s", exc)
        transcript = None

    if transcript:
        response.transcript = transcript

    return response


__all__ = ["app"]
