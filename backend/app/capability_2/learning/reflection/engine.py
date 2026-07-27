"""
Reflection Engine — Post-turn observation orchestrator.

The Reflection Engine's job is NOT to learn. Its job is to observe.
It accepts the completed turn data, delegates to a ReflectionProvider,
and returns a ReflectionResult containing structured observations.

This engine is always invoked asynchronously in the background
after the user-facing response has been fully delivered.
"""

import logging
from typing import Optional

from app.capability_2.learning.contracts import ReflectionResult
from app.capability_2.learning.reflection.provider import (
    IReflectionProvider,
    get_reflection_provider,
)

from app.services.logger import get_logger
logger = get_logger("reflection_engine")


class ReflectionEngine:
    """
    Orchestrates post-turn reflection by delegating to the
    configured IReflectionProvider and assembling results.

    Usage:
        engine = ReflectionEngine()
        result = await engine.run(turn_id, user_input, response)
    """

    def __init__(self, provider: Optional[IReflectionProvider] = None):
        self._provider = provider or get_reflection_provider()

    async def run(
        self,
        turn_id: str,
        user_input: str,
        response: str,
        interrupted: bool = False,
    ) -> ReflectionResult:
        """
        Execute reflection on a completed turn.

        Args:
            turn_id: Unique identifier for this turn.
            user_input: The user's transcript or text query.
            response: Sentri's full generated response.
            interrupted: Whether the turn was interrupted by the user.

        Returns:
            ReflectionResult containing typed observations.
        """
        logger.info(f"[{turn_id}] Reflection started")

        try:
            observations = await self._provider.reflect(
                user_input=user_input,
                response=response,
                interrupted=interrupted,
            )

            result = ReflectionResult(
                turn_id=turn_id,
                observations=observations,
                interrupted=interrupted,
            )

            logger.info(
                f"[{turn_id}] Reflection complete — "
                f"{len(observations)} observation(s) extracted"
            )

            # Log each observation at debug level
            for obs in observations:
                logger.debug(
                    f"  [{obs.category.value}] {obs.description} "
                    f"(confidence={obs.confidence:.2f})"
                )

            return result

        except Exception as e:
            logger.error(f"[{turn_id}] Reflection failed: {e}")
            # Return empty result on failure — reflection must never break the pipeline
            return ReflectionResult(
                turn_id=turn_id,
                observations=[],
                interrupted=interrupted,
            )
