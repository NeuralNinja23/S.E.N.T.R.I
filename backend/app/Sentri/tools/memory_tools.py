from app.services.logger import get_logger

from app.capability_1.core.runtime import MemoryRuntime
from app.capability_1.infra.adapter import MemoryAdapter

logger = get_logger("memory_tools")

_runtime = None
_adapter = None


def _get_adapter() -> MemoryAdapter:
    global _runtime, _adapter
    if _adapter is None:
        _runtime = MemoryRuntime()
        _adapter = MemoryAdapter(_runtime)
    return _adapter


def remember_fact(fact: str, category: str) -> str:
    """
    Saves a new user fact or standing instruction to persistent memory.
    - fact: The details or rule to remember (e.g. "User boxes at Trenches Gym").
    - category: Must be 'user' (for facts about the user) or 'directives' (for response style/tone/behavior instructions).
    """
    adapter = _get_adapter()
    return adapter.remember_fact(fact, category)


def search_memory(query: str) -> str:
    """
    Searches the persistent memory graph for facts matching the query.
    - query: Keywords to search for.
    """
    adapter = _get_adapter()
    return adapter.search_memory(query)


def forget_fact(query: str) -> str:
    """
    Deletes any verified user facts or preferences matching the query terms from persistent memory.
    - query: Keywords or topics to forget (e.g. "Hospitality", "Rohan", "favorite color").
    """
    adapter = _get_adapter()
    return adapter.forget_fact(query)
