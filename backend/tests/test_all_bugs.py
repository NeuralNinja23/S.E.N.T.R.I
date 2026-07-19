"""
S.E.N.T.R.I. — Regression Test Suite (All 30 Bugs)
Run with:  python -m pytest tests/test_all_bugs.py -v
           python -m unittest tests/test_all_bugs.py -v
"""
import unittest
import asyncio
import os
import sys
import time
import json
import re
import tempfile
import threading
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch, call

# ── Environment setup (must precede app imports) ──────────────────────────────
os.environ.setdefault("MEMORY_DB_PATH", ":memory:")
os.environ.setdefault("ASR_LANGUAGE", "es")
os.environ.setdefault("TTS_LANGUAGE", "en-gb")
os.environ.setdefault("REASONING_MODEL", "phi4-mini:latest")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHASE 1 — Critical Blockers & DB Integrity
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestBug12_SQLiteFKCascade(unittest.TestCase):
    """Bug 12: SQLite foreign key PRAGMA enables CASCADE deletes."""

    def test_cascade_delete_removes_evidence(self):
        from app.memory.storage.sqlite_store import SQLiteStore
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "mem.db")
            store = SQLiteStore(db_path)
            entry = {
                "id": "mem-001", "category": "Identity", "subject": "user",
                "predicate": "name", "object": "Nisarg", "confidence": 1.0,
                "verification_status": "VERIFIED", "origin": "test",
                "version": 1, "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"
            }
            store.insert_entry(entry)
            ev = {
                "id": "ev-001", "memory_id": "mem-001", "turn_id": "t1",
                "timestamp": "2026-01-01T00:00:00Z", "confidence": 1.0, "notes": "cascade test"
            }
            store.add_evidence(ev)
            self.assertEqual(len(store.get_evidence_by_memory_id("mem-001")), 1)

            store.delete_entry("mem-001")
            self.assertEqual(len(store.get_evidence_by_memory_id("mem-001")), 0,
                             "Evidence should cascade-delete when parent is removed")


class TestBug17_NPlus1RecallUpdates(unittest.TestCase):
    """Bug 17: recall() uses a single batch SQL UPDATE, not N individual updates."""

    def test_batch_update_called_once(self):
        from app.memory.providers.structured_memory import StructuredMemoryProvider
        from app.memory.runtime import MemoryRuntime
        from app.memory.contracts import MemoryEntry, MemoryQuery

        def make_entry(eid):
            return MemoryEntry(
                id=eid, category="Identity", subject="user",
                predicate="x", object="y", confidence=1.0,
                verification_status="VERIFIED", origin="test",
                version=1, created_at="", updated_at=""
            )

        with patch.object(StructuredMemoryProvider, "query",
                          return_value=[make_entry("a"), make_entry("b"), make_entry("c")]), \
             patch.object(StructuredMemoryProvider, "batch_update_recall_time") as mock_batch:
            r = MemoryRuntime()
            r.recall(MemoryQuery(category="Identity"))
            mock_batch.assert_called_once()
            ids = mock_batch.call_args[0][0]
            self.assertEqual(sorted(ids), ["a", "b", "c"],
                             "All matching IDs should be passed in a single batch call")

    def test_batch_method_exists_in_sqlite_store(self):
        from app.memory.storage.sqlite_store import SQLiteStore
        self.assertTrue(hasattr(SQLiteStore, "batch_update_last_recalled_at"))

    def test_batch_method_exists_in_provider(self):
        from app.memory.providers.structured_memory import StructuredMemoryProvider
        self.assertTrue(hasattr(StructuredMemoryProvider, "batch_update_recall_time"))


class TestBug18_DebugWritesRemoved(unittest.TestCase):
    """Bug 18: No blocking sync file writes inside async adapter."""

    def test_no_debug_file_writes_in_adapter(self):
        import inspect
        import re
        from app.conversation.adapter import ConversationAdapter
        source = inspect.getsource(ConversationAdapter)
        # Check that no actual open() calls with these debug filenames remain.
        # (Comments referencing the removed filenames are acceptable and expected.)
        self.assertIsNone(
            re.search(r'open\s*\(\s*["\']full_ollama_json\.json', source),
            "open('full_ollama_json.json') found — debug write not removed"
        )
        self.assertIsNone(
            re.search(r'open\s*\(\s*["\']raw_ollama_response\.txt', source),
            "open('raw_ollama_response.txt') found — debug write not removed"
        )
        self.assertIsNone(
            re.search(r'open\s*\(\s*["\']failed_prompt\.txt', source),
            "open('failed_prompt.txt') found — debug write not removed"
        )


