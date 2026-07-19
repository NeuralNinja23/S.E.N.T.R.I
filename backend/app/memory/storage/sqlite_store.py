import sqlite3
import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger("sqlite_store")

class SQLiteStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_db()

    def get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")  # Bug #12: enable CASCADE deletes on evidence table
        return conn

    def initialize_db(self):
        """Initializes tables and unique indices in the SQLite database."""
        conn = self.get_conn()
        cursor = conn.cursor()
        
        # Create memory_entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_entries (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                confidence REAL NOT NULL,
                verification_status TEXT NOT NULL,
                origin TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_recalled_at TEXT,
                semantic_importance REAL NOT NULL DEFAULT 0.5
            )
        """)
        
        # Run automatic migration if column does not exist
        cursor.execute("PRAGMA table_info(memory_entries)")
        columns = [col[1] for col in cursor.fetchall()]
        if "semantic_importance" not in columns:
            cursor.execute("ALTER TABLE memory_entries ADD COLUMN semantic_importance REAL NOT NULL DEFAULT 0.5")
            
        # Update existing records with default importance weights
        cursor.execute("UPDATE memory_entries SET semantic_importance = 1.0 WHERE category = 'Identity' AND predicate IN ('NAME', 'PREFERRED_NAME')")
        cursor.execute("UPDATE memory_entries SET semantic_importance = 0.85 WHERE category = 'Identity' AND predicate IN ('CITY', 'STATE', 'COUNTRY')")
        cursor.execute("UPDATE memory_entries SET semantic_importance = 0.9 WHERE category = 'Career'")
        cursor.execute("UPDATE memory_entries SET semantic_importance = 0.9 WHERE category = 'Project'")
        cursor.execute("UPDATE memory_entries SET semantic_importance = 0.9 WHERE category = 'Goal'")
        cursor.execute("UPDATE memory_entries SET semantic_importance = 0.8 WHERE category = 'Preference'")
        cursor.execute("UPDATE memory_entries SET semantic_importance = 0.7 WHERE category = 'Lifestyle'")
        
        # Create composite unique index to enforce logical uniqueness of facts
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_entries_unique_fact
            ON memory_entries (category, subject, predicate, object)
        """)
        
        # Create evidence table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                turn_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                confidence REAL NOT NULL,
                notes TEXT,
                FOREIGN KEY (memory_id) REFERENCES memory_entries (id) ON DELETE CASCADE
            )
        """)
        
        # Create composite unique index on evidence
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_unique_obs
            ON evidence (memory_id, turn_id, timestamp)
        """)
        
        conn.commit()
        conn.close()
 
    def insert_entry(self, entry: Dict[str, Any]) -> str:
        """Inserts a new canonical memory entry."""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO memory_entries (
                id, category, subject, predicate, object, confidence, 
                verification_status, origin, version, created_at, updated_at, last_recalled_at,
                semantic_importance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["id"], entry["category"], entry["subject"], entry["predicate"], entry["object"],
            entry["confidence"], entry["verification_status"], entry["origin"], entry["version"],
            entry["created_at"], entry["updated_at"], entry.get("last_recalled_at"),
            entry.get("semantic_importance", 0.5)
        ))
        conn.commit()
        conn.close()
        return entry["id"]
 
    def update_entry(self, entry: Dict[str, Any]):
        """Updates a canonical memory entry, incrementing version."""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE memory_entries
            SET object = ?, confidence = ?, verification_status = ?, origin = ?, 
                version = ?, updated_at = ?, semantic_importance = ?
            WHERE id = ?
        """, (
            entry["object"], entry["confidence"], entry["verification_status"], entry["origin"],
            entry["version"], entry["updated_at"], entry.get("semantic_importance", 0.5), entry["id"]
        ))
        conn.commit()
        conn.close()

    def delete_entry(self, entry_id: str):
        """Deletes a canonical memory entry and cascaded evidence."""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
        conn.commit()
        conn.close()

    def exists_entry(self, category: str, subject: str, predicate: str, val_object: str) -> Optional[str]:
        """Checks if a triple already exists, returning its ID if found."""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM memory_entries
            WHERE category = ? AND subject = ? AND predicate = ? AND object = ?
        """, (category, subject, predicate, val_object))
        row = cursor.fetchone()
        conn.close()
        return row["id"] if row else None

    def get_entry_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single canonical entry."""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM memory_entries WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def query_entries(
        self, 
        category: Optional[str] = None, 
        subject: Optional[str] = None, 
        predicate: Optional[str] = None, 
        include_inferred: bool = True,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Queries canonical memory entries using optional filters."""
        conn = self.get_conn()
        cursor = conn.cursor()
        
        query = "SELECT * FROM memory_entries WHERE 1=1"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        if subject:
            query += " AND subject = ?"
            params.append(subject)
        if predicate:
            query += " AND predicate = ?"
            params.append(predicate)
        if not include_inferred:
            query += " AND verification_status != 'INFERRED'"
            
        # Sort and Limit matches
        query += " ORDER BY semantic_importance DESC, confidence DESC, updated_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_last_recalled_at(self, entry_id: str, timestamp: str):
        """Updates last_recalled_at timestamp of a memory."""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE memory_entries
            SET last_recalled_at = ?
            WHERE id = ?
        """, (timestamp, entry_id))
        conn.commit()
        conn.close()

    def batch_update_last_recalled_at(self, entry_ids: List[str], timestamp: str):
        """Updates last_recalled_at timestamp for a batch of memories (Bug #17)."""
        if not entry_ids:
            return
        conn = self.get_conn()
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in entry_ids)
        query = f"UPDATE memory_entries SET last_recalled_at = ? WHERE id IN ({placeholders})"
        cursor.execute(query, [timestamp] + entry_ids)
        conn.commit()
        conn.close()

    def add_evidence(self, obs: Dict[str, Any]):
        """Logs a reinforcement observation associated with a canonical memory."""
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO evidence (id, memory_id, turn_id, timestamp, confidence, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (obs["id"], obs["memory_id"], obs["turn_id"], obs["timestamp"], obs["confidence"], obs.get("notes")))
            conn.commit()
        except sqlite3.IntegrityError:
            # Ignore duplicate evidence records matching unique idx_evidence_unique_obs
            pass
        finally:
            conn.close()

    def get_evidence_by_memory_id(self, memory_id: str) -> List[Dict[str, Any]]:
        """Retrieves all evidence logged for a specific canonical memory."""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM evidence WHERE memory_id = ? ORDER BY timestamp DESC", (memory_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
