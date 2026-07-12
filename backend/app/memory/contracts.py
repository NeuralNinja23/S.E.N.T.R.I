from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class MemoryEntry:
    id: str
    category: str
    subject: str
    predicate: str
    object: str
    confidence: float
    verification_status: str  # "VERIFIED" or "INFERRED"
    origin: str  # "USER_EXPLICIT", "USER_CORRECTED", "SYSTEM_IMPORTED", "MANUAL", "AUTO_EXTRACTED"
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    last_recalled_at: Optional[str] = None
    semantic_importance: float = 0.5

@dataclass
class EvidenceEntry:
    id: str
    memory_id: str
    turn_id: str
    timestamp: str
    confidence: float
    notes: Optional[str] = None

@dataclass
class MemoryQuery:
    category: Optional[str] = None
    subject: Optional[str] = None
    predicate: Optional[str] = None
    limit: int = 10
    include_inferred: bool = True

@dataclass
class MemoryResult:
    memories: List[MemoryEntry]
    count: int
