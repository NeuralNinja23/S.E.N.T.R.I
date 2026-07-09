import json
from app.services.logger import get_logger

logger = get_logger("memory_tools")

def remember_fact(fact: str, category: str) -> str:
    """
    Saves a new user fact or standing instruction to persistent memory.
    - fact: The details or rule to remember (e.g. "User boxes at Trenches Gym").
    - category: Must be 'user' (for facts about the user) or 'directives' (for response style/tone/behavior instructions).
    """
    logger.info("remember_fact called, but memory database is currently disabled.")
    return json.dumps({"status": "success", "message": "Memory database is currently disabled. Fact was processed but not stored."})

def search_memory(query: str) -> str:
    """
    Searches the persistent memory graph for facts matching the query.
    - query: Keywords to search for.
    """
    logger.info("search_memory called, but memory database is currently disabled.")
    return json.dumps({"results": []})
