"""
Behavioral Adapter.

Translates semantic BehavioralState configurations into runtime prompts
and memory budget parameters, influencing Sentri's execution behavior.
"""

from app.capability_2.learning.contracts import BehavioralState
from app.services.logger import get_logger

logger = get_logger("behavioral_adapter")


class BehavioralAdapter:
    """
    Translates semantic state properties into concrete runtime parameters.
    """

    @staticmethod
    def adapt_prompt(base_prompt: str, state: BehavioralState) -> str:
        """
        Appends style and interaction guidelines to the system prompt
        based on active behavioral state settings.
        """
        guidelines = []

        # 1. Adapt Conversation Style
        if state.conversation_style == "minimal":
            guidelines.append(
                "- CONVERSATION STYLE [MINIMAL]: Be extremely brief, concise, and direct. "
                "Answer in as few words as possible. Avoid conversational fluff, greetings, "
                "or explanations unless specifically requested."
            )
        elif state.conversation_style == "academic":
            guidelines.append(
                "- CONVERSATION STYLE [ACADEMIC]: Provide highly detailed, authoritative, "
                "and comprehensive responses. Include background context, academic depth, "
                "and thorough logical reasoning."
            )

        # 2. Adapt Dialogue Policy
        if state.dialogue_policy == "assertive":
            guidelines.append(
                "- DIALOGUE POLICY [ASSERTIVE]: Take the lead in guiding the conversation. "
                "Proactively offer solutions, guide the user, and directly push back or "
                "correct the user if they state something incorrect or assume a wrong premise."
            )

        # 3. Adapt Interaction Preference
        if state.interaction_preference == "speech_focused":
            guidelines.append(
                "- INTERACTION PREFERENCE [SPEECH]: Optimize your response for text-to-speech. "
                "Write in natural, easy-to-read spoken sentences. Completely avoid markdown, "
                "bold headers, bullet points, tables, or code blocks that are difficult to speak."
            )
        elif state.interaction_preference == "text_focused":
            guidelines.append(
                "- INTERACTION PREFERENCE [TEXT]: Optimize your response for on-screen reading. "
                "Use rich markdown formatting, bold headers, list items, and code blocks to organize information."
            )

        if guidelines:
            adapted_block = (
                "\n\n=== RUNTIME ADAPTED BEHAVIOR DIRECTIVES ===\n"
                + "\n".join(guidelines)
                + "\n============================================\n"
            )
            logger.info(
                f"Adapted system prompt with style guidelines: "
                f"style={state.conversation_style}, policy={state.dialogue_policy}, "
                f"pref={state.interaction_preference}"
            )
            return base_prompt + adapted_block

        return base_prompt

    @staticmethod
    def adapt_planning_budget(base_budget: int, state: BehavioralState) -> int:
        """
        Translates planning behavior into dynamic context retrieval budgets.
        """
        original_budget = base_budget

        if state.planning_behavior == "concise":
            # Cap retrieval to keep it small and fast
            adapted_budget = min(5, base_budget // 2)
            adapted_budget = max(1, adapted_budget)
        elif state.planning_behavior == "deep":
            # Elevate retrieval budget for comprehensive context
            adapted_budget = max(15, base_budget * 2)
        else:
            # Balanced / Default
            adapted_budget = base_budget

        if adapted_budget != original_budget:
            logger.info(
                f"Adapted planning budget from {original_budget} to {adapted_budget} "
                f"based on planning_behavior={state.planning_behavior}"
            )

        return adapted_budget
