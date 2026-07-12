import json
import logging
from app.memory.contracts import MemoryEntry, MemoryQuery
from app.memory.runtime import MemoryRuntime

logger = logging.getLogger("memory_adapter")

class MemoryAdapter:
    """
    Temporary MemoryAdapter providing backward compatibility for legacy tool interfaces.
    """
    def __init__(self, runtime: MemoryRuntime):
        self.runtime = runtime

    def remember_fact(self, fact: str, category: str, turn_id: str = "legacy") -> str:
        """
        Adapts legacy remember_fact(fact, category) to structured MemoryRuntime.remember().
        """
        # Map legacy categories to schema-allowed categories
        cat = category.strip().lower()
        if cat == "user":
            db_category = "Fact"
            predicate = "has_fact"
        elif cat == "directives":
            db_category = "Preference"
            predicate = "preferred_style"
        else:
            # Fallback/Capitalization check
            capitalized = category.capitalize()
            if capitalized in ("Identity", "Career", "Preference", "Lifestyle", "Relationship", "Goal", "Project", "Fact"):
                db_category = capitalized
            else:
                db_category = "Fact"
            predicate = "has_fact"

        entry = MemoryEntry(
            id="",
            category=db_category,
            subject="user",
            predicate=predicate,
            object=fact.strip(),
            confidence=0.95,
            verification_status="VERIFIED",
            origin="USER_EXPLICIT"
        )
        
        try:
            self.runtime.remember(entry, turn_id)
            return json.dumps({
                "status": "success", 
                "message": f"Memory stored under category '{db_category}'."
            })
        except Exception as e:
            logger.error(f"Adapter failed to store memory: {e}")
            return json.dumps({"status": "error", "message": str(e)})

    def search_memory(self, query: str) -> str:
        """
        Adapts legacy search_memory(query) to Structured Memory queries.
        """
        try:
            # Query all facts
            db_query = MemoryQuery(limit=100)
            res = self.runtime.recall(db_query)
            
            # Simple keyword match on object content
            keywords = query.strip().lower().split()
            matched_facts = []
            for entry in res.memories:
                obj_lower = entry.object.lower()
                # If any keyword matches, include it
                if any(kw in obj_lower for kw in keywords):
                    matched_facts.append(entry.object)
                    
            return json.dumps({"results": matched_facts})
        except Exception as e:
            logger.error(f"Adapter failed to search memory: {e}")
            return json.dumps({"results": [], "error": str(e)})
