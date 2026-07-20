import re
from typing import List, AsyncGenerator


class SpeechPlanner:
    """
    Decides when Sentri can naturally begin speaking by analyzing the streamed tokens
    acoustically rather than just grammatically. Serves as a prosodic phrase planner.
    """

    def __init__(self, max_tokens: int = 20, min_words_for_breath: int = 6):
        self.max_tokens = max_tokens
        self.min_words_for_breath = min_words_for_breath
        self.buffer: List[str] = []
        self.token_count = 0

        # Common titles/abbreviations in English
        self._abbreviations = {
            "mr",
            "ms",
            "mrs",
            "dr",
            "eg",
            "ie",
            "vs",
            "etc",
            "st",
            "ave",
            "rd",
            "co",
            "jr",
            "sr",
            "prof",
        }

    async def feed(self, token: str) -> AsyncGenerator[str, None]:
        """
        Appends a token to the buffer. Evaluates if the compiled text represents
        a point where a human can naturally begin speaking, and yields the phrase.
        """
        self.buffer.append(token)
        self.token_count += 1

        if self.should_flush():
            chunk = self.flush()
            if chunk:
                yield chunk

    def should_flush(self) -> bool:
        """
        Evaluates the current buffer text to decide if it's a natural speech boundary.
        """
        # 1. Hard threshold limit to avoid buffer bloat and excessive latency
        if self.token_count >= self.max_tokens:
            return True

        current_text = "".join(self.buffer)
        stripped = current_text.strip()
        if not stripped:
            return False

        last_char = stripped[-1]

        # 2. Check for sentence terminal punctuation (. ! ?)
        if last_char in (".", "?", "!"):
            # Protection A: Decimal check (e.g. "3.14")
            # If the period is preceded by a digit, check if we might be in a decimal
            if last_char == "." and len(stripped) > 1 and stripped[-2].isdigit():
                # Don't flush yet, wait for next tokens to see if it's a decimal
                return False

            # Protection B: Abbreviation check
            # Find the last word in the buffer (ignoring trailing punctuation)
            words = re.findall(r"\b[a-zA-Z]+\b", stripped)
            if words:
                last_word = words[-1].lower()
                if last_word in self._abbreviations:
                    return False

            return True

        # 3. Check for phrase terminal punctuation (breathing boundaries: , ; : —)
        if last_char in (",", ";", ":", "—"):
            # Only split at a breath boundary if the buffer has enough words to form a natural phrase
            word_count = len(re.findall(r"\w+", stripped))
            if word_count >= self.min_words_for_breath:
                return True

        return False

    def flush(self) -> str:
        """
        Clears the buffer and returns the compiled phrase.
        """
        if not self.buffer:
            return ""
        chunk = "".join(self.buffer).strip()
        self.buffer = []
        self.token_count = 0
        return chunk


# Alias for backward compatibility
ResponseChunker = SpeechPlanner