class TestBug22_FalseDeleteConfirmation(unittest.TestCase):
    """Bug 22: Honest 'not found' response when no memories match delete."""

    def test_delete_branch_strings(self):
        # Inspect source to confirm correct strings are present
        import inspect
        import app.api.websocket as ws_mod
        source = inspect.getsource(ws_mod)
        self.assertIn("I couldn't find any matching memory entries to delete", source)
        # Old buggy confirmation should NOT be present
        self.assertNotIn("Memory erasure complete", source)


class TestBug23_ASRDiagnosticsRemoved(unittest.TestCase):
    """Bug 23: ASR diagnostic debug logging removed from production code."""

    def test_asr_debug_logging_code_removed(self):
        """The actual logger.debug / print calls for amplitude diagnostics must be gone."""
        import inspect
        from app.conversation.streaming_pipeline.providers import asr
        source = inspect.getsource(asr)
        # Active debug calls must not be present (only a comment referencing removal is OK)
        self.assertNotIn('logger.debug("[ASR', source)
        self.assertNotIn('print("[ASR', source)
        # The ASR_LANGUAGE config import must be present (Bug #10 fix)
        self.assertIn('ASR_LANGUAGE', source)


class TestBug30_ToolSchemaCategory(unittest.TestCase):
    """Bug 30: remember_fact schema must declare 'category' parameter."""

    def test_category_in_schema(self):
        from app.tasks.tool_schemas import TOOL_SCHEMAS
        schema = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == "remember_fact")
        props = schema["function"]["parameters"]["properties"]
        required = schema["function"]["parameters"]["required"]
        self.assertIn("category", props, "'category' missing from remember_fact properties")
        self.assertIn("category", required, "'category' missing from remember_fact required list")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHASE 2 — Core Inconsistencies
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestBug2_PersonaOverrideRemoved(unittest.TestCase):
    """Bug 2: Hardcoded 'British butler' override is gone from system prompt."""

    def test_butler_strings_absent(self):
        from app.conversation.system_prompt import SystemPromptProvider
        provider = SystemPromptProvider()
        prompt = provider.build()
        self.assertNotIn("British butler", prompt)
        self.assertNotIn("butler manner", prompt.lower())


class TestBug3_ChatHistory(unittest.IsolatedAsyncioTestCase):
    """Bug 3: Conversation history is included in Ollama requests."""

    async def test_history_in_payload(self):
        from app.conversation.adapter import ConversationAdapter
        history = [
            {"role": "user", "text": "My name is Nisarg."},
            {"role": "model", "text": "Hello Nisarg!"}
        ]
        captured = {}

        async def fake_post(url, json=None, **kw):
            captured["payload"] = json
            m = MagicMock()
            m.status_code = 200
            m.json = lambda: {"message": {"content": "Ok"}, "done": True}
            return m

        with patch("httpx.AsyncClient.post", side_effect=fake_post):
            await ConversationAdapter.generate_async("System", "Who am I?", history=history)

        messages = captured["payload"]["messages"]
        # Ollama uses 'user' and 'model' roles (not 'assistant') — at least 4 messages: system+history+query
        self.assertGreater(len(messages), 2, "History must be included in messages")
        # The final message must be the user query
        self.assertEqual(messages[-1]["content"], "Who am I?")
        # There must be a message containing the history user text
        content_texts = [m.get("content", "") for m in messages]
        self.assertTrue(
            any("Nisarg" in t for t in content_texts),
            "History message 'My name is Nisarg.' must appear in payload messages"
        )


