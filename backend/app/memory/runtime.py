import uuid
import logging
from datetime import datetime
from typing import List, Optional

from app.memory.contracts import MemoryEntry, EvidenceEntry, MemoryQuery, MemoryResult
from app.memory.registry import provider_registry

logger = logging.getLogger("memory_runtime")

class MemoryRuntime:
    """
    MemoryRuntime is the primary developer interface for memory CRUD and query capabilities,
    decoupled from storage implementation via structured providers.
    """
    def __init__(self, provider_name: str = "structured_memory"):
        self.provider = provider_registry.get_provider(provider_name)

    def _now_iso(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

    def remember(self, entry: MemoryEntry, turn_id: str) -> str:
        """
        Stores a semantic memory entry using the Pending -> Verified Lifecycle.
        - Checks for exact matching tuples and records evidence reinforcements.
        - Promotes INFERRED candidate entries to VERIFIED if reinforcements >= 3, deprecating old values.
        - Stores candidate updates/contradictions as separate INFERRED entries.
        """
        now = self._now_iso()
        
        # Check if the exact triple exists
        existing_id = self.exists(entry.category, entry.subject, entry.predicate, entry.object)
        
        if existing_id:
            logger.info(f"Fact '{entry.subject} {entry.predicate} {entry.object}' already exists (ID: {existing_id}). Recording evidence.")
            existing_entry = self.provider.get_by_id(existing_id)
            if existing_entry:
                existing_entry.updated_at = now
                
                # Check for promotion if the entry is currently INFERRED
                if existing_entry.verification_status == "INFERRED":
                    evidences = self.provider.get_evidence(existing_id)
                    evidence_count = len(evidences) + 1  # includes current turn
                    if evidence_count >= 3:
                        logger.info(f"Promoting memory {existing_id} to VERIFIED due to reinforcement ({evidence_count} observations).")
                        existing_entry.verification_status = "VERIFIED"
                        existing_entry.confidence = 1.0
                        
                        # Archive/delete any older VERIFIED fact with the same subject/predicate/category
                        other_verified = self.provider.query(MemoryQuery(
                            category=existing_entry.category,
                            subject=existing_entry.subject,
                            predicate=existing_entry.predicate,
                            include_inferred=False
                        ))
                        for ov in other_verified:
                            if ov.id != existing_id:
                                logger.info(f"Deleting older verified fact (ID: {ov.id}, Object: {ov.object}) due to promotion of new fact.")
                                self.provider.delete(ov.id)
                                
                self.provider.update(existing_entry)
            
            # Record reinforcement observation
            obs = EvidenceEntry(
                id=uuid.uuid4().hex,
                memory_id=existing_id,
                turn_id=turn_id,
                timestamp=now,
                confidence=entry.confidence,
                notes=f"Reinforced observation via turn {turn_id}."
            )
            self.provider.record_evidence(obs)
            return existing_id
            
        # Check if a fact with same subject/predicate/category exists but has a different object
        candidates = self.provider.query(MemoryQuery(
            category=entry.category,
            subject=entry.subject,
            predicate=entry.predicate,
            include_inferred=True,
            limit=50
        ))
        
        should_upsert_overwrite = entry.category in ("Identity", "Career") and len(candidates) > 0
        
        if should_upsert_overwrite:
            # Instead of overwriting the VERIFIED record, we insert the new object value
            # as an INFERRED (Pending) fact.
            logger.info(f"New candidate value for {entry.category}/{entry.subject}/{entry.predicate}: {entry.object}. Storing as PENDING (INFERRED).")
            
            memory_id = entry.id if entry.id else uuid.uuid4().hex
            new_entry = MemoryEntry(
                id=memory_id,
                category=entry.category,
                subject=entry.subject,
                predicate=entry.predicate,
                object=entry.object,
                confidence=0.4, # Low confidence for new inferred candidate
                verification_status="INFERRED",
                origin=entry.origin,
                version=1,
                created_at=now,
                updated_at=now,
                semantic_importance=entry.semantic_importance
            )
            self.provider.save(new_entry)
            
            obs = EvidenceEntry(
                id=uuid.uuid4().hex,
                memory_id=memory_id,
                turn_id=turn_id,
                timestamp=now,
                confidence=entry.confidence,
                notes=f"Initial pending observation via turn {turn_id}."
            )
            self.provider.record_evidence(obs)
            return memory_id
            
        # Else, create a new memory entry
        memory_id = entry.id if entry.id else uuid.uuid4().hex
        new_entry = MemoryEntry(
            id=memory_id,
            category=entry.category,
            subject=entry.subject,
            predicate=entry.predicate,
            object=entry.object,
            confidence=entry.confidence,
            verification_status=entry.verification_status,
            origin=entry.origin,
            version=1,
            created_at=now,
            updated_at=now,
            semantic_importance=entry.semantic_importance
        )
        self.provider.save(new_entry)
        
        # Log initial evidence
        obs = EvidenceEntry(
            id=uuid.uuid4().hex,
            memory_id=memory_id,
            turn_id=turn_id,
            timestamp=now,
            confidence=entry.confidence,
            notes=f"Initial observation via turn {turn_id}."
        )
        self.provider.record_evidence(obs)
        return memory_id

    def recall(self, query: MemoryQuery) -> MemoryResult:
        """
        Queries and returns memory records matching search parameters.
        Updates last_recalled_at timestamp for all matched entries.
        """
        memories = self.provider.query(query)
        if memories:
            now = self._now_iso()
            entry_ids = [entry.id for entry in memories]
            self.provider.batch_update_recall_time(entry_ids, now)
            for entry in memories:
                entry.last_recalled_at = now
        return MemoryResult(memories=memories, count=len(memories))

    def exists(self, category: str, subject: str, predicate: str, object_val: str) -> Optional[str]:
        """Checks if a specific triple already exists, returning its ID."""
        return self.provider.exists(category, subject, predicate, object_val)

    def merge(self, target_id: str, source_id: str):
        """Merges observations from source memory ID into target memory ID, deleting source."""
        evidence_records = self.provider.get_evidence(source_id)
        for obs in evidence_records:
            # Change memory reference
            obs.memory_id = target_id
            self.provider.record_evidence(obs)
        # Delete old canonical entry
        self.provider.delete(source_id)

    def update(self, entry: MemoryEntry):
        """Updates an entry directly."""
        entry.updated_at = self._now_iso()
        self.provider.update(entry)

    def delete(self, entry_id: str):
        """Deletes a memory entry."""
        self.provider.delete(entry_id)

    def list_memories(self, limit: int = 100) -> List[MemoryEntry]:
        """Lists all stored canonical memories."""
        query = MemoryQuery(limit=limit)
        return self.provider.query(query)
