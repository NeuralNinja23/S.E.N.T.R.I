from typing import List, Dict, Any, Optional
from app.conversation.contracts import ReasoningRequest

class PromptBuilder:
    """
    Orchestrates the construction of a standardized ReasoningRequest contract
    by composing the system prompt, memory contexts, and conversation history.
    """
    def __init__(self):
        pass

    def build(
        self,
        system_prompt: str,
        memory: Optional[str],
        history: List[Dict[str, Any]],
        transcript: str
    ) -> ReasoningRequest:
        """
        Assembles inputs into a ReasoningRequest payload contract.
        """
        return ReasoningRequest(
            system_prompt=system_prompt,
            memory=memory,
            history=history,
            user_input=transcript
        )