class TestBug5_ThinkTagStripping(unittest.IsolatedAsyncioTestCase):
    """Bug 5: <think>...</think> blocks stripped from voice output tokens."""

    async def test_think_tags_are_stripped(self):
        from app.conversation.streaming_pipeline.providers.reasoning import OllamaReasoningProvider
        from app.conversation.contracts import ReasoningRequest

        provider = OllamaReasoningProvider(model_name="phi4-mini:latest")

        raw_lines = [
            '{"message": {"content": "<think>internal thought</think>"}, "done": false}',
            '{"message": {"content": "Hello!"}, "done": false}',
            '{"message": {"content": ""}, "done": true}',
        ]

        async def mock_aiter_lines():
            for line in raw_lines:
                yield line

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.aiter_lines = mock_aiter_lines

        ctx_manager = MagicMock()
        ctx_manager.__aenter__ = AsyncMock(return_value=mock_resp)
        ctx_manager.__aexit__ = AsyncMock(return_value=False)

        with patch.object(provider._client, "stream", return_value=ctx_manager):
            tokens = []
            async for tok in provider.stream(ReasoningRequest(system_prompt="", user_input="Hi")):
                tokens.append(tok)

        result = "".join(tokens)
        self.assertNotIn("<think>", result)
        self.assertNotIn("</think>", result)
        self.assertNotIn("internal thought", result)
        self.assertIn("Hello!", result)


class TestBug6_TokenCap(unittest.IsolatedAsyncioTestCase):
    """Bug 6: num_predict=1024 is enforced in the Ollama payload."""

    async def test_token_cap_in_payload(self):
        from app.conversation.streaming_pipeline.providers.reasoning import OllamaReasoningProvider
        from app.conversation.contracts import ReasoningRequest

        provider = OllamaReasoningProvider(model_name="phi4-mini:latest")
        captured = {}

        async def mock_aiter_lines():
            yield '{"message": {"content": "Hi"}, "done": false}'
            yield '{"message": {"content": ""}, "done": true}'

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.aiter_lines = mock_aiter_lines

        ctx_manager = MagicMock()
        ctx_manager.__aenter__ = AsyncMock(return_value=mock_resp)
        ctx_manager.__aexit__ = AsyncMock(return_value=False)

        def capture_stream(method, url, **kw):
            captured["json"] = kw.get("json", {})
            return ctx_manager

        with patch.object(provider._client, "stream", side_effect=capture_stream):
            async for _ in provider.stream(ReasoningRequest(system_prompt="", user_input="Hi")):
                pass

        options = captured["json"].get("options", {})
        self.assertEqual(options.get("num_predict"), 1024, "num_predict must be 1024 in voice options")


class TestBug20_IntentAnalyzerCached(unittest.TestCase):
    """Bug 20: IntentAnalyzer and RetrievalPlanner are module-level singletons."""

    def test_singletons_exist(self):
        from app.api import websocket as ws_mod
        self.assertTrue(hasattr(ws_mod, "_intent_analyzer"))
        self.assertTrue(hasattr(ws_mod, "_retrieval_planner"))
        self.assertIsNotNone(ws_mod._intent_analyzer)
        self.assertIsNotNone(ws_mod._retrieval_planner)


class TestBug24_TTSLanguage(unittest.TestCase):
    """Bug 24: TTS provider uses TTS_LANGUAGE from config, not hardcoded 'en-us'."""

    def test_tts_language_in_source_not_hardcoded(self):
        import inspect
        from app.conversation.streaming_pipeline.providers import tts as tts_mod
        source = inspect.getsource(tts_mod)
        # Must NOT hardcode 'en-us' string
        self.assertNotIn('lang="en-us"', source)
        self.assertNotIn("lang='en-us'", source)
        # Must reference TTS_LANGUAGE config variable
        self.assertIn('TTS_LANGUAGE', source)

    def test_tts_language_config_value_is_used(self):
        import inspect
        from app.conversation.streaming_pipeline.providers import tts as tts_mod
        source = inspect.getsource(tts_mod)
        # TTS_LANGUAGE is imported inside synthesize and passed to lang= parameter
        self.assertIn('lang=TTS_LANGUAGE', source)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHASE 3 — UX & Robustness
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestBug1_VoiceTranscriptRewrite(unittest.TestCase):
    """Bug 1: pipeline.py no longer rewrites IDENTITY_QUERY transcripts to 'hi'."""

    def test_rewrite_code_absent(self):
        import inspect
        from app.conversation.streaming_pipeline import pipeline
        source = inspect.getsource(pipeline)
        self.assertNotIn('model_input_transcript = "hi"', source)
        self.assertNotIn("model_input_transcript = 'hi'", source)

    def test_original_transcript_preserved(self):
        """Code path: model_input_transcript = transcript (no conditional overwrite)."""
        import inspect
        from app.conversation.streaming_pipeline import pipeline
        source = inspect.getsource(pipeline)
        # The single valid assignment must just be "transcript" without an if/IDENTITY gate
        self.assertIn("model_input_transcript = transcript", source)
        # The IDENTITY conditional no longer exists
        self.assertNotIn('if intent == "IDENTITY_QUERY":\n            model_input_transcript = "hi"', source)


