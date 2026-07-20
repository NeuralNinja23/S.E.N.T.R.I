import json
import logging
from app.capability_1.core.contracts import MemoryEntry, MemoryQuery
from app.capability_1.core.runtime import MemoryRuntime

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
            if capitalized in (
                "Identity",
                "Career",
                "Preference",
                "Lifestyle",
                "Relationship",
                "Goal",
                "Project",
                "Fact",
            ):
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
            origin="USER_EXPLICIT",
        )

        try:
            self.runtime.remember(entry, turn_id)
            return json.dumps(
                {
                    "status": "success",
                    "message": f"Memory stored under category '{db_category}'.",
                }
            )
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

    def forget_fact(self, query: str) -> str:
        """
        Deletes memory entries matching the query keywords.
        """
        try:
            keywords = [
                w.strip().lower()
                for w in query.strip().split()
                if w.strip().lower()
                not in (
                    "about",
                    "my",
                    "the",
                    "from",
                    "your",
                    "memory",
                    "that",
                    "record",
                )
            ]
            if not keywords:
                return json.dumps(
                    {"status": "error", "message": "No query keywords provided."}
                )

            all_memories = self.runtime.list_memories()
            deleted_count = 0
            for entry in all_memories:
                match = False
                for w in keywords:
                    if (
                        w in entry.category.lower()
                        or w in entry.subject.lower()
                        or w in entry.predicate.lower()
                        or w in entry.object.lower()
                    ):
                        match = True
                        break
                if match:
                    self.runtime.delete(entry.id)
                    deleted_count += 1

            return json.dumps(
                {
                    "status": "success",
                    "message": f"Successfully deleted {deleted_count} matching memory entries.",
                }
            )
        except Exception as e:
            logger.error(f"Adapter failed to forget memory: {e}")
            return json.dumps({"status": "error", "message": str(e)})
