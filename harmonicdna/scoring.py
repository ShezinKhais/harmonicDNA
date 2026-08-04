"""Compute normalised similarity scores from alignment results."""

from __future__ import annotations

from dataclasses import dataclass

from harmonicdna.aligner import AlignmentResult, SAME


@dataclass
class SimilarityScore:
    raw_score: float
    normalised: float   # 0-1, relative to self-alignment of longer sequence
    identity: float     # fraction of aligned positions that match
    verdict: str        # "identical" | "very similar" | "related" | "distant"


def similarity_score(result: AlignmentResult,
                     max_possible: float) -> SimilarityScore:
    """
    Normalise the SW score against the best possible score for these sequences.
    max_possible should be align(seq, seq).score for the longer sequence.
    """
    if max_possible <= 0:
        norm = 0.0
    else:
        norm = min(1.0, result.score / max_possible)

    if norm >= 0.95:
        verdict = "identical"
    elif norm >= 0.75:
        verdict = "very similar"
    elif norm >= 0.5:
        verdict = "related"
    else:
        verdict = "distant"

    return SimilarityScore(
        raw_score  = result.score,
        normalised = round(norm, 3),
        identity   = result.identity,
        verdict    = verdict,
    )


def self_align_score(seq: list[str], match: float = SAME) -> float:
    """Compute the perfect score when aligning a sequence against itself."""
    # best case: every position matches, and SAME is the highest score the
    # substitution table can award, so this really is the ceiling
    return len(seq) * match
