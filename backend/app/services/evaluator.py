"""Core pronunciation evaluation logic built on top of librosa and numpy."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

import librosa
import numpy as np

from ..schemas import EvaluationMetrics, EvaluationResponse, LetterScore
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

    def _compute_letter_segments(self, text: str, frames: int) -> List[range]:
        letters = [char for char in text if not char.isspace()]
        if not letters:
            letters = list(text)
        letters = letters or ["?"]

        boundaries = np.linspace(0, frames, num=len(letters) + 1, endpoint=True, dtype=int)
        segments: List[range] = []
        for start, end in zip(boundaries[:-1], boundaries[1:]):
            end_idx = int(end) if end > start else int(start + 1)
            segments.append(range(int(start), end_idx))
        return segments

    def evaluate(self, text: str, reference: AudioData, user: AudioData) -> EvaluationResponse:
        reference_features = self._extract_features(reference)
        user_features = self._extract_features(user)

        _, path = librosa.sequence.dtw(X=reference_features, Y=user_features, metric="cosine")
        path = np.array(path)[::-1]

        diffs: List[float] = []
        for ref_idx, user_idx in path:
            ref_vec = reference_features[:, ref_idx]
            user_vec = user_features[:, user_idx]
            diffs.append(float(np.linalg.norm(ref_vec - user_vec)))

        avg_diff = float(np.mean(diffs)) if diffs else 0.0
        dtw_distance = float(np.sum(diffs))

        frames = reference_features.shape[1]
        letter_segments = self._compute_letter_segments(text, frames)
        per_letter: List[List[float]] = [[] for _ in letter_segments]

        # Precompute numeric boundaries to accelerate lookup
        boundaries = np.array([segment.start for segment in letter_segments] + [letter_segments[-1].stop])

        for ref_idx, user_idx in path:
            diff = float(np.linalg.norm(reference_features[:, ref_idx] - user_features[:, user_idx]))
            letter_idx = int(np.searchsorted(boundaries[1:], ref_idx, side="right"))
            letter_idx = min(letter_idx, len(per_letter) - 1)
            per_letter[letter_idx].append(diff)

        letter_scores: List[LetterScore] = []
        clean_letters = [char for char in text if not char.isspace()]
        if not clean_letters:
            clean_letters = list(text) or ["?"]

        for idx, (letter, segment, values) in enumerate(zip(clean_letters, letter_segments, per_letter)):
            if not values:
                score = _safe_exponential_decay(avg_diff)
                segment_metric = {
                    "avg_diff": avg_diff,
                    "support": 0,
                }
            else:
                mean_val = float(np.mean(values))
                score = _safe_exponential_decay(mean_val)
                segment_metric = {
                    "avg_diff": mean_val,
                    "support": len(values),
                }

            letter_scores.append(
                LetterScore(
                    symbol=letter,
                    score=score,
                    frame_start=segment.start,
                    frame_end=segment.stop,
                    metrics=segment_metric,
                )
            )

        overall_score = float(np.mean([item.score for item in letter_scores])) if letter_scores else _safe_exponential_decay(avg_diff)
        normalized_score = overall_score / 100.0

        duration_ratio = user.duration / reference.duration if reference.duration else 0.0
        energy_ratio = compute_energy_ratio(reference, user)
        articulation_score = _safe_exponential_decay(avg_diff, scale=2.0)

        response = EvaluationResponse(
            overall_score=overall_score,
            normalized_score=normalized_score,
            letter_scores=letter_scores,
            metrics=EvaluationMetrics(
                dtw_distance=dtw_distance,
                duration_ratio=duration_ratio,
                energy_ratio=energy_ratio,
                articulation_score=articulation_score,
            ),
            transcript=None,
        )

        return response


__all__ = [
    "AudioEvaluator",
    "FeatureExtractionConfig",
]
