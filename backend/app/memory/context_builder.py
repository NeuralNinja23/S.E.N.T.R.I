import logging
from typing import List
from app.memory.contracts import MemoryEntry

logger = logging.getLogger("context_builder")

class MemoryContextBuilder:
    """
    MemoryContextBuilder ranks, filters, and formats structured MemoryEntry lists 
    into a clean context block for prompt injection.
    """
    @staticmethod
    def build_context(memories: List[MemoryEntry], max_chars: int = 8000, limit: int = 50) -> str:
        """
        Ranks, filters, and formats candidate memories.
        
        Ranking Criteria:
        1. semantic_importance: high > low (e.g. 1.0 > 0.1)
        2. verification_status: 'VERIFIED' > 'INFERRED'
        3. confidence: high > low
        4. updated_at: recent > older
        """
        if not memories:
            return ""

        # Deduplicate memories and skip INFERRED (pending) ones
        seen_keys = set()
        unique_memories = []
        for m in memories:
            if m.verification_status == "INFERRED":
                continue
            m_key = (m.category.lower(), m.subject.lower(), m.predicate.lower(), m.object.lower())
            if m_key not in seen_keys:
                seen_keys.add(m_key)
                unique_memories.append(m)

        # 1. Rank memories
        def rank_key(entry: MemoryEntry):
            importance = getattr(entry, "semantic_importance", 0.5)
            status_score = 1 if entry.verification_status == "VERIFIED" else 0
            confidence = entry.confidence
            updated_at = entry.updated_at or ""
            return (importance, status_score, confidence, updated_at)

        ranked_memories = sorted(unique_memories, key=rank_key, reverse=True)

        # 2. Limit by dynamic memory budget policy
        ranked_memories = ranked_memories[:limit]

        # 3. Format and enforce length budget
        formatted_lines = []
        current_length = 0
        
        for entry in ranked_memories:
            # Render representation into natural sentences
            pred_clean = entry.predicate.lower().replace("_", " ")
            obj = entry.object
            
            if entry.subject.lower() == "user":
                if entry.predicate in ("has_fact", "preferred_style"):
                    # Direct raw text
                    fact_str = obj
                elif obj.lower() == "true":
                    fact_str = f"User {pred_clean}"
                elif obj.lower() == "false":
                    fact_str = f"User does not {pred_clean}"
                elif pred_clean in ("likes", "dislikes", "prefers", "values", "believes", "founded", "works on", "works at", "lives with", "has experience", "interested in"):
                    fact_str = f"User {pred_clean} {obj}"
                else:
                    fact_str = f"User {pred_clean}: {obj}"
            else:
                fact_str = f"{entry.subject} {pred_clean} {obj}"
                
            line = f"- {fact_str}"
            
            # Check length budget
            if current_length + len(line) + 1 > max_chars:
                break
                
            formatted_lines.append(line)
            current_length += len(line) + 1

        if not formatted_lines:
            return ""

        # Build output structure matching isolated context design
        context_block = (
            "\n=== USER PROFILE & LONG-TERM KNOWLEDGE ===\n"
            + "\n".join(formatted_lines)
            + "\n==========================================\n"
        )
        return context_block
