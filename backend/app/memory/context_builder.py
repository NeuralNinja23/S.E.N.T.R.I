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
        Partitioning verified authoritative memories from pending unverified observations.
        """
        if not memories:
            return ""

        # 1. Filter out COUNTRY and STATE from narrow queries (limit < 10) to reduce context pollution
        filtered_memories = []
        for m in memories:
            if limit < 10 and m.category == "Identity" and m.predicate in ("COUNTRY", "STATE"):
                continue
            filtered_memories.append(m)

        # 2. Deduplicate memories
        seen_keys = set()
        unique_memories = []
        for m in filtered_memories:
            m_key = (m.category.lower(), m.subject.lower(), m.predicate.lower(), m.object.lower())
            if m_key not in seen_keys:
                seen_keys.add(m_key)
                unique_memories.append(m)

        # 3. Rank memories
        def rank_key(entry: MemoryEntry):
            importance = getattr(entry, "semantic_importance", 0.5) or 0.5
            status_score = 1 if entry.verification_status == "VERIFIED" else 0
            confidence = entry.confidence or 0.5
            updated_at = entry.updated_at or ""
            return (importance, status_score, confidence, updated_at)

        ranked_memories = sorted(unique_memories, key=rank_key, reverse=True)
        ranked_memories = ranked_memories[:limit]

        # 4. Partition into Verified and Pending
        verified = [m for m in ranked_memories if m.verification_status == "VERIFIED"]
        pending = [m for m in ranked_memories if m.verification_status != "VERIFIED"]

        def generate_output(ver_list, pend_list) -> str:
            lines = []
            if ver_list:
                lines.append("=== VERIFIED LONG-TERM USER PROFILE (Authoritative) ===")
                for m in ver_list:
                    pred_clean = m.predicate.lower().replace("_", " ")
                    conf = m.confidence or 1.0
                    
                    # Convert to natural third-person phrasing to prevent LLM identity confusion
                    if m.subject.lower() == "user":
                        if pred_clean == "name":
                            lines.append(f"- The user's name: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "preferred name":
                            lines.append(f"- The user prefers to be called: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "city":
                            lines.append(f"- The user's city: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "state":
                            lines.append(f"- The user's state: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "country":
                            lines.append(f"- The user's country: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "lives with":
                            lines.append(f"- The user lives with: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "lives independently":
                            lines.append(f"- The user lives independently: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "works at":
                            lines.append(f"- The user works at: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "founded":
                            lines.append(f"- The user founded: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "works on":
                            lines.append(f"- The user works on: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "has experience":
                            lines.append(f"- The user has experience in: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "dislikes":
                            lines.append(f"- The user dislikes: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "prefers":
                            lines.append(f"- The user prefers: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "believes":
                            lines.append(f"- The user believes: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "values":
                            lines.append(f"- The user values: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "interested in":
                            lines.append(f"- The user is interested in: {m.object} (Confidence: {conf:.2f})")
                        else:
                            lines.append(f"- The user {pred_clean}: {m.object} (Confidence: {conf:.2f})")
                    else:
                        lines.append(f"- {m.subject} {pred_clean}: {m.object} (Confidence: {conf:.2f})")
                lines.append("")

            if pend_list:
                lines.append("=== PENDING / UNVERIFIED USER PROFILE OBSERVATIONS ===")
                lines.append("[IMPORTANT: Do NOT use these pending facts to answer queries unless explicitly asked by the user.]")
                for m in pend_list:
                    pred_clean = m.predicate.lower().replace("_", " ")
                    conf = m.confidence or 0.40
                    
                    if m.subject.lower() == "user":
                        if pred_clean == "name":
                            lines.append(f"- The user's name: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "preferred name":
                            lines.append(f"- The user prefers to be called: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "city":
                            lines.append(f"- The user's city: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "state":
                            lines.append(f"- The user's state: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "country":
                            lines.append(f"- The user's country: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "lives with":
                            lines.append(f"- The user lives with: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "lives independently":
                            lines.append(f"- The user lives independently: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "works at":
                            lines.append(f"- The user works at: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "founded":
                            lines.append(f"- The user founded: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "works on":
                            lines.append(f"- The user works on: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "has experience":
                            lines.append(f"- The user has experience in: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "dislikes":
                            lines.append(f"- The user dislikes: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "prefers":
                            lines.append(f"- The user prefers: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "believes":
                            lines.append(f"- The user believes: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "values":
                            lines.append(f"- The user values: {m.object} (Confidence: {conf:.2f})")
                        elif pred_clean == "interested in":
                            lines.append(f"- The user is interested in: {m.object} (Confidence: {conf:.2f})")
                        else:
                            lines.append(f"- The user {pred_clean}: {m.object} (Confidence: {conf:.2f})")
                    else:
                        lines.append(f"- {m.subject} {pred_clean}: {m.object} (Confidence: {conf:.2f})")
                lines.append("")
            return "\n".join(lines).strip()

        # 5. Length Budget Enforcement
        output_str = generate_output(verified, pending)
        while len(output_str) > max_chars and len(ranked_memories) > 1:
            ranked_memories.pop()
            verified = [m for m in ranked_memories if m.verification_status == "VERIFIED"]
            pending = [m for m in ranked_memories if m.verification_status != "VERIFIED"]
            output_str = generate_output(verified, pending)

        return output_str
