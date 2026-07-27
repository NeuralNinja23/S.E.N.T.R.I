"""
Behavioral State Manager.

Manages the persistence, reinforcement updates, and temporal decay of
procedural behavioral scores in the SQLite database (sentri_memory.db).
"""

import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from app.config import MEMORY_DB_PATH
from app.capability_2.learning.contracts import (
    BehavioralState,
    BehaviorCommand,
    BehaviorTarget,
    BehaviorOperation,
)
from app.services.logger import get_logger

logger = get_logger("behavioral_state")

# ──────────────────────────────────────────────────────────────────────────────
#  DECAY CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────
# Exponential decay half-life: 14400 seconds (4 hours)
DECAY_HALF_LIFE_SECONDS = 14400.0
DECAY_CONSTANT = math.log(2.0) / DECAY_HALF_LIFE_SECONDS

# Reinforcement parameter step sizes
REINFORCE_STEP_SIZE = 0.20  # +0.20 weight per reinforcement command
SHIFT_STEP_SIZE = 0.50      # +0.50 weight for shift command

# Cap reinforcement scores to prevent runaway weights
MAX_SCORE = 3.0
MIN_SCORE = 0.0

# Define defaults and all allowed semantic values
BEHAVIOR_DEFAULTS = {
    BehaviorTarget.CONVERSATION_STYLE: {
        "default": "conversational",
        "values": ["conversational", "minimal", "academic"]
    },
    BehaviorTarget.PLANNING_BEHAVIOR: {
        "default": "balanced",
        "values": ["balanced", "concise", "deep", "interactive"]
    },
    BehaviorTarget.DIALOGUE_POLICY: {
        "default": "cooperative",
        "values": ["cooperative", "assertive"]
    },
    BehaviorTarget.INTERACTION_PREFERENCE: {
        "default": "hybrid",
        "values": ["hybrid", "text_focused", "speech_focused"]
    }
}


