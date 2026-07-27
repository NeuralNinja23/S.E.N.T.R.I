"""
Thread-safe Telemetry Collector and Instrumentation Engine for SENTRI.
"""
import time
import threading
import logging
from typing import Dict, List, Any

logger = logging.getLogger("telemetry")

class TelemetryCollector:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TelemetryCollector, cls).__new__(cls)
                cls._instance._init_collector()
            return cls._instance

    def _init_collector(self):
        self.lock = threading.Lock()
        self.metrics: Dict[str, Any] = {
            # Durations lists to calculate avg/max
            "sqlite_write_times": [],
            "memory_retrieval_times": [],
            "prompt_build_times": [],
            "context_builder_times": [],
            "reflection_durations": [],
            "behavior_adapter_durations": [],
            
            # Context size telemetry
            "working_memory_sizes": [],
            "retrieved_memory_counts": [],
            "token_counts": [],
            "prompt_sizes": [],
            
            # Queue sizes
            "token_queue_length": 0,
            "phrase_queue_length": 0,
            "audio_queue_length": 0,
            "reflection_queue_length": 0,
        }

    def record_duration(self, key: str, duration_ms: float):
        with self.lock:
            if key in self.metrics and isinstance(self.metrics[key], list):
                self.metrics[key].append(duration_ms)
                if len(self.metrics[key]) > 1000:
                    self.metrics[key].pop(0)

    def record_value(self, key: str, val: int):
        with self.lock:
            if key in self.metrics and isinstance(self.metrics[key], list):
                self.metrics[key].append(val)
                if len(self.metrics[key]) > 1000:
                    self.metrics[key].pop(0)

    def set_queue_length(self, queue_name: str, length: int):
        with self.lock:
            key = f"{queue_name}_queue_length"
            if key in self.metrics:
                self.metrics[key] = length

    def increment_queue(self, queue_name: str):
        with self.lock:
            key = f"{queue_name}_queue_length"
            if key in self.metrics:
                self.metrics[key] += 1

    def decrement_queue(self, queue_name: str):
        with self.lock:
            key = f"{queue_name}_queue_length"
            if key in self.metrics and self.metrics[key] > 0:
                self.metrics[key] -= 1

    def get_telemetry_dict(self) -> Dict[str, Any]:
        with self.lock:
            res = {}
            for k, v in self.metrics.items():
                if isinstance(v, list):
                    if v:
                        res[f"{k}_avg"] = round(sum(v) / len(v), 2)
                        res[f"{k}_max"] = round(max(v), 2)
                    else:
                        res[f"{k}_avg"] = 0.0
                        res[f"{k}_max"] = 0.0
                else:
                    res[k] = v
            return res

# Global Singleton
telemetry_collector = TelemetryCollector()

