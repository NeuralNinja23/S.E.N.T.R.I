import datetime
from pathlib import Path
from typing import Optional

class SystemPromptProvider:
    """
    Handles reading the sentinel.md system instructions and appending active context
    such as local date/time, and manages prompt overrides.
    """
    def __init__(self, instruction_path: Optional[Path] = None):
        if instruction_path is None:
            self.instruction_path = Path(__file__).resolve().parent.parent / "Sentinel" / "Instructions" / "sentinel.md"
        else:
            self.instruction_path = instruction_path

    def build(self, override_prompt: Optional[str] = None) -> str:
        """
        Builds the baseline system instruction string with active time context.
        """
        if override_prompt is not None:
            return override_prompt

        try:
            with open(self.instruction_path, "r", encoding="utf-8") as f:
                base_instruction = f.read()
        except FileNotFoundError:
            base_instruction = "You are Sentinel, a highly sophisticated digital assistant."

        import os
        current_dt = datetime.datetime.now().strftime("%A, %B %d, %Y, %I:%M %p")
        time_context = (
            f"\n\n=== TEMPORAL & ENVIRONMENT REALITY ===\n"
            f"- Current Date/Time: {current_dt}\n"
        )
        location = os.getenv("LOCAL_LOCATION")
        if location:
            time_context += f"- Current Location: {location}\n"
        time_context += "======================================\n"
        return base_instruction + time_context
