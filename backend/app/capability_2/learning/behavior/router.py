"""
Reflection Split & Command Router.

Translates raw turn observations (ReflectionResult) into structured
MemoryCommands (for Capability 1) and BehaviorCommands (for Capability 2).
"""

import json
import logging
from typing import List, Tuple

import httpx

from app.config import REFLECTION_PROVIDER, REFLECTION_MODEL
from app.capability_2.learning.contracts import (
    ReflectionResult,
    MemoryCommand,
    BehaviorCommand,
    MemoryAction,
    BehaviorTarget,
    BehaviorOperation,
    ObservationCategory,
)
from app.services.logger import get_logger

logger = get_logger("reflection_split")

ROUTER_SYSTEM_PROMPT = """You are a conversation learning router. Your job is to translate raw conversation observations into structured system commands.

You will receive a list of observations.

Translate each observation into one of two command types:

1. MemoryCommand (for KNOWLEDGE observations):
   - "action": "REMEMBER", "UPDATE", or "DELETE"
   - "subject": Who the fact is about (typically "user")
   - "predicate": The relationship or attribute (e.g., "prefers", "dislikes", "lives_in", "works_as")
   - "object": The value or detail (e.g., "brief responses", "Paris", "software engineer")
   - "category": The memory category (typically "Preferences", "Identity", "Career")
   - "confidence": Float between 0.0 and 1.0

2. BehaviorCommand (for BEHAVIOR observations):
   - "target": Must be one of: "CONVERSATION_STYLE", "PLANNING_BEHAVIOR", "DIALOGUE_POLICY", "INTERACTION_PREFERENCE"
   - "operation": Must be either "REINFORCE" (if reinforcing existing style/behavior) or "SHIFT" (if moving to a different style)
   - "value": The target behavior value. Allowed values:
     - For CONVERSATION_STYLE: "minimal", "conversational", "academic"
     - For PLANNING_BEHAVIOR: "concise", "balanced", "deep", "interactive"
     - For DIALOGUE_POLICY: "assertive", "cooperative"
     - For INTERACTION_PREFERENCE: "text_focused", "speech_focused", "hybrid"
   - "confidence": Float between 0.0 and 1.0

Return a JSON object with two arrays:
{
  "memory_commands": [...],
  "behavior_commands": [...]
}

Rules:
- Be strict with the allowed Enum values for targets, operations, and values.
- Only generate commands for observations with high confidence.
- Return ONLY the JSON object, no other text."""


class ReflectionSplit:
    """
    Translates raw observations from a ReflectionResult into
    actionable MemoryCommands and BehaviorCommands.
    """

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str = "http://127.0.0.1:11434",
    ):
        self.model_name = model_name or REFLECTION_MODEL
        self.base_url = base_url

    async def route(
        self, result: ReflectionResult
    ) -> Tuple[List[MemoryCommand], List[BehaviorCommand]]:
        """
        Route observations to their respective planes.
        """
        if not result.observations:
            return [], []

        # Convert observations to JSON string for the LLM input
        obs_payload = [
            {
                "category": obs.category.value,
                "description": obs.description,
                "raw_phrase": obs.raw_phrase,
                "confidence": obs.confidence,
            }
            for obs in result.observations
        ]

        user_content = json.dumps(obs_payload, indent=2)

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "think": False,
            "keep_alive": -1,
            "options": {
                "temperature": 0.2,  # Low temperature for strict structured output
                "num_ctx": 4096,
                "num_predict": 512,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(
                    f"{self.base_url}/api/chat", json=payload
                )
                if res.status_code != 200:
                    logger.error(
                        f"ReflectionSplit LLM returned HTTP {res.status_code}"
                    )
                    return [], []

                data = res.json()
                raw_content = data.get("message", {}).get("content", "")
                return self._parse_commands(raw_content)

        except Exception as e:
            logger.error(f"ReflectionSplit routing failed: {e}")
            return [], []

    @staticmethod
    def _parse_commands(
        raw: str,
    ) -> Tuple[List[MemoryCommand], List[BehaviorCommand]]:
        """Parse router LLM output into typed commands."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"ReflectionSplit returned malformed JSON: {raw[:200]}")
            return [], []

        memory_cmds: List[MemoryCommand] = []
        behavior_cmds: List[BehaviorCommand] = []

        # Parse MemoryCommands
        for m_entry in data.get("memory_commands", []):
            try:
                action = MemoryAction(m_entry.get("action", "").upper())
                cmd = MemoryCommand(
                    action=action,
                    subject=m_entry.get("subject", ""),
                    predicate=m_entry.get("predicate", ""),
                    object=m_entry.get("object", ""),
                    confidence=float(m_entry.get("confidence", 1.0)),
                    category=m_entry.get("category", "Preferences"),
                )
                memory_cmds.append(cmd)
            except (ValueError, KeyError) as e:
                logger.debug(f"Skipping malformed MemoryCommand: {e}")
                continue

        # Parse BehaviorCommands
        for b_entry in data.get("behavior_commands", []):
            try:
                target = BehaviorTarget(b_entry.get("target", "").upper())
                operation = BehaviorOperation(b_entry.get("operation", "").upper())
                cmd = BehaviorCommand(
                    target=target,
                    operation=operation,
                    value=b_entry.get("value", ""),
                    confidence=float(b_entry.get("confidence", 1.0)),
                )
                behavior_cmds.append(cmd)
            except (ValueError, KeyError) as e:
                logger.debug(f"Skipping malformed BehaviorCommand: {e}")
                continue

        logger.info(
            f"Routed observations to {len(memory_cmds)} MemoryCommand(s) "
            f"and {len(behavior_cmds)} BehaviorCommand(s)"
        )
        return memory_cmds, behavior_cmds