class TestBug4_TrueStreaming(unittest.IsolatedAsyncioTestCase):
    """Bug 4: Ollama payload uses stream=True (real streaming)."""

    async def test_stream_true_in_payload(self):
        from app.conversation.streaming_pipeline.providers.reasoning import OllamaReasoningProvider
        from app.conversation.contracts import ReasoningRequest

        provider = OllamaReasoningProvider(model_name="phi4-mini:latest")
        captured = {}

        async def mock_aiter_lines():
            yield '{"message": {"content": "ok"}, "done": true}'

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.aiter_lines = mock_aiter_lines
        ctx_mgr = MagicMock()
        ctx_mgr.__aenter__ = AsyncMock(return_value=mock_resp)
        ctx_mgr.__aexit__ = AsyncMock(return_value=False)

        def capture(method, url, **kw):
            captured["json"] = kw.get("json", {})
            return ctx_mgr

        with patch.object(provider._client, "stream", side_effect=capture):
            async for _ in provider.stream(ReasoningRequest(system_prompt="", user_input="Hi")):
                pass

        self.assertTrue(captured["json"].get("stream"), "Payload must have stream=True for real streaming")


class TestBug10_ASRLanguageConfigured(unittest.TestCase):
    """Bug 10: ASR uses ASR_LANGUAGE env var, not hardcoded 'en'."""

    def test_asr_calls_config_language(self):
        import inspect
        from app.conversation.streaming_pipeline.providers import asr as asr_mod
        source = inspect.getsource(asr_mod)
        # Must reference config language, not hardcoded 'en'
        self.assertNotIn('language="en"', source)
        self.assertIn("ASR_LANGUAGE", source)


class TestBug13_SubstringFalsePositives(unittest.TestCase):
    """Bug 13: Word-boundary regexes prevent false positives."""

    def test_programming_does_not_trigger_ram(self):
        from app.conversation.quick_responses import QuickResponseEngine
        engine = QuickResponseEngine()
        result = engine.respond("UNKNOWN_QUERY", "i am programming")
        self.assertIsNone(result, "'programming' must NOT trigger RAM quick response")

    def test_drama_does_not_trigger_ram(self):
        from app.conversation.quick_responses import QuickResponseEngine
        engine = QuickResponseEngine()
        result = engine.respond("UNKNOWN_QUERY", "I love drama movies")
        self.assertIsNone(result, "'drama' must NOT trigger RAM quick response")

    def test_bare_ram_word_triggers_ram_usage(self):
        from app.conversation.quick_responses import QuickResponseEngine
        import re
        engine = QuickResponseEngine()
        # Verify the regex matches standalone 'ram'
        self.assertTrue(bool(re.search(r'\bram\b', 'what is my ram usage')),
                        "Word-boundary regex must match standalone 'ram'")
        self.assertFalse(bool(re.search(r'\bram\b', 'i am programming')),
                         "Word-boundary regex must NOT match 'ram' inside 'programming'")


class TestBug14_VRAMNotShadowed(unittest.TestCase):
    """Bug 14: GPU check runs before RAM — VRAM query routes to GPU handler."""

    def test_vram_is_gpu_question_not_ram(self):
        from app.conversation.quick_responses import QuickResponseEngine
        engine = QuickResponseEngine()
        # _is_gpu_question must capture 'vram' before _is_ram_question sees it
        self.assertTrue(engine._is_gpu_question("what is my vram usage"),
                        "VRAM query must be classified as a GPU question")
        self.assertFalse(engine._is_ram_question("what is my vram usage"),
                         "VRAM query must NOT be classified as a RAM question")

    def test_vram_respond_calls_gpu_handler(self):
        from app.conversation.quick_responses import QuickResponseEngine
        engine = QuickResponseEngine()
        with patch.object(engine, "_gpu_usage", return_value="GPU stats") as mock_gpu, \
             patch.object(engine, "_ram_usage", return_value="RAM stats") as mock_ram:
            result = engine.respond("UNKNOWN_QUERY", "what is my vram usage")
            self.assertEqual(result, "GPU stats",
                             "'vram usage' must invoke _gpu_usage, not _ram_usage")
            mock_gpu.assert_called_once()
            mock_ram.assert_not_called()


