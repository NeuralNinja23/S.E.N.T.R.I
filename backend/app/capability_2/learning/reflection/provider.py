"""
Reflection Provider Interface and Implementations.

Decouples the Reflection Engine from any specific LLM backend.
The first implementation wraps the existing Ollama HTTP endpoint,
but future implementations may use distilled classifiers, rule engines,
or dedicated reflection models without touching the engine.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import List

import httpx

from app.config import REFLECTION_PROVIDER, REFLECTION_MODEL
from app.capability_2.learning.contracts import Observation, ObservationCategory

from app.services.logger import get_logger
logger = get_logger("reflection_provider")

# ──────────────────────────────────────────────────────────────────────────────
#  REFLECTION PROMPT — instructs the LLM to produce structured observations
# ──────────────────────────────────────────────────────────────────────────────

REFLECTION_SYSTEM_PROMPT = """You are a reflection engine. Your job is to observe a completed conversation turn and extract structured observations.

You will receive:
- The user's input (transcript)
- Sentri's response
- Whether the turn was interrupted

Your task:
1. Extract factual observations about the user (preferences, facts, corrections).
2. Extract behavioral observations about the interaction quality (style feedback, engagement signals).

Return a JSON array of observations. Each observation must have:
- "category": either "KNOWLEDGE" or "BEHAVIOR"
- "description": a clear, specific description of what was observed
- "raw_phrase": the exact phrase from the conversation that supports this observation
- "confidence": a float between 0.0 and 1.0

Rules:
- Only extract observations you are confident about (confidence >= 0.6).
- Do not invent observations. Only report what is clearly present.
- If there is nothing notable, return an empty array: []
- Return ONLY the JSON array, no other text.

Example output:
[
  {"category": "KNOWLEDGE", "description": "User prefers minimal responses", "raw_phrase": "just give me the short version", "confidence": 0.92},
  {"category": "BEHAVIOR", "description": "User responded positively to technical depth", "raw_phrase": "that's exactly what I needed", "confidence": 0.85}
]"""


# ──────────────────────────────────────────────────────────────────────────────
#  INTERFACE
# ──────────────────────────────────────────────────────────────────────────────


class IReflectionProvider(ABC):
    """
    Interface for reflection providers.
    Accepts turn data and returns structured observations.
    """

    @abstractmethod
    async def reflect(
        self,
        user_input: str,
        response: str,
        interrupted: bool = False,
    ) -> List[Observation]:
        """
        Analyze a completed turn and return structured observations.
        Must not block the main conversation loop.
        """
        ...


# ──────────────────────────────────────────────────────────────────────────────
#  IMPLEMENTATION — Ollama-backed reflection via direct HTTP
# ──────────────────────────────────────────────────────────────────────────────


class OllamaReflectionProvider(IReflectionProvider):
    """
    Reflection provider that queries a local Ollama endpoint
    for turn analysis. Uses non-streaming mode since reflection
    runs in the background after the turn completes.
    """

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str = "http://127.0.0.1:11434",
    ):
        self.model_name = model_name or REFLECTION_MODEL
        self.base_url = base_url

    async def reflect(
        self,
        user_input: str,
        response: str,
        interrupted: bool = False,
    ) -> List[Observation]:
        """Query Ollama for structured reflection on the completed turn."""
        user_content = (
            f"User Input: {user_input}\n"
            f"Sentri Response: {response}\n"
            f"Interrupted: {interrupted}"
        )

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "think": False,
            "keep_alive": -1,
            "options": {
                "temperature": 0.3,  # Low temperature for consistent structured output
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
                        f"Reflection provider returned HTTP {res.status_code}"
                    )
                    return []

                data = res.json()
                raw_content = data.get("message", {}).get("content", "")
                return self._parse_observations(raw_content)

        except Exception as e:
            logger.error(f"Reflection provider failed: {e}")
            return []

    @staticmethod
    def _parse_observations(raw: str) -> List[Observation]:
        """Parse LLM JSON output into typed Observation objects."""
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (fences)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            entries = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"Reflection provider returned non-JSON: {raw[:200]}")
            return []

        if not isinstance(entries, list):
            logger.warning("Reflection provider returned non-list JSON")
            return []

        observations: List[Observation] = []
        for entry in entries:
            try:
                cat_str = entry.get("category", "").upper()
                category = ObservationCategory(cat_str)
                obs = Observation(
                    category=category,
                    description=entry.get("description", ""),
                    raw_phrase=entry.get("raw_phrase", ""),
                    confidence=float(entry.get("confidence", 0.0)),
                )
                # Filter low-confidence observations
                if obs.confidence >= 0.6:
                    observations.append(obs)
            except (ValueError, KeyError) as parse_err:
                logger.debug(f"Skipping malformed observation: {parse_err}")
                continue

        return observations


# ──────────────────────────────────────────────────────────────────────────────
#  PROVIDER FACTORY — mirrors the existing ProviderRegistry pattern
# ──────────────────────────────────────────────────────────────────────────────


class DisabledReflectionProvider(IReflectionProvider):
    """No-op reflection provider that skips background LLM reflection calls."""
    async def reflect(self, user_input: str, response: str, interrupted: bool = False) -> List[Observation]:
        return []


def get_reflection_provider(
    provider_id: str | None = None,
) -> IReflectionProvider:
    """
    Factory function to resolve the configured reflection provider.
    Mirrors the ProviderRegistry pattern used in the streaming pipeline.
    """
    provider_id = provider_id or REFLECTION_PROVIDER
    if provider_id == "ollama":
        return OllamaReflectionProvider()
    elif provider_id in ("disabled", "none", "off"):
        return DisabledReflectionProvider()
    raise ValueError(f"Unknown reflection provider: {provider_id}")

