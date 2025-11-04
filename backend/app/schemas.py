"""Pydantic schemas for the spoken evaluation service."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Basic health check response."""

    status: str = Field(default="ok", description="Current health status")


class CharacterScore(BaseModel):
    """Character-level evaluation details for单词模式."""

    symbol: str = Field(..., description="评估的字符或音素")
    score: float = Field(..., ge=0.0, le=100.0, description="0-100 分数")
    frame_start: int = Field(..., ge=0, description="参考音频中对应的起始帧")
    frame_end: int = Field(..., ge=0, description="参考音频中对应的结束帧")
    metrics: Dict[str, float] = Field(default_factory=dict, description="辅助诊断指标")


class WordScore(BaseModel):
    """Word-level evaluation details for句子模式."""

    word: str = Field(..., description="评估的单词")
    score: float = Field(..., ge=0.0, le=100.0, description="0-100 分数")
    frame_start: int = Field(..., ge=0, description="参考音频中对应的起始帧")
    frame_end: int = Field(..., ge=0, description="参考音频中对应的结束帧")
    metrics: Dict[str, float] = Field(default_factory=dict, description="辅助诊断指标")


class WordEvaluationResult(BaseModel):
    """Aggregated scoring for单词评测."""

    character_scores: List[CharacterScore] = Field(default_factory=list, description="字符级评分明细")
    mfcc_score: float = Field(..., ge=0.0, le=100.0, description="MFCC 相似度得分")
    energy_score: float = Field(..., ge=0.0, le=100.0, description="能量与重音得分")
    pitch_score: float = Field(..., ge=0.0, le=100.0, description="音高匹配得分")
    composite_score: float = Field(..., ge=0.0, le=100.0, description="综合得分")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="整体单词评分")


class SentenceEvaluationResult(BaseModel):
    """Aggregated scoring for句子评测."""

    word_scores: List[WordScore] = Field(default_factory=list, description="单词级评分明细")
    pronunciation_score: float = Field(..., ge=0.0, le=100.0, description="发音得分")
    fluency_score: float = Field(..., ge=0.0, le=100.0, description="流利度得分")
    word_total_score: float = Field(..., ge=0.0, le=100.0, description="单词总分")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="整体句子评分")


class EvaluationMode(str, Enum):
    """Evaluation modes supported by the服务."""

    WORD = "WORD"
    SENTENCE = "SENTENCE"


class TranscriptResult(BaseModel):
    """Speech recognition outcome, if Whisper inference is available."""

    text: str = Field(..., description="Recognised text")
    language: Optional[str] = Field(None, description="Detected language code")
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Estimated recognition confidence"
    )


class EvaluationResponse(BaseModel):
    """Response payload returned after processing an evaluation request."""

    mode: EvaluationMode = Field(..., description="评测模式")
    word_result: Optional[WordEvaluationResult] = Field(None, description="单词评测结果")
    sentence_result: Optional[SentenceEvaluationResult] = Field(None, description="句子评测结果")
    transcript: Optional[TranscriptResult] = Field(None, description="语音识别结果")


__all__ = [
    "CharacterScore",
    "EvaluationMode",
    "EvaluationResponse",
    "HealthResponse",
    "SentenceEvaluationResult",
    "TranscriptResult",
    "WordEvaluationResult",
    "WordScore",
]
