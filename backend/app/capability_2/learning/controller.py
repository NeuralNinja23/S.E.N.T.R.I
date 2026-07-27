"""
Learning Controller — Learning Plane orchestrator.

Coordinates post-turn analysis: runs the ReflectionEngine and
InteractionEvaluator, splits observations into Memory and Behavior commands,
and routes commands to their respective storage/state handlers.
"""

import uuid
from typing import Optional

from app.capability_2.learning.contracts import (
    ReflectionResult,
    EvaluationResult,
    MemoryAction,
)
from app.capability_2.learning.reflection.engine import ReflectionEngine
from app.capability_2.learning.evaluation.evaluator import InteractionEvaluator
from app.capability_2.learning.behavior.router import ReflectionSplit
from app.services.logger import get_logger

logger = get_logger("learning_controller")


class LearningController:
    """
    Orchestrates post-turn reflection, evaluation, split routing,
    and command execution.
    """

    def __init__(
        self,
        engine: Optional[ReflectionEngine] = None,
        evaluator: Optional[InteractionEvaluator] = None,
        router: Optional[ReflectionSplit] = None,
    ):
        self.engine = engine or ReflectionEngine()
        self.evaluator = evaluator or InteractionEvaluator()
        self.router = router or ReflectionSplit()

    async def process_post_turn(
        self,
        turn_id: str,
        user_input: str,
        response: str,
        ttfa_ms: float = 0.0,
        interrupted: bool = False,
    ) -> tuple[Optional[ReflectionResult], Optional[EvaluationResult]]:
        """
        Run the complete background learning and evaluation cycle.
        """
        logger.info(f"[{turn_id}] Starting post-turn learning workflow")

        # 1. Reflection
        reflection_result = await self.engine.run(
            turn_id=turn_id,
            user_input=user_input,
            response=response,
            interrupted=interrupted,
        )

        # 2. Evaluation
        evaluation_result = self.evaluator.evaluate(
            turn_id=turn_id,
            response=response,
            ttfa_ms=ttfa_ms,
            interrupted=interrupted,
        )

        # 3. Router Split
        if reflection_result.observations:
            memory_cmds, behavior_cmds = await self.router.route(reflection_result)

            # 4. Command Dispatch
            await self._dispatch_memory_commands(turn_id, memory_cmds)
            await self._dispatch_behavior_commands(turn_id, behavior_cmds)

        return reflection_result, evaluation_result

    async def _dispatch_memory_commands(self, turn_id: str, commands) -> None:
        """Execute memory commands via Capability 1 APIs."""
        if not commands:
            return

        try:
            from app.capability_1.core.runtime import MemoryRuntime
            from app.capability_1.core.contracts import MemoryEntry

            runtime = MemoryRuntime()

            for cmd in commands:
                if cmd.action != MemoryAction.REMEMBER:
                    # DELETE/UPDATE are not supported in auto-extraction yet
                    logger.debug(f"[{turn_id}] Memory action {cmd.action.value} not supported")
                    continue

                entry = MemoryEntry(
                    id=uuid.uuid4().hex,
                    category=cmd.category,
                    subject=cmd.subject,
                    predicate=cmd.predicate,
                    object=cmd.object,
                    confidence=cmd.confidence,
                    verification_status="INFERRED",  # Always inferred first per lifecycle
                    origin="AUTO_EXTRACTED",
                )

                logger.info(
                    f"[{turn_id}] Executing MemoryCommand: "
                    f"remember('{entry.subject} {entry.predicate} {entry.object}')"
                )
                
                # Call public Capability 1 Memory API safely in thread executor (blocking db call)
                import asyncio
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None, runtime.remember, entry, turn_id
                )

        except Exception as e:
            logger.error(f"[{turn_id}] Failed to dispatch memory commands: {e}")

    async def _dispatch_behavior_commands(self, turn_id: str, commands) -> None:
        """Execute behavior commands via Capability 2 BehavioralStateManager."""
        if not commands:
            return

        try:
            from app.capability_2.learning.behavior.state import BehavioralStateManager
            state_manager = BehavioralStateManager()
            
            import asyncio
            loop = asyncio.get_running_loop()

            for cmd in commands:
                logger.info(
                    f"[{turn_id}] Executing BehaviorCommand: "
                    f"target={cmd.target.value}, op={cmd.operation.value}, "
                    f"value={cmd.value}, confidence={cmd.confidence}"
                )
                await loop.run_in_executor(
                    None, state_manager.apply_command, cmd
                )
        except Exception as e:
            logger.error(f"[{turn_id}] Failed to dispatch behavior commands: {e}")
