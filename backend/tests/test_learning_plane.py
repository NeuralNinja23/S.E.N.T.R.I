"""
Unit tests for the Capability 2 Learning Plane.
Covers reflection contracts, evaluation, state management, split routing, and adaptation.
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.capability_2.learning.contracts import (
    Observation,
    ObservationCategory,
    ReflectionResult,
    MemoryCommand,
    BehaviorCommand,
    MemoryAction,
    BehaviorTarget,
    BehaviorOperation,
    BehavioralState,
    LatencyProfile,
)
from app.capability_2.learning.evaluation.evaluator import InteractionEvaluator
from app.capability_2.learning.behavior.state import BehavioralStateManager
from app.capability_2.learning.adaptation.adapter import BehavioralAdapter


class TestLearningPlane(unittest.TestCase):
    def test_contracts_initialization(self):
        """Verify contracts can be initialized with correct defaults."""
        obs = Observation(
            category=ObservationCategory.KNOWLEDGE,
            description="User prefers python",
            raw_phrase="python",
            confidence=0.9,
        )
        self.assertEqual(obs.category, ObservationCategory.KNOWLEDGE)
        self.assertEqual(obs.confidence, 0.9)

        m_cmd = MemoryCommand(
            action=MemoryAction.REMEMBER,
            subject="user",
            predicate="prefers",
            object="python",
            confidence=0.8,
        )
        self.assertEqual(m_cmd.action, MemoryAction.REMEMBER)
        self.assertEqual(m_cmd.category, "Preferences")

    def test_interaction_evaluator(self):
        """Verify the rule-based evaluator computes scores and profiles correctly."""
        evaluator = InteractionEvaluator()

        # Efficient turn
        res1 = evaluator.evaluate(
            turn_id="test_turn",
            response="Short sentence answer.",
            ttfa_ms=2500.0,
            interrupted=False,
        )
        self.assertEqual(res1.latency_profile, LatencyProfile.EFFICIENT)
        self.assertGreaterEqual(res1.quality_score, 0.5)

        # Delayed turn
        res2 = evaluator.evaluate(
            turn_id="test_turn",
            response="Another short response.",
            ttfa_ms=6000.0,
            interrupted=False,
        )
        self.assertEqual(res2.latency_profile, LatencyProfile.DELAYED)

        # Interrupted turn penalization
        res3 = evaluator.evaluate(
            turn_id="test_turn",
            response="This response was cut off by user input.",
            ttfa_ms=1000.0,
            interrupted=True,
        )
        self.assertLess(res3.quality_score, res1.quality_score)

    def test_behavioral_adapter(self):
        """Verify behavioral adapter applies correct prompt and budget overrides."""
        # 1. Prompt adaptation
        state_min = BehavioralState(conversation_style="minimal")
        prompt = BehavioralAdapter.adapt_prompt("Base prompt instructions.", state_min)
        self.assertIn("CONVERSATION STYLE [MINIMAL]", prompt)

        state_acad = BehavioralState(conversation_style="academic")
        prompt_acad = BehavioralAdapter.adapt_prompt("Base prompt instructions.", state_acad)
        self.assertIn("CONVERSATION STYLE [ACADEMIC]", prompt_acad)

        # 2. Budget adaptation
        state_deep = BehavioralState(planning_behavior="deep")
        budget_deep = BehavioralAdapter.adapt_planning_budget(20, state_deep)
        self.assertEqual(budget_deep, 40)

        state_conc = BehavioralState(planning_behavior="concise")
        budget_conc = BehavioralAdapter.adapt_planning_budget(20, state_conc)
        self.assertEqual(budget_conc, 5)


if __name__ == "__main__":
    unittest.main()
