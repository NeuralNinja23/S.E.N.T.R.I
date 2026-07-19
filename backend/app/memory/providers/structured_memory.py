from typing import List, Optional, Dict, Any
from app.memory.contracts import MemoryEntry, EvidenceEntry, MemoryQuery
from app.memory.storage.sqlite_store import SQLiteStore
from app.config import MEMORY_DB_PATH

class StructuredMemoryProvider:
    """
    StructuredMemoryProvider bridges domain memory contracts with the SQLite storage layer.
    """
    def __init__(self, db_path: str = MEMORY_DB_PATH):
        self.store = SQLiteStore(db_path)

    def _to_entry(self, row: Dict[str, Any]) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"],
            category=row["category"],
            subject=row["subject"],
            predicate=row["predicate"],
            object=row["object"],
            confidence=row["confidence"],
            verification_status=row["verification_status"],
            origin=row["origin"],
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_recalled_at=row.get("last_recalled_at"),
            semantic_importance=row.get("semantic_importance", 0.5)
        )

    def _to_evidence(self, row: Dict[str, Any]) -> EvidenceEntry:
        return EvidenceEntry(
            id=row["id"],
            memory_id=row["memory_id"],
            turn_id=row["turn_id"],
            timestamp=row["timestamp"],
            confidence=row["confidence"],
            notes=row.get("notes")
        )

    def save(self, entry: MemoryEntry) -> str:
        """Saves a new canonical MemoryEntry to database."""
        # Assign dynamic default semantic importances based on domain hierarchy if fallback default 0.5 is used
        importance = entry.semantic_importance
        if importance == 0.5:
            if entry.category == "Identity" and entry.predicate in ("NAME", "PREFERRED_NAME"):
                importance = 1.0
            elif entry.category == "Identity" and entry.predicate in ("CITY", "STATE", "COUNTRY"):
                importance = 0.85
            elif entry.category == "Career":
                importance = 0.9
            elif entry.category == "Project":
                importance = 0.9
            elif entry.category == "Goal":
                importance = 0.9
            elif entry.category == "Preference":
                importance = 0.8
            elif entry.category == "Lifestyle":
                importance = 0.7
                
        data = {
            "id": entry.id,
            "category": entry.category,
            "subject": entry.subject,
            "predicate": entry.predicate,
            "object": entry.object,
            "confidence": entry.confidence,
            "verification_status": entry.verification_status,
            "origin": entry.origin,
            "version": entry.version,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
            "last_recalled_at": entry.last_recalled_at,
            "semantic_importance": importance
        }
        return self.store.insert_entry(data)

    def update(self, entry: MemoryEntry):
        """Updates an existing MemoryEntry."""
        importance = entry.semantic_importance
        if importance == 0.5:
            if entry.category == "Identity" and entry.predicate in ("NAME", "PREFERRED_NAME"):
                importance = 1.0
            elif entry.category == "Identity" and entry.predicate in ("CITY", "STATE", "COUNTRY"):
                importance = 0.85
            elif entry.category == "Career":
                importance = 0.9
            elif entry.category == "Project":
                importance = 0.9
            elif entry.category == "Goal":
                importance = 0.9
            elif entry.category == "Preference":
                importance = 0.8
            elif entry.category == "Lifestyle":
                importance = 0.7
                
        data = {
            "id": entry.id,
            "object": entry.object,
            "confidence": entry.confidence,
            "verification_status": entry.verification_status,
            "origin": entry.origin,
            "version": entry.version,
            "updated_at": entry.updated_at,
            "semantic_importance": importance
        }
        self.store.update_entry(data)

    def delete(self, entry_id: str):
        """Deletes a MemoryEntry by ID."""
        self.store.delete_entry(entry_id)

    def exists(self, category: str, subject: str, predicate: str, object_val: str) -> Optional[str]:
        """Checks if a matching fact already exists, returning its ID."""
        return self.store.exists_entry(category, subject, predicate, object_val)

    def get_by_id(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieves a single MemoryEntry by its ID."""
        row = self.store.get_entry_by_id(entry_id)
        return self._to_entry(row) if row else None

    def query(self, query: MemoryQuery) -> List[MemoryEntry]:
        """Queries memories matching search query criteria."""
        rows = self.store.query_entries(
            category=query.category,
            subject=query.subject,
            predicate=query.predicate,
            include_inferred=query.include_inferred,
            limit=query.limit
        )
        return [self._to_entry(row) for row in rows]

    def update_recall_time(self, entry_id: str, timestamp: str):
        """Updates last_recalled_at timestamp."""
        self.store.update_last_recalled_at(entry_id, timestamp)

    def batch_update_recall_time(self, entry_ids: List[str], timestamp: str):
        """Updates last_recalled_at timestamp for a batch of entries (Bug #17)."""
        self.store.batch_update_last_recalled_at(entry_ids, timestamp)

    def record_evidence(self, obs: EvidenceEntry):
        """Records a reinforcement observation."""
        data = {
            "id": obs.id,
            "memory_id": obs.memory_id,
            "turn_id": obs.turn_id,
            "timestamp": obs.timestamp,
            "confidence": obs.confidence,
            "notes": obs.notes
        }
        self.store.add_evidence(data)

    def get_evidence(self, memory_id: str) -> List[EvidenceEntry]:
        """Retrieves evidence lists associated with a memory."""
        rows = self.store.get_evidence_by_memory_id(memory_id)
        return [self._to_evidence(row) for row in rows]