def instrument_system():
    """Dynamically patches key methods to record internal telemetry without altering core code."""
    logger.info("Initializing dynamic system instrumentation...")

    # 1. Instrument SQLiteStore (Capability 1)
    try:
        from app.capability_1.storage.sqlite_store import SQLiteStore
        
        # SQLite writes
        orig_insert = SQLiteStore.insert_entry
        def wrapped_insert(self, *args, **kwargs):
            t0 = time.time()
            res = orig_insert(self, *args, **kwargs)
            t1 = time.time()
            telemetry_collector.record_duration("sqlite_write_times", (t1 - t0) * 1000)
            return res
        SQLiteStore.insert_entry = wrapped_insert

        orig_update = SQLiteStore.update_entry
        def wrapped_update(self, *args, **kwargs):
            t0 = time.time()
            res = orig_update(self, *args, **kwargs)
            t1 = time.time()
            telemetry_collector.record_duration("sqlite_write_times", (t1 - t0) * 1000)
            return res
        SQLiteStore.update_entry = wrapped_update

        orig_delete = SQLiteStore.delete_entry
        def wrapped_delete(self, *args, **kwargs):
            t0 = time.time()
            res = orig_delete(self, *args, **kwargs)
            t1 = time.time()
            telemetry_collector.record_duration("sqlite_write_times", (t1 - t0) * 1000)
            return res
        SQLiteStore.delete_entry = wrapped_delete

        # SQLite retrievals
        orig_query = SQLiteStore.query_entries
        def wrapped_query(self, *args, **kwargs):
            t0 = time.time()
            res = orig_query(self, *args, **kwargs)
            t1 = time.time()
            telemetry_collector.record_duration("memory_retrieval_times", (t1 - t0) * 1000)
            telemetry_collector.record_value("retrieved_memory_counts", len(res))
            return res
        SQLiteStore.query_entries = wrapped_query

        orig_get_by_id = SQLiteStore.get_entry_by_id
        def wrapped_get_by_id(self, *args, **kwargs):
            t0 = time.time()
            res = orig_get_by_id(self, *args, **kwargs)
            t1 = time.time()
            telemetry_collector.record_duration("memory_retrieval_times", (t1 - t0) * 1000)
            return res
        SQLiteStore.get_entry_by_id = wrapped_get_by_id

        logger.info("  SQLiteStore telemetry instrumented.")
    except Exception as e:
        logger.warning(f"  Failed to patch SQLiteStore: {e}")

    # 2. Instrument BehavioralStateManager (Capability 2)
    try:
        from app.capability_2.learning.behavior.state import BehavioralStateManager
        
        orig_apply_command = BehavioralStateManager.apply_command
        def wrapped_apply_command(self, *args, **kwargs):
            t0 = time.time()
            res = orig_apply_command(self, *args, **kwargs)
            t1 = time.time()
            telemetry_collector.record_duration("sqlite_write_times", (t1 - t0) * 1000)
            return res
        BehavioralStateManager.apply_command = wrapped_apply_command

        orig_get_state = BehavioralStateManager.get_state
        def wrapped_get_state(self):
            # This can also execute database reads & lazy decay writes
            t0 = time.time()
            res = orig_get_state(self)
            t1 = time.time()
            # If database operations took significant time, count as read time
            telemetry_collector.record_duration("memory_retrieval_times", (t1 - t0) * 1000)
            return res
        BehavioralStateManager.get_state = wrapped_get_state

        logger.info("  BehavioralStateManager telemetry instrumented.")
    except Exception as e:
        logger.warning(f"  Failed to patch BehavioralStateManager: {e}")

    # 3. Instrument SystemPromptProvider (Capability 2)
    try:
        from app.capability_2.prompts.system_prompt import SystemPromptProvider
        orig_build_prompt = SystemPromptProvider.build
        def wrapped_build_prompt(self, *args, **kwargs):
            t0 = time.time()
            res = orig_build_prompt(self, *args, **kwargs)
            t1 = time.time()
            telemetry_collector.record_duration("prompt_build_times", (t1 - t0) * 1000)
            telemetry_collector.record_value("prompt_sizes", len(res))
            return res
        SystemPromptProvider.build = wrapped_build_prompt
        logger.info("  SystemPromptProvider telemetry instrumented.")
    except Exception as e:
        logger.warning(f"  Failed to patch SystemPromptProvider: {e}")

    # 4. Instrument MemoryContextBuilder (Capability 1)
    try:
        from app.capability_1.core.context_builder import MemoryContextBuilder
        orig_build_context = MemoryContextBuilder.build_context
        @staticmethod
        def wrapped_build_context(*args, **kwargs):
            t0 = time.time()
            res = orig_build_context(*args, **kwargs)
            t1 = time.time()
            telemetry_collector.record_duration("context_builder_times", (t1 - t0) * 1000)
            # Record length of context string
            telemetry_collector.record_value("working_memory_sizes", len(res))
            return res
        MemoryContextBuilder.build_context = wrapped_build_context
        logger.info("  MemoryContextBuilder telemetry instrumented.")
    except Exception as e:
        logger.warning(f"  Failed to patch MemoryContextBuilder: {e}")

    # 5. Instrument ReflectionEngine & LearningController (Capability 2)
    try:
        from app.capability_2.learning.reflection.engine import ReflectionEngine
        orig_reflect_run = ReflectionEngine.run
        async def wrapped_reflect_run(self, *args, **kwargs):
            t0 = time.time()
            res = await orig_reflect_run(self, *args, **kwargs)
            t1 = time.time()
            telemetry_collector.record_duration("reflection_durations", (t1 - t0) * 1000)
            return res
        ReflectionEngine.run = wrapped_reflect_run

        from app.capability_2.learning.controller import LearningController
        orig_post_turn = LearningController.process_post_turn
        async def wrapped_post_turn(self, *args, **kwargs):
            telemetry_collector.increment_queue("reflection")
            try:
                res = await orig_post_turn(self, *args, **kwargs)
                return res
            finally:
                telemetry_collector.decrement_queue("reflection")
        LearningController.process_post_turn = wrapped_post_turn

        logger.info("  ReflectionEngine telemetry instrumented.")
    except Exception as e:
        logger.warning(f"  Failed to patch ReflectionEngine: {e}")

    # 6. Instrument BehavioralAdapter (Capability 2)
    try:
        from app.capability_2.learning.adaptation.adapter import BehavioralAdapter
        
        orig_adapt_prompt = BehavioralAdapter.adapt_prompt
        @classmethod
        def wrapped_adapt_prompt(cls, *args, **kwargs):
            t0 = time.time()
            res = orig_adapt_prompt(*args, **kwargs)
            t1 = time.time()
            telemetry_collector.record_duration("behavior_adapter_durations", (t1 - t0) * 1000)
            return res
        BehavioralAdapter.adapt_prompt = wrapped_adapt_prompt

        orig_adapt_budget = BehavioralAdapter.adapt_planning_budget
        @classmethod
        def wrapped_adapt_budget(cls, *args, **kwargs):
            t0 = time.time()
            res = orig_adapt_budget(*args, **kwargs)
            t1 = time.time()
            telemetry_collector.record_duration("behavior_adapter_durations", (t1 - t0) * 1000)
            return res
        BehavioralAdapter.adapt_planning_budget = wrapped_adapt_budget

        logger.info("  BehavioralAdapter telemetry instrumented.")
    except Exception as e:
        logger.warning(f"  Failed to patch BehavioralAdapter: {e}")

    # 7. Instrument TurnChannels (Capability 2 voice queue monitoring)
    try:
        from app.capability_2.core.contracts import TurnChannels
        import asyncio
        orig_channels_init = TurnChannels.__init__
        def wrapped_channels_init(self, *args, **kwargs):
            orig_channels_init(self, *args, **kwargs)
            
            async def queue_monitor():
                try:
                    while True:
                        telemetry_collector.set_queue_length("token", self.token_queue.qsize())
                        telemetry_collector.set_queue_length("phrase", self.phrase_queue.qsize())
                        telemetry_collector.set_queue_length("audio", self.audio_queue.qsize())
                        await asyncio.sleep(0.05)
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
            try:
                loop = asyncio.get_running_loop()
                self._monitor_task = loop.create_task(queue_monitor())
            except Exception:
                pass
        TurnChannels.__init__ = wrapped_channels_init
        logger.info("  TurnChannels telemetry instrumented.")
    except Exception as e:
        logger.warning(f"  Failed to patch TurnChannels: {e}")
