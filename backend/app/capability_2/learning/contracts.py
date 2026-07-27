"""
Capability 2 — Learning Plane Contracts

Defines the core data models, enums, and command structures for the
Reflection Engine, Evaluation, Behavioral State, and Adaptation layers.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List


# ──────────────────────────────────────────────────────────────────────────────
#  ENUMS — Strict type-safe identifiers for commands and observations
# ──────────────────────────────────────────────────────────────────────────────


class MemoryAction(Enum):
    """Actions that can be performed on declarative knowledge (Capability 1)."""
    REMEMBER = "REMEMBER"
    DELETE = "DELETE"
    UPDATE = "UPDATE"


class BehaviorTarget(Enum):
    """Semantic behavioral dimensions that the Learning Plane can influence."""
    CONVERSATION_STYLE = "CONVERSATION_STYLE"
    PLANNING_BEHAVIOR = "PLANNING_BEHAVIOR"
    DIALOGUE_POLICY = "DIALOGUE_POLICY"
    INTERACTION_PREFERENCE = "INTERACTION_PREFERENCE"


class BehaviorOperation(Enum):
    """Operations that can be applied to a behavioral target."""
    REINFORCE = "REINFORCE"
    SHIFT = "SHIFT"


class ObservationCategory(Enum):
    """Classification of a reflection observation."""
    KNOWLEDGE = "KNOWLEDGE"
    BEHAVIOR = "BEHAVIOR"


class LatencyProfile(Enum):
    """Qualitative assessment of turn latency performance."""
    EFFICIENT = "EFFICIENT"
    DELAYED = "DELAYED"
    BLOCKED = "BLOCKED"


# ──────────────────────────────────────────────────────────────────────────────
#  COMMANDS — Decision outputs from the Reflection Split router
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class MemoryCommand:
    """
    Command to modify declarative knowledge.
    Produced by the Reflection Split and executed by Capability 1.
    """
    action: MemoryAction
    subject: str
    predicate: str
    object: str
    confidence: float
    category: str = "Preferences"


@dataclass
class BehaviorCommand:
    """
    Command to influence procedural behavior.
    Produced by the Reflection Split and executed by the BehavioralStateManager.
    """
    target: BehaviorTarget
    operation: BehaviorOperation
    value: str
    confidence: float = 1.0


# ──────────────────────────────────────────────────────────────────────────────
#  OBSERVATIONS — Structured outputs from the Reflection Engine
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class Observation:
    """A single observation extracted from a completed turn."""
    category: ObservationCategory
    description: str
    raw_phrase: str
    confidence: float


@dataclass
class ReflectionResult:
    """
    Complete output of the Reflection Engine for a single turn.
    Contains raw observations that have not yet been routed.
    """
    turn_id: str
    observations: List[Observation] = field(default_factory=list)
    interrupted: bool = False


# ──────────────────────────────────────────────────────────────────────────────
#  EVALUATION — Quality assessment output (separate from reflection)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class EvaluationResult:
    """
    Quality assessment of a completed turn.
    Produced by the InteractionEvaluator, not the Reflection Engine.
    """
    turn_id: str
    quality_score: float  # 0.0 - 1.0
    latency_profile: LatencyProfile


# ──────────────────────────────────────────────────────────────────────────────
#  SEMANTIC STATE — Behavioral State (persisted by BehavioralStateManager)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class BehavioralState:
    """
    Semantic representation of Sentri's current behavioral posture.
    These are abstract behavioral dimensions, not implementation knobs.
    The BehavioralAdapter translates these into runtime parameters.
    """
    conversation_style: str = "conversational"    # "minimal" | "conversational" | "academic"
    planning_behavior: str = "balanced"           # "concise" | "deep" | "interactive"
    dialogue_policy: str = "cooperative"          # "assertive" | "cooperative"
    interaction_preference: str = "hybrid"        # "text_focused" | "speech_focused" | "hybrid"
