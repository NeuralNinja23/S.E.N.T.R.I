"""
Interaction Evaluator — Turn quality assessment.

Evaluation is separated from Reflection by design:
  - Reflection observes (extracts knowledge and behavior signals).
  - Evaluation judges (scores quality and identifies performance issues).

This separation allows success metrics, conversation scoring,
and regression benchmarks without polluting the reflection pipeline.
"""

import logging

from app.capability_2.learning.contracts import EvaluationResult, LatencyProfile

from app.services.logger import get_logger
logger = get_logger("interaction_evaluator")

# Latency thresholds (milliseconds from user speech end to first audio/token)
TTFA_EFFICIENT_MS = 3000.0    # Under 3s = efficient
TTFA_DELAYED_MS = 8000.0      # Under 8s = delayed, over = blocked


class InteractionEvaluator:
    """
    Evaluates the quality of a completed turn using heuristic metrics.
    Does NOT use the LLM — this is a rule-based evaluator.

    Usage:
        evaluator = InteractionEvaluator()
        result = evaluator.evaluate(turn_id, response, ttfa_ms)
    """

    def evaluate(
        self,
        turn_id: str,
        response: str,
        ttfa_ms: float = 0.0,
        interrupted: bool = False,
    ) -> EvaluationResult:
        """
        Produce a quality assessment for a completed turn.

        Args:
            turn_id: Unique identifier for this turn.
            response: Sentri's full generated response.
            ttfa_ms: Time to first audio in milliseconds.
            interrupted: Whether the turn was interrupted.

        Returns:
            EvaluationResult with quality score and latency profile.
        """
        quality = self._compute_quality(response, interrupted)
        latency = self._classify_latency(ttfa_ms)

        result = EvaluationResult(
            turn_id=turn_id,
            quality_score=quality,
            latency_profile=latency,
        )

        logger.info(
            f"[{turn_id}] Evaluation — quality={quality:.2f}, "
            f"latency={latency.value}, interrupted={interrupted}"
        )
        return result

    @staticmethod
    def _compute_quality(response: str, interrupted: bool) -> float:
        """
        Heuristic quality score. Phase 1 uses simple length and
        interruption-based scoring. Will be replaced with LLM-graded
        evaluation in later phases.
        """
        if not response or not response.strip():
            return 0.0

        score = 0.7  # Baseline — a response was generated

        # Penalize very short responses (might indicate failure)
        word_count = len(response.split())
        if word_count < 3:
            score -= 0.2
        elif word_count > 10:
            score += 0.1

        # Penalize interruption (user cut Sentri off)
        if interrupted:
            score -= 0.15

        return max(0.0, min(1.0, score))

    @staticmethod
    def _classify_latency(ttfa_ms: float) -> LatencyProfile:
        """Classify time-to-first-audio into a semantic latency profile."""
        if ttfa_ms <= 0.0:
            # No timing data available — assume efficient
            return LatencyProfile.EFFICIENT
        if ttfa_ms <= TTFA_EFFICIENT_MS:
            return LatencyProfile.EFFICIENT
        if ttfa_ms <= TTFA_DELAYED_MS:
            return LatencyProfile.DELAYED
        return LatencyProfile.BLOCKED
