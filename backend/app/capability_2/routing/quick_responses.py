"""
Quick Response Engine — Deterministic responses for predictable intents.

Bypasses the LLM entirely for greetings, identity questions, time/date queries,
and other repetitive intents. Zero inference latency, total output control.
"""

import re
import datetime
from typing import Optional


class QuickResponseEngine:
    """
    Returns instant, deterministic responses for known intents.
    If the intent is not handled, returns None — letting the LLM take over.
    """

    def respond(self, intent: str, transcript: str) -> Optional[str]:
        """
        Attempt to produce a quick response for the given intent + transcript.
        Returns the response string, or None if the LLM should handle it.
        """
        query = transcript.lower().strip().strip("?!. ")

        # ── Greetings ──────────────────────────────────────────────
        if self._is_greeting(intent, query):
            return self._greeting()

        # ── Identity (who are you / what's your name) ─────────────
        if self._is_identity_question(query):
            return self._identity()

        # ── User name (what is my name) ───────────────────────────
        if self._is_name_question(query):
            return self._user_name()

        # ── Time query ────────────────────────────────────────────
        if self._is_time_question(query):
            return self._current_time()

        # ── Date query ────────────────────────────────────────────
        if self._is_date_question(query):
            return self._current_date()

        # ── GPU usage query (Bug #14: checked BEFORE RAM to prevent vram→ram shadowing)
        if self._is_gpu_question(query):
            return self._gpu_usage()

        # ── RAM usage query ───────────────────────────────────────
        if self._is_ram_question(query):
            return self._ram_usage()

        # ── CPU usage query ───────────────────────────────────────
        if self._is_cpu_question(query):
            return self._cpu_usage()

        # ── Disk usage query ──────────────────────────────────────
        if self._is_disk_question(query):
            return self._disk_usage()

        # ── Thank you / goodbye ───────────────────────────────────
        if self._is_thanks(query):
            return self._thanks()

        if self._is_goodbye(query):
            return self._goodbye()

        # ── Stop / be quiet ───────────────────────────────────────
        if self._is_stop(query):
            return None  # Return None to let governance handle the stop

        return None  # Not a quick-response intent — fall through to LLM

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  MATCHERS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _is_greeting(self, intent: str, query: str) -> bool:
        if intent == "IDENTITY_QUERY":
            greetings = (
                "hi",
                "hello",
                "hey",
                "greetings",
                "yo",
                "sup",
                "good morning",
                "good afternoon",
                "good evening",
                "whats up",
                "howdy",
            )
            return query in greetings or query.startswith(
                (
                    "hi ",
                    "hello ",
                    "hey ",
                    "good morning",
                    "good afternoon",
                    "good evening",
                )
            )
        return False

    def _is_identity_question(self, query: str) -> bool:
        # Match anything containing "who are you", "what is your name", "your name", etc.
        identity_keywords = (
            "who are you",
            "what are you",
            "your name",
            "who is sentri",
            "what is sentri",
            "tell me your name",
            "whats your name",
        )
        return any(k in query for k in identity_keywords) or (
            ("who" in query or "what" in query) and "name" in query and "your" in query
        )

    def _is_name_question(self, query: str) -> bool:
        # Match anything asking for user's own name
        return (
            "my name" in query or "who am i" in query or "do you know me" in query
        ) and any(w in query for w in ("what", "whats", "who", "do", "tell"))

    def _is_time_question(self, query: str) -> bool:
        # Match any variation of asking for the current time
        return "time" in query and any(
            w in query for w in ("what", "whats", "tell", "current", "now", "is it")
        )

    def _is_date_question(self, query: str) -> bool:
        # Match any variation of asking for the current date/day
        return any(
            k in query
            for k in (
                "what day",
                "what date",
                "today's date",
                "whats today",
                "what is today",
            )
        ) or (
            ("date" in query or "day" in query)
            and any(w in query for w in ("what", "whats", "tell", "today"))
        )

    def _is_thanks(self, query: str) -> bool:
        return query in (
            "thank you",
            "thanks",
            "thanks a lot",
            "thank you very much",
            "thank you sentri",
            "thanks sentri",
            "much appreciated",
        )

    def _is_goodbye(self, query: str) -> bool:
        return query in (
            "goodbye",
            "bye",
            "bye bye",
            "see you",
            "see you later",
            "good night",
            "goodnight",
            "see ya",
            "later",
        )

    def _is_stop(self, query: str) -> bool:
        return query in ("stop", "shut up", "be quiet", "silence", "enough")

    def _is_ram_question(self, query: str) -> bool:
        # Bug #13: word-boundary regex prevents "programming" / "drama" false positives
        return (
            bool(re.search(r"\bram\b", query))
            or "memory usage" in query
            or "virtual memory" in query
        )

    def _is_cpu_question(self, query: str) -> bool:
        # Bug #13: word-boundary regex prevents substring false positives like "occupy"
        return (
            bool(re.search(r"\bcpu\b", query))
            or "processor usage" in query
            or "processor utilization" in query
        )

    def _is_gpu_question(self, query: str) -> bool:
        # Bug #13: word-boundary regex — also prevents "vram" matching _is_ram_question
        return (
            bool(re.search(r"\bgpu\b", query))
            or "graphics card" in query
            or bool(re.search(r"\bvram\b", query))
        )

    def _is_disk_question(self, query: str) -> bool:
        return (
            "disk" in query
            or "storage" in query
            or "hard drive" in query
            or "hard disk" in query
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  RESPONSE GENERATORS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _time_of_day(self) -> str:
        hour = datetime.datetime.now().hour
        if hour < 12:
            return "morning"
        elif hour < 17:
            return "afternoon"
        else:
            return "evening"

    def _greeting(self) -> str:
        return f"Good {self._time_of_day()}."

    def _identity(self) -> str:
        return "I am Sentri, Someone Everyone Needs To Remember."

    def _user_name(self) -> str:
        # Pull preferred name from memory at runtime
        try:
            from app.capability_1.core.runtime import MemoryRuntime
            from app.capability_1.core.contracts import MemoryQuery

            runtime = MemoryRuntime()
            result = runtime.recall(
                MemoryQuery(
                    category="Identity",  # Bug #26: title-case to match how remember_fact stores it
                    subject="user",
                    limit=5,
                    include_inferred=True,
                )
            )
            for mem in result.memories:
                # Bug #16: lowercase predicate for case-insensitive match (PREFERRED_NAME, name, etc.)
                if mem.predicate.lower() in ("preferred_name", "name", "full_name"):
                    return f"Your name is {mem.object}."
        except Exception:
            pass
        return "Your name is Sir."

    def _current_time(self) -> str:
        now = datetime.datetime.now()
        return f"It is {now.strftime('%I:%M %p').lstrip('0')}."

    def _current_date(self) -> str:
        now = datetime.datetime.now()
        return f"Today is {now.strftime('%A, %B %d, %Y')}."

    def _ram_usage(self) -> str:
        try:
            import psutil

            mem = psutil.virtual_memory()
            return f"Your system's RAM usage is currently at {round(mem.percent, 1)}%."
        except Exception:
            return "I am currently unable to check your system's RAM usage."

    def _cpu_usage(self) -> str:
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=0.1)
            return f"CPU usage is currently at {round(cpu_percent, 1)}%."
        except Exception:
            return "I am currently unable to check your CPU usage."

    def _gpu_usage(self) -> str:
        try:
            import subprocess

            result = subprocess.run(
                "nvidia-smi --query-gpu=utilization.gpu,temperature.gpu --format=csv,noheader,nounits",
                capture_output=True,
                text=True,
                shell=True,
                timeout=3,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(",")
                gpu_percent = float(parts[0].strip())
                gpu_temp = float(parts[1].strip())
                return f"GPU utilization is at {round(gpu_percent, 1)}% with a temperature of {round(gpu_temp)} degrees."
        except Exception:
            pass
        return "I am currently unable to check your GPU metrics."

    def _disk_usage(self) -> str:
        try:
            import psutil
            import platform

            disk_path = "C:\\" if platform.system() == "Windows" else "/"
            disk = psutil.disk_usage(disk_path)
            disk_total = round(disk.total / (1024**3))
            disk_used = round(disk.used / (1024**3))
            disk_percent = round(disk.percent, 1)
            return f"Disk usage on your C drive is at {disk_percent}%, with {disk_used} gigabytes used of {disk_total} gigabytes total."
        except Exception:
            return "I am currently unable to retrieve your disk storage metrics."

    def _thanks(self) -> str:
        return "You're welcome."

    def _goodbye(self) -> str:
        return f"Good {self._time_of_day()}. Take care."
