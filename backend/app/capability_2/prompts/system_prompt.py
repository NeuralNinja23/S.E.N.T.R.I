import datetime
from pathlib import Path
from typing import Optional


class SystemPromptProvider:
    """
    Handles reading the sentri.md system instructions and appending active context
    such as local date/time, and manages prompt overrides.
    """

    def __init__(self, instruction_path: Optional[Path] = None):
        if instruction_path is None:
            self.instruction_path = (
                Path(__file__).resolve().parent.parent.parent  # prompts/ → capability_2/ → app/
                / "Sentri"
                / "Instructions"
                / "sentri.md"
            )
        else:
            self.instruction_path = instruction_path

    def build(self, override_prompt: Optional[str] = None) -> str:
        """
        Builds the baseline system instruction string with active time context.
        Bug #2: Removed hardcoded British butler voice_constraint — sentri.md is the sole persona source.
        """
        if override_prompt is not None:
            return override_prompt

        try:
            with open(self.instruction_path, "r", encoding="utf-8") as f:
                base_instruction = f.read()
        except FileNotFoundError:
            base_instruction = (
                "You are Sentri, a highly sophisticated digital assistant."
            )

        # Bug #2: No persona override prepended — sentri.md defines the Digital Human persona directly.

        import os
        import time

        now = datetime.datetime.now()
        current_dt = now.strftime("%A, %B %d, %Y")
        current_time = now.strftime("%I:%M %p")
        hour = now.hour
        if hour < 12:
            time_of_day = "Morning"
        elif hour < 17:
            time_of_day = "Afternoon"
        else:
            time_of_day = "Evening"

        time_context = (
            f"\n\n=== TEMPORAL & ENVIRONMENT REALITY ===\n"
            f"- Current Date: {current_dt}\n"
            f"- Current Time: {current_time}\n"
            f"- Time of Day: {time_of_day}\n"
            f"- For greetings use 'Good {time_of_day.lower()}'. Do NOT mention the month, season, or year.\n"
        )
        location = os.getenv("LOCAL_LOCATION")
        if location:
            time_context += f"- Current Location: {location}\n"
        time_context += "======================================\n"

        # Bypasses Ollama's prefix prompt caching to ensure fresh date/time and rules are loaded
        time_context += f"\n<!-- cache_bypass: {time.time()} -->\n"

        return base_instruction + time_context