class BehavioralStateManager:
    """
    Saves and loads behavioral states in SQLite.
    Applies reinforcement/shift logic and lazy temporal decay.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or MEMORY_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize the behavioral_scores table and seed default values."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS behavioral_scores (
                    target TEXT NOT NULL,
                    value TEXT NOT NULL,
                    score REAL NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (target, value)
                )
                """
            )
            conn.commit()

            # Seed default values if table is empty
            cursor.execute("SELECT COUNT(*) FROM behavioral_scores")
            if cursor.fetchone()[0] == 0:
                logger.info("Seeding default behavioral scores in SQLite database")
                now = datetime.utcnow().isoformat() + "Z"
                for target, info in BEHAVIOR_DEFAULTS.items():
                    default_val = info["default"]
                    for val in info["values"]:
                        # Default value gets 1.0, others start at 0.0
                        score = 1.0 if val == default_val else 0.0
                        cursor.execute(
                            """
                            INSERT INTO behavioral_scores (target, value, score, updated_at)
                            VALUES (?, ?, ?, ?)
                            """,
                            (target.value, val, score, now)
                        )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize behavioral database: {e}")
        finally:
            conn.close()

    def get_state(self) -> BehavioralState:
        """
        Retrieves the active BehavioralState by applying lazy temporal decay
        to all scores and returning the highest-scoring value for each target.
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            
            # 1. Fetch all scores
            cursor.execute("SELECT target, value, score, updated_at FROM behavioral_scores")
            rows = cursor.fetchall()
            
            # Organize rows by target
            scores_by_target = {}
            for row in rows:
                target_str = row["target"]
                try:
                    target = BehaviorTarget(target_str)
                except ValueError:
                    continue
                if target not in scores_by_target:
                    scores_by_target[target] = []
                scores_by_target[target].append(dict(row))

            now_dt = datetime.utcnow()
            now_str = now_dt.isoformat() + "Z"
            
            active_values = {}
            needs_update = False

            # 2. Process decay and find highest scoring value per target
            for target, info in BEHAVIOR_DEFAULTS.items():
                target_scores = scores_by_target.get(target, [])
                default_val = info["default"]
                
                highest_val = default_val
                highest_score = -1.0
                
                for entry in target_scores:
                    val = entry["value"]
                    score = entry["score"]
                    updated_at_str = entry["updated_at"]
                    
                    # Parse timestamp (strip trailing 'Z' if present)
                    try:
                        updated_at = datetime.fromisoformat(updated_at_str.replace("Z", ""))
                        elapsed = (now_dt - updated_at).total_seconds()
                    except Exception:
                        elapsed = 0.0

                    # Apply lazy exponential decay
                    if elapsed > 10.0:  # Only decay if more than 10 seconds elapsed
                        target_default = 1.0 if val == default_val else 0.0
                        score = target_default + (score - target_default) * math.exp(-DECAY_CONSTANT * elapsed)
                        entry["score"] = score
                        entry["updated_at"] = now_str
                        needs_update = True

                    if score > highest_score:
                        highest_score = score
                        highest_val = val
                
                active_values[target] = highest_val

            # 3. If lazy decay was applied, persist the updated scores
            if needs_update:
                for target, entries in scores_by_target.items():
                    for entry in entries:
                        cursor.execute(
                            """
                            UPDATE behavioral_scores
                            SET score = ?, updated_at = ?
                            WHERE target = ? AND value = ?
                            """,
                            (entry["score"], entry["updated_at"], target.value, entry["value"])
                        )
                conn.commit()

            # 4. Assemble and return state object
            return BehavioralState(
                conversation_style=active_values.get(BehaviorTarget.CONVERSATION_STYLE, "conversational"),
                planning_behavior=active_values.get(BehaviorTarget.PLANNING_BEHAVIOR, "balanced"),
                dialogue_policy=active_values.get(BehaviorTarget.DIALOGUE_POLICY, "cooperative"),
                interaction_preference=active_values.get(BehaviorTarget.INTERACTION_PREFERENCE, "hybrid"),
            )

        except Exception as e:
            logger.error(f"Failed to load behavioral state: {e}")
            return BehavioralState()
        finally:
            conn.close()

    def apply_command(self, cmd: BehaviorCommand) -> None:
        """
        Applies a BehaviorCommand reinforcement/shift to the database scores.
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat() + "Z"

            # 1. Fetch current scores for this target to apply decay first
            cursor.execute(
                "SELECT value, score, updated_at FROM behavioral_scores WHERE target = ?",
                (cmd.target.value,)
            )
            rows = cursor.fetchall()
            
            default_val = BEHAVIOR_DEFAULTS[cmd.target]["default"]
            now_dt = datetime.utcnow()

            scores = {}
            for row in rows:
                val = row["value"]
                score = row["score"]
                updated_at_str = row["updated_at"]
                
                try:
                    updated_at = datetime.fromisoformat(updated_at_str.replace("Z", ""))
                    elapsed = (now_dt - updated_at).total_seconds()
                except Exception:
                    elapsed = 0.0

                # Apply decay
                target_default = 1.0 if val == default_val else 0.0
                score = target_default + (score - target_default) * math.exp(-DECAY_CONSTANT * elapsed)
                scores[val] = score

            # 2. Modify score based on command
            if cmd.value not in scores:
                logger.warning(f"Value '{cmd.value}' is not valid for target {cmd.target.value}")
                return

            step = REINFORCE_STEP_SIZE if cmd.operation == BehaviorOperation.REINFORCE else SHIFT_STEP_SIZE
            increment = cmd.confidence * step
            
            # Reinforce: increase target value score
            scores[cmd.value] = min(MAX_SCORE, scores[cmd.value] + increment)

            # Shift: slightly penalize/decay other values to accelerate switch
            if cmd.operation == BehaviorOperation.SHIFT:
                for val in scores:
                    if val != cmd.value:
                        scores[val] = max(MIN_SCORE, scores[val] - (increment * 0.5))

            # 3. Persist the new scores
            for val, score in scores.items():
                cursor.execute(
                    """
                    UPDATE behavioral_scores
                    SET score = ?, updated_at = ?
                    WHERE target = ? AND value = ?
                    """,
                    (score, now, cmd.target.value, val)
                )
            conn.commit()

            logger.info(
                f"Applied BehaviorCommand: target={cmd.target.value}, "
                f"value={cmd.value}, operation={cmd.operation.value}. New score={scores[cmd.value]:.3f}"
            )

        except Exception as e:
            logger.error(f"Failed to apply behavior command: {e}")
        finally:
            conn.close()