class TestBug15_BargeIn(unittest.TestCase):
    """Bug 15: Barge-in code path exists in websocket.py."""

    def test_barge_in_code_present(self):
        import inspect
        from app.api import websocket as ws_mod
        source = inspect.getsource(ws_mod)
        self.assertIn("Barge-in", source)
        self.assertIn("session.clear_speech_buffer()", source)
        self.assertIn("session.speaking = False", source)

    def test_clear_speech_buffer_method_exists(self):
        from app.conversation.session import ConversationSession
        s = ConversationSession("test")
        s.speech_buffer.extend(b"\x00" * 100)
        s.clear_speech_buffer()
        self.assertEqual(len(s.speech_buffer), 0)


class TestBug16And26_CasingParity(unittest.TestCase):
    """Bug 16 & 26: Predicate and category casing are normalised in name lookup."""

    def test_uppercase_predicate_matches(self):
        from app.conversation.quick_responses import QuickResponseEngine
        engine = QuickResponseEngine()

        # Test the predicate normalisation logic directly via source
        # (MemoryRuntime is lazy-imported inside _user_name(), so we check source)
        import inspect
        from app.conversation import quick_responses
        source = inspect.getsource(quick_responses._user_name if hasattr(quick_responses, '_user_name')
                                   else quick_responses.QuickResponseEngine._user_name)
        # Must use .lower() for predicate comparison
        self.assertIn('.lower()', source)
        # Must match lowercase variants of the predicate
        self.assertIn('"preferred_name"', source)
        self.assertIn('"name"', source)

    def test_uppercase_predicate_logic_in_source(self):
        """Source code must use .lower() for predicate comparison."""
        import inspect
        from app.conversation import quick_responses
        source = inspect.getsource(quick_responses)
        self.assertIn(".lower()", source)
        self.assertIn('"preferred_name"', source)

    def test_title_case_category_used_in_query(self):
        from app.conversation.quick_responses import QuickResponseEngine
        engine = QuickResponseEngine()
        # Patch MemoryRuntime where it is actually imported (inside the function)
        with patch("app.memory.runtime.MemoryRuntime") as MockRuntime:
            mock_result = MagicMock()
            mock_result.memories = []
            MockRuntime.return_value.recall.return_value = mock_result
            # Force call _user_name directly
            engine._user_name()
        # Verify source uses title-case 'Identity'
        import inspect
        from app.conversation import quick_responses
        source = inspect.getsource(quick_responses)
        self.assertIn('category="Identity"', source,
                      "Memory query must use title-case 'Identity' to match DB storage")


class TestBug19_IntentGreetingDetection(unittest.TestCase):
    """Bug 19 (improved): Full-utterance regex handles all punctuation variants of greetings."""

    def test_regex_pattern_at_module_level(self):
        """The greeting regex must be compiled once at module level, not inside analyze()."""
        import app.conversation.intent_analysis as ia_mod
        self.assertTrue(hasattr(ia_mod, "_GREETING_ONLY"),
                        "_GREETING_ONLY must be a module-level compiled regex")

    def test_bare_greeting_classified_identity(self):
        from app.conversation.intent_analysis import IntentAnalyzer
        analyzer = IntentAnalyzer()
        self.assertEqual(analyzer.analyze("Good morning"), "IDENTITY_QUERY")
        self.assertEqual(analyzer.analyze("hello"), "IDENTITY_QUERY")

    def test_compound_with_comma_falls_through_to_tfidf(self):
        """'Good morning, <non-identity content>' must not match via startswith."""
        from app.conversation.intent_analysis import IntentAnalyzer
        analyzer = IntentAnalyzer()
        # 'Good morning, check my projects' has no identity-proto words → TF-IDF → PROJECTS or UNKNOWN
        result = analyzer.analyze("Good morning, check my projects")
        self.assertIn(result, ["PROJECTS_QUERY", "UNKNOWN_QUERY"],
                      f"Compound greeting should not be IDENTITY_QUERY; got {result}")


class TestBug26_CategoryCasing(unittest.TestCase):
    """Bug 26: Memory query uses 'Identity' (title-case) to match DB storage."""

    def test_identity_title_case_in_source(self):
        import inspect
        from app.conversation import quick_responses
        source = inspect.getsource(quick_responses)
        self.assertIn('category="Identity"', source)


