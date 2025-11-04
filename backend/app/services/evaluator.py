"""Core pronunciation evaluation logic built on top of librosa and numpy."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

import librosa
import numpy as np

from ..schemas import (
    CharacterScore,
    EvaluationMode,
    EvaluationResponse,
    SentenceEvaluationResult,
    WordEvaluationResult,
    WordScore,
)
from .audio_processing import AudioData, compute_energy_ratio


def _safe_exponential_decay(value: float, scale: float = 1.0) -> float:
    """Return a bounded exponential decay score within [0, 100]."""

    return float(max(0.0, min(100.0, 100.0 * math.exp(-value / max(scale, 1e-6)))))


@dataclass(slots=True)
class FeatureExtractionConfig:
    """Configuration for spectral feature extraction."""

    n_mfcc: int = 20
    hop_length: int = 512
    n_fft: int = 2048
    fmin: int = 20
    fmax: int = 7_000


class AudioEvaluator:
    """Encapsulates the audio feature extraction and scoring logic."""

    def __init__(self, config: FeatureExtractionConfig | None = None) -> None:
        self.config = config or FeatureExtractionConfig()

    def _extract_features(self, audio: AudioData) -> np.ndarray:
        config = self.config
        mfcc = librosa.feature.mfcc(
            y=audio.samples,
            sr=audio.sample_rate,
            n_mfcc=config.n_mfcc,
            hop_length=config.hop_length,
            n_fft=config.n_fft,
            fmin=config.fmin,
            fmax=config.fmax,
        )
        # Apply mean-variance normalisation to increase robustness across speakers
        return librosa.util.normalize(mfcc)

    def _compute_character_segments(self, text: str, frames: int) -> Tuple[List[str], List[range]]:
        letters = [char for char in text if not char.isspace()]
        if not letters:
            letters = list(text.strip())
        letters = letters or ["?"]
        segments = self._build_segments(len(letters), frames)
        return letters, segments

    def _compute_word_segments(self, text: str, frames: int) -> Tuple[List[str], List[range]]:
        words = [word for word in text.replace("\n", " ").split(" ") if word]
        if not words:
            cleaned = text.strip()
            words = [cleaned] if cleaned else ["?"]
        segments = self._build_segments(len(words), frames)
        return words, segments

    def _build_segments(self, count: int, frames: int) -> List[range]:
        boundaries = np.linspace(0, frames, num=count + 1, endpoint=True, dtype=int)
        segments: List[range] = []
        for start, end in zip(boundaries[:-1], boundaries[1:]):
            end_idx = int(end) if end > start else int(start + 1)
            segments.append(range(int(start), end_idx))
        return segments or [range(0, max(frames, 1))]

    def _aggregate_by_segments(
        self,
        path: np.ndarray,
        reference_features: np.ndarray,
        user_features: np.ndarray,
        segments: Sequence[range],
    ) -> List[List[float]]:
        aggregates: List[List[float]] = [[] for _ in segments]
        boundaries = np.array([segment.start for segment in segments] + [segments[-1].stop])
        for ref_idx, user_idx in path:
            diff = float(np.linalg.norm(reference_features[:, ref_idx] - user_features[:, user_idx]))
            seg_idx = int(np.searchsorted(boundaries[1:], ref_idx, side="right"))
            seg_idx = min(seg_idx, len(aggregates) - 1)
            aggregates[seg_idx].append(diff)
        return aggregates

    def _estimate_pitch(self, audio: AudioData) -> float:
        try:
            pitch = librosa.yin(
                audio.samples,
                fmin=80,
                fmax=450,
                sr=audio.sample_rate,
                frame_length=self.config.n_fft,
                hop_length=self.config.hop_length,
            )
        except Exception:  # pragma: no cover - fallback when pitch extraction fails
            return float("nan")

        if pitch.size == 0:
            return float("nan")

        return float(np.nanmean(pitch))

    def _estimate_pause_ratio(self, audio: AudioData) -> float:
        frame_length = max(1, int(audio.sample_rate * 0.03))
        samples = audio.samples
        total_frames = max(1, len(samples) // frame_length)
        silent_frames = 0
        threshold = 0.015

        for start in range(0, len(samples), frame_length):
            frame = samples[start : start + frame_length]
            if frame.size == 0:
                continue
            if float(np.mean(np.abs(frame))) < threshold:
                silent_frames += 1

        return float(silent_frames / total_frames)

    def _diff_stats(
        self,
        reference_features: np.ndarray,
        user_features: np.ndarray,
    ) -> Tuple[np.ndarray, float]:
        _, path = librosa.sequence.dtw(X=reference_features, Y=user_features, metric="cosine")
        path = np.array(path)[::-1]

        diffs = [
            float(np.linalg.norm(reference_features[:, ref_idx] - user_features[:, user_idx]))
            for ref_idx, user_idx in path
        ]
        avg_diff = float(np.mean(diffs)) if diffs else 0.0
        return path, avg_diff

    def evaluate(
        self,
        text: str,
        reference: AudioData,
        user: AudioData,
        mode: EvaluationMode,
    ) -> EvaluationResponse:
        reference_features = self._extract_features(reference)
        user_features = self._extract_features(user)

        path, avg_diff = self._diff_stats(reference_features, user_features)
        frames = reference_features.shape[1]

        if mode == EvaluationMode.WORD:
            return self._evaluate_word_mode(text, reference, user, reference_features, user_features, path, avg_diff, frames)

        return self._evaluate_sentence_mode(
            text,
            reference,
            user,
            reference_features,
            user_features,
            path,
            avg_diff,
            frames,
        )

    def _evaluate_word_mode(
        self,
        text: str,
        reference: AudioData,
        user: AudioData,
        reference_features: np.ndarray,
        user_features: np.ndarray,
        path: np.ndarray,
        avg_diff: float,
        frames: int,
    ) -> EvaluationResponse:
        letters, segments = self._compute_character_segments(text, frames)
        per_letter = self._aggregate_by_segments(path, reference_features, user_features, segments)

        character_scores: List[CharacterScore] = []
        for letter, segment, values in zip(letters, segments, per_letter):
            if values:
                mean_val = float(np.mean(values))
                score = _safe_exponential_decay(mean_val)
                metrics = {"avg_diff": mean_val, "support": len(values)}
            else:
                score = _safe_exponential_decay(avg_diff)
                metrics = {"avg_diff": avg_diff, "support": 0}

            character_scores.append(
                CharacterScore(
                    symbol=letter,
                    score=score,
                    frame_start=segment.start,
                    frame_end=segment.stop,
                    metrics=metrics,
                )
            )

        mfcc_score = _safe_exponential_decay(avg_diff, scale=2.0)
        energy_ratio = compute_energy_ratio(reference, user)
        energy_penalty = abs(1.0 - min(max(energy_ratio, 0.0), 5.0)) * 5.0
        energy_score = _safe_exponential_decay(energy_penalty, scale=2.0)

        pitch_ref = self._estimate_pitch(reference)
        pitch_user = self._estimate_pitch(user)
        if np.isnan(pitch_ref) or np.isnan(pitch_user) or pitch_ref <= 0.0:
            pitch_score = 50.0
        else:
            pitch_diff_ratio = abs(pitch_ref - pitch_user) / max(pitch_ref, 1e-6)
            pitch_score = _safe_exponential_decay(pitch_diff_ratio * 10.0, scale=2.5)

        composite_score = float(np.clip(0.6 * mfcc_score + 0.2 * energy_score + 0.2 * pitch_score, 0.0, 100.0))
        overall_score = float(np.mean([item.score for item in character_scores])) if character_scores else composite_score

        result = WordEvaluationResult(
            character_scores=character_scores,
            mfcc_score=mfcc_score,
            energy_score=energy_score,
            pitch_score=pitch_score,
            composite_score=composite_score,
            overall_score=overall_score,
        )

        return EvaluationResponse(mode=EvaluationMode.WORD, word_result=result, sentence_result=None, transcript=None)

    def _evaluate_sentence_mode(
        self,
        text: str,
        reference: AudioData,
        user: AudioData,
        reference_features: np.ndarray,
        user_features: np.ndarray,
        path: np.ndarray,
        avg_diff: float,
        frames: int,
    ) -> EvaluationResponse:
        words, segments = self._compute_word_segments(text, frames)
        per_word = self._aggregate_by_segments(path, reference_features, user_features, segments)

        word_scores: List[WordScore] = []
        for word, segment, values in zip(words, segments, per_word):
            if values:
                mean_val = float(np.mean(values))
                score = _safe_exponential_decay(mean_val, scale=2.0)
                metrics = {"avg_diff": mean_val, "support": len(values)}
            else:
                score = _safe_exponential_decay(avg_diff, scale=2.0)
                metrics = {"avg_diff": avg_diff, "support": 0}

            word_scores.append(
                WordScore(
                    word=word,
                    score=score,
                    frame_start=segment.start,
                    frame_end=segment.stop,
                    metrics=metrics,
                )
            )

        pronunciation_score = _safe_exponential_decay(avg_diff, scale=2.5)
        duration_ratio = user.duration / reference.duration if reference.duration else 0.0
        pause_ratio_ref = self._estimate_pause_ratio(reference)
        pause_ratio_user = self._estimate_pause_ratio(user)
        pause_penalty = abs(pause_ratio_ref - pause_ratio_user) * 5.0
        tempo_penalty = abs(1.0 - min(max(duration_ratio, 0.0), 4.0)) * 5.0
        fluency_score = _safe_exponential_decay(pause_penalty + tempo_penalty, scale=2.5)

        word_total_score = float(np.mean([item.score for item in word_scores])) if word_scores else pronunciation_score
        overall_score = float(np.clip(0.7 * pronunciation_score + 0.3 * fluency_score, 0.0, 100.0))

        result = SentenceEvaluationResult(
            word_scores=word_scores,
            pronunciation_score=pronunciation_score,
            fluency_score=fluency_score,
            word_total_score=word_total_score,
            overall_score=overall_score,
        )

        return EvaluationResponse(mode=EvaluationMode.SENTENCE, word_result=None, sentence_result=result, transcript=None)


__all__ = [
    "AudioEvaluator",
    "FeatureExtractionConfig",
]
