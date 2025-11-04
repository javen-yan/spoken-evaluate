"""Pydantic schemas for the spoken evaluation service."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Basic health check response."""

    status: str = Field(default="ok", description="Current health status")


class LetterScore(BaseModel):
    """Represents the evaluation score for a single letter/symbol."""

    symbol: str = Field(..., description="Evaluated character or phoneme")
    score: float = Field(..., ge=0.0, le=100.0, description="Score from 0 to 100")
    frame_start: int = Field(..., ge=0, description="Starting frame index in reference audio")
    frame_end: int = Field(..., ge=0, description="Ending frame index in reference audio")
    metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Additional diagnostic metrics for the segment",
    )


class EvaluationMetrics(BaseModel):
    """Aggregated metrics summarising the evaluation process."""

    dtw_distance: float = Field(..., ge=0.0, description="Raw DTW distance")
    duration_ratio: float = Field(
        ..., ge=0.0, description="Ratio between user and reference durations"
    )
    energy_ratio: float = Field(..., ge=0.0, description="Relative energy difference")
    articulation_score: float = Field(..., ge=0.0, le=100.0, description="Articulation quality")


class TranscriptResult(BaseModel):
    """Speech recognition outcome, if Whisper inference is available."""

    text: str = Field(..., description="Recognised text")
    language: Optional[str] = Field(None, description="Detected language code")
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Estimated recognition confidence"
    )


class EvaluationResponse(BaseModel):
    """Response payload returned after processing an evaluation request."""

    overall_score: float = Field(..., ge=0.0, le=100.0, description="Overall quality score")
    normalized_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall score normalised to 0-1"
    )
    letter_scores: List[LetterScore] = Field(
        default_factory=list,
        description="Per-letter evaluation scores",
    )
    metrics: EvaluationMetrics
    transcript: Optional[TranscriptResult] = Field(
        None, description="Speech recognition result if available"
    )


__all__ = [
    "EvaluationMetrics",
    "EvaluationResponse",
    "HealthResponse",
    "LetterScore",
    "TranscriptResult",
]