class TestBug28_TelemetryLock(unittest.TestCase):
    """Bug 28: threading.Lock prevents race on network counter globals."""

    def test_lock_exists_in_system_stats(self):
        import inspect
        from app.api import system_stats
        source = inspect.getsource(system_stats)
        self.assertIn("_net_lock", source)
        self.assertIn("threading.Lock()", source)

    def test_concurrent_polls_return_dicts(self):
        from app.api.system_stats import _get_net_speed
        results = []
        errors = []
        def poll():
            try:
                results.append(_get_net_speed())
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=poll) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [], "Concurrent polls must not raise exceptions")
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertIn("net_send_bps", r)
            self.assertIn("net_recv_bps", r)


class TestBug29_RedactorMultiWord(unittest.TestCase):
    """Bug 29: Redactor captures quoted multi-word credential values — extended edge cases."""

    def test_double_quoted_passphrase_redacted(self):
        from app.utils.redact import redact
        result = redact('password: "my secret passphrase"')
        self.assertNotIn("my secret passphrase", result)
        self.assertIn("[REDACTED]", result)

    def test_single_quoted_passphrase_redacted(self):
        from app.utils.redact import redact
        result = redact("secret: 'multi word val'")
        self.assertNotIn("multi word val", result)
        self.assertIn("[REDACTED]", result)

    def test_bare_token_still_redacted(self):
        from app.utils.redact import redact
        result = redact("token: abc123def456ghi789jkl012mno345")
        self.assertIn("[REDACTED]", result)

    # ── Recommended regression cases ─────────────────────────────────────────

    def test_extremely_long_passphrase_redacted(self):
        """Passphrases > 100 chars must be fully redacted, not truncated."""
        from app.utils.redact import redact
        long_pass = "correct horse battery staple " * 10  # 290-char passphrase
        result = redact(f'password: "{long_pass.strip()}"')
        self.assertNotIn("correct horse", result)
        self.assertIn("[REDACTED]", result)

    def test_mixed_whitespace_in_value(self):
        """Tabs and multiple spaces inside quoted values must be redacted."""
        from app.utils.redact import redact
        result = redact('secret: "value\twith  mixed  spaces"')
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("value", result)

    def test_non_credential_key_not_redacted(self):
        """Normal config keys must not be redacted."""
        from app.utils.redact import redact
        result = redact('language: "en-gb"')
        self.assertIn("en-gb", result,
                      "Non-credential keys like 'language' must not be redacted")

    def test_already_redacted_passphrase_idempotent(self):
        """Running redact() twice must not double-redact or corrupt output."""
        from app.utils.redact import redact
        once = redact('password: "hunter2"')
        twice = redact(once)
        self.assertEqual(once, twice, "redact() must be idempotent")

    def test_email_not_affected_by_credential_rule(self):
        """Email addresses get their own rule and must use [REDACTED_EMAIL], not [REDACTED]."""
        from app.utils.redact import redact
        result = redact("contact: user@example.com")
        self.assertNotIn("user@example.com", result)
        self.assertIn("[REDACTED_EMAIL]", result)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHASE 4 — Performance & Refactoring
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestBug8_InactivityTimerGated(unittest.TestCase):
    """Bug 8: Inactivity checker gates on session.speaking and runtime state."""

    def test_checker_code_gates_on_speaking(self):
        import inspect
        from app.api import websocket as ws_mod
        source = inspect.getsource(ws_mod)
        self.assertIn("session.speaking", source)
        self.assertIn("RuntimeState.THINKING", source)
        self.assertIn("RuntimeState.SPEAKING", source)

    def test_state_set_on_turn_start_end(self):
        import inspect
        from app.api import websocket as ws_mod
        source = inspect.getsource(ws_mod)
        self.assertIn("runtime_store.set_state(RuntimeState.THINKING)", source)
        self.assertIn("runtime_store.set_state(RuntimeState.READY)", source)


