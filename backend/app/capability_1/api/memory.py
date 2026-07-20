import logging
from typing import List
from app.capability_1.core.runtime import MemoryRuntime
from app.capability_1.core.context_builder import MemoryContextBuilder
from app.capability_1.core.contracts import MemoryQuery

logger = logging.getLogger("memory_api")
memory_runtime = MemoryRuntime()


def handle_memory_erasure(text_query: str) -> str | None:
    """
    Checks if a user query is a request to forget/delete information from memory.
    If matches, triggers deletion and returns a response string, otherwise returns None.
    """
    query_lower = text_query.lower().strip()
    if any(
        kw in query_lower
        for kw in [
            "forget ",
            "forget about ",
            "delete ",
            "erase ",
            "remove from memory",
            "clear memory",
        ]
    ):
        # Extract keywords to search and delete
        words = [
            w.strip()
            for w in query_lower.split()
            if w.strip()
            not in (
                "forget",
                "about",
                "delete",
                "erase",
                "remove",
                "clear",
                "from",
                "me",
                "to",
                "my",
                "the",
                "your",
                "memory",
                "record",
                "that",
            )
        ]
        if words:
            all_memories = memory_runtime.list_memories()
            deleted_count = 0
            for entry in all_memories:
                match = False
                for w in words:
                    if (
                        w in entry.category.lower()
                        or w in entry.subject.lower()
                        or w in entry.predicate.lower()
                        or w in entry.object.lower()
                    ):
                        match = True
                        break
                if match:
                    memory_runtime.delete(entry.id)
                    deleted_count += 1

            if deleted_count > 0:
                response_text = (
                    f"Done. I've removed {deleted_count} "
                    f"{'entry' if deleted_count == 1 else 'entries'} from memory."
                )
                logger.info(
                    f"Memory erasure executed for words {words}. Deleted {deleted_count} entries."
                )
            else:
                response_text = (
                    "I couldn't find any matching memory entries to delete. "
                    "Could you be more specific about what to forget?"
                )
            return response_text
    return None


def retrieve_memory_context(categories: List[str], budget: int) -> str:
    """
    Given a list of intent categories and a token budget, recalls relevant memories
    and formats them as a memory profile block.
    """
    res_memories = []
    for category in categories:
        q = MemoryQuery(
            category=category,
            subject="user",
            limit=budget,
            include_inferred=True,
        )
        res = memory_runtime.recall(q)
        res_memories.extend(res.memories)

    try:
        warm_profile_block = MemoryContextBuilder.build_context(
            res_memories, max_chars=6000, limit=budget
        )
    except Exception as mem_err:
        logger.error(f"Failed to build memory profile: {mem_err}")
        warm_profile_block = ""
    return warm_profile_block