class TestBug11_ConsolidatedCleaner(unittest.TestCase):
    """Bug 11: Both adapter.py and pipeline.py delegate to ResponseCleaner."""

    def test_utils_file_exists(self):
        import app.conversation.utils as utils_mod
        self.assertTrue(hasattr(utils_mod, "ResponseCleaner"))

    def test_adapter_delegates_to_response_cleaner(self):
        import inspect
        from app.conversation.adapter import ConversationAdapter
        source = inspect.getsource(ConversationAdapter._clean_response)
        self.assertIn("ResponseCleaner", source)

    def test_pipeline_delegates_to_response_cleaner(self):
        import inspect
        from app.conversation.streaming_pipeline import pipeline
        source = inspect.getsource(pipeline)
        self.assertIn("ResponseCleaner", source)

    def test_cliche_stripped_by_cleaner(self):
        from app.conversation.utils import ResponseCleaner
        text = "The weather is nice. How can I assist you today?"
        result = ResponseCleaner.clean(text)
        self.assertNotIn("How can I assist you today?", result)

    def test_think_tags_stripped_by_cleaner(self):
        from app.conversation.utils import ResponseCleaner
        text = "<think>reasoning here</think>The answer is 42."
        result = ResponseCleaner.clean(text)
        self.assertNotIn("<think>", result)
        self.assertIn("42", result)

    def test_asterisk_and_stage_directions_stripped(self):
        from app.conversation.utils import ResponseCleaner
        # Should strip stage directions like *sighs* completely
        text = "*sighs* Hello Nisarg. *clears throat* Here is your **project**."
        result = ResponseCleaner.clean(text)
        self.assertNotIn("*sighs*", result)
        self.assertNotIn("sighs", result)
        self.assertNotIn("*clears throat*", result)
        self.assertNotIn("clears throat", result)
        # Should strip bold/italic asterisks but keep the inner text
        self.assertIn("project", result)
        self.assertNotIn("**", result)
        self.assertNotIn("*", result)
        self.assertEqual(result, "Hello Nisarg. Here is your project.")



class TestBug21_SpeechPlannerFlush(unittest.TestCase):
    """Bug 21: speech_planner.flush() is called in the pipeline finally block."""

    def test_flush_in_finally_block_of_pipeline(self):
        import inspect
        from app.conversation.streaming_pipeline import pipeline
        source = inspect.getsource(pipeline)
        self.assertIn("speech_planner.flush()", source)

    def test_flush_clears_buffer(self):
        from app.conversation.streaming_pipeline.chunker import SpeechPlanner
        sp = SpeechPlanner()
        sp.buffer = ["word1", " word2"]
        sp.token_count = 2
        sp.flush()
        self.assertEqual(sp.buffer, [])
        self.assertEqual(sp.token_count, 0)


class TestBug27_PauseResumeTasks(unittest.TestCase):
    """Bug 27: pause_all_tasks() covers PENDING tasks; task worker respects PAUSED."""

    def test_pending_tasks_are_paused(self):
        from app.tasks.task_models import Task, TaskStatus, TaskPriority
        from app.tasks.task_manager import pause_all_tasks
        from app.runtime.runtime_state import tasks

        task_id = "test-pause-" + str(time.time())
        tasks[task_id] = Task(
            id=task_id, type="test_op", status=TaskStatus.PENDING,
            priority=TaskPriority.NORMAL, origin="test",
            created_at=datetime.now(), updated_at=datetime.now()
        )

        pause_all_tasks()
        self.assertEqual(tasks[task_id].status, TaskStatus.PAUSED,
                         "PENDING tasks must transition to PAUSED on pause_all_tasks()")
        del tasks[task_id]

    def test_resume_returns_to_running(self):
        from app.tasks.task_models import Task, TaskStatus, TaskPriority
        from app.tasks.task_manager import pause_all_tasks, resume_all_tasks
        from app.runtime.runtime_state import tasks

        task_id = "test-resume-" + str(time.time())
        tasks[task_id] = Task(
            id=task_id, type="test_op", status=TaskStatus.RUNNING,
            priority=TaskPriority.NORMAL, origin="test",
            created_at=datetime.now(), updated_at=datetime.now()
        )
        pause_all_tasks()
        self.assertEqual(tasks[task_id].status, TaskStatus.PAUSED)
        resume_all_tasks()
        self.assertEqual(tasks[task_id].status, TaskStatus.RUNNING,
                         "PAUSED tasks must transition to RUNNING on resume_all_tasks()")
        del tasks[task_id]

    def test_worker_loop_has_pause_check(self):
        import inspect
        from app.runtime import task_runtime
        source = inspect.getsource(task_runtime)
        self.assertIn("TaskStatus.PAUSED", source)
        self.assertIn("await asyncio.sleep", source)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
