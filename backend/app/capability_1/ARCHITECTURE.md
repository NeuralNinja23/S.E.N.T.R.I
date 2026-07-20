# SENTRI V2 — Persistent Memory Domain Architecture

This document defines the architecture of the persistent memory subsystem in SENTRI V2 (`capability_1`), covering the storage model, retrieval contract, verification lifecycle, and context injection pipeline.

---

## ⚖️ Core Architecture Rule

> **Memory is read-only from the conversation layer. Only the memory domain owns writes.**

This is the governing rule for every change to the memory domain.

| ✅ Allowed | ❌ Forbidden |
|---|---|
| `conversation.py` → `retrieve_memory_context()` | `conversation.py` → `sqlite_store.py` directly |
| `memory.py` → `MemoryRuntime.remember()` | `websocket.py` → `MemoryEntry` construction |
| `MemoryRuntime` → `StructuredMemoryProvider` | `prompt_builder.py` → `MemoryRuntime` directly |

The only places that should write to memory:
- `capability_1/api/memory.py` — erasure and retrieval API
- `capability_1/core/runtime.py` — `remember()`, `delete()`, `recall()`
- `Sentri/tools/memory_tools.py` — tool-calling write path

Everything else reads memory exclusively through `retrieve_memory_context()` or `MemoryContextBuilder.build_context()`.

---

## 1. Domain Architecture

```
API (memory.py / websocket.py)
    │
    ▼
MemoryRuntime                ← owns all read/write operations
    │
    ├─► StructuredMemoryProvider  ← query planner + verification gating
    │       │
    │       ▼
    │   SQLiteMemoryStore         ← persistent graph store (sentri_memory.db)
    │
    └─► MemoryRegistry            ← provider resolution by name

MemoryContextBuilder         ← formats retrieved memories into prompt context
    │
    └─► capability_2/prompts/memory_provider.py  ← injects context into prompt
```

```
RetrievalPlanner  (capability_2/routing)
    │
    └── MemoryQuery(category, subject, limit, include_inferred)
            │
            ▼
        MemoryRuntime.recall()
            │
            ▼
        MemoryContextBuilder.build_context()
```

---

## 2. Memory Entry Schema

Each fact stored in `sentri_memory.db` is a **typed graph triple**:

```python
MemoryEntry(
    id                  # UUID — stable identifier for deletion targeting
    category            # "Identity" | "Career" | "Lifestyle" | "Preference" | ...
    subject             # "user" (always, for now)
    predicate           # "NAME" | "CITY" | "EMPLOYER" | "FAVORITE_COLOR" | ...
    object              # The fact value — "Nisarg" | "Ahmedabad" | "Anti Noob Media"
    confidence          # 0.0–1.0 — used to gate retrieval under uncertainty
    verification_status # "VERIFIED" | "UNVERIFIED" | "PENDING" | "RETRACTED"
    origin              # "USER_EXPLICIT" | "INFERRED" | "TOOL"
)
```

---

## 3. Verification Lifecycle

Facts pass through a verification state machine before being served to the prompt:

```
USER_EXPLICIT → VERIFIED        (immediate — user stated it directly)
INFERRED      → PENDING         (requires corroboration before VERIFIED)
PENDING       → VERIFIED        (confidence threshold crossed)
PENDING       → RETRACTED       (contradicted by new fact)
VERIFIED      → RETRACTED       (user explicitly forgets or corrects)
```

Only `VERIFIED` entries are included in context by default.
`include_inferred=True` on a `MemoryQuery` also includes `PENDING` entries.

---

## 4. Retrieval Contract

Defined in [`core/contracts.py`](file:///c:/Users/JARVIS/Desktop/SENTRI/backend/app/capability_1/core/contracts.py):

- **`MemoryQuery`**: Specifies `category`, `subject`, `limit`, `include_inferred`. The only object crossing the boundary between conversation and memory layers.
- **`MemoryResult`**: Wraps a list of `MemoryEntry` objects returned from `recall()`.
- **`MemoryRuntime`**: The single public façade. All reads go through `recall()`. All writes go through `remember()` and `delete()`.

---

## 5. Context Injection Pipeline

```
1. IntentAnalyzer      → classifies query intent (Identity? Career? Memory?)
2. RetrievalPlanner    → maps intent → [categories] + budget (max entries)
3. MemoryRuntime       → executes MemoryQuery per category
4. MemoryContextBuilder→ formats entries → markdown context block
5. PromptBuilder       → injects context block into system prompt
6. LLM                 → reasons over grounded context
```

`MemoryContextBuilder.build_context()` enforces:
- `max_chars` — hard character budget per turn
- `limit` — max number of entries
- Third-person phrasing (`"The user's name is Nisarg"`) to prevent identity confusion

---

## 6. Memory API Surface

Defined in [`api/memory.py`](file:///c:/Users/JARVIS/Desktop/SENTRI/backend/app/capability_1/api/memory.py):

| Function | Purpose |
|---|---|
| `handle_memory_erasure(text_query)` | Fuzzy-matches and deletes entries matching the user's forget command |
| `retrieve_memory_context(categories, budget)` | Returns a formatted context block for the given categories |

Defined in [`api/upload.py`](file:///c:/Users/JARVIS/Desktop/SENTRI/backend/app/capability_1/api/upload.py):

| Function | Purpose |
|---|---|
| `upload_document(file)` | Parses and stores document text in-memory for context injection |
| `get_all_documents_text_context()` | Returns combined document text for prompt injection |
| `list_documents()` / `delete_document()` / `clear_documents()` | Document management |

---

## 7. Storage

[`storage/sqlite_store.py`](file:///c:/Users/JARVIS/Desktop/SENTRI/backend/app/capability_1/storage/sqlite_store.py) wraps `sentri_memory.db`:

- Single SQLite file at `Sentri/storage/sentri_memory.db`
- Schema: `memory_entries` table — one row per `MemoryEntry`
- All writes are atomic; concurrent reads are safe via WAL mode
- Deletion is hard-delete — no soft-delete or tombstoning

---

## 8. Provider Independence

[`providers/structured_memory.py`](file:///c:/Users/JARVIS/Desktop/SENTRI/backend/app/capability_1/providers/structured_memory.py) implements the `IMemoryProvider` interface.

Adding a new storage backend (e.g., ChromaDB vector store, Neo4j graph) requires only:
1. Implementing `IMemoryProvider`
2. Registering it in `MemoryRegistry`
3. Setting the provider name in `config.py`

No other code changes needed — `MemoryRuntime` resolves the provider by interface.

---

## 9. Future Roadmap

- **Inferred memory**: Passive extraction of facts from conversation history without explicit user instruction.
- **Confidence decay**: Time-based confidence reduction for facts not reinforced over long periods.
- **Vector search**: Semantic similarity retrieval via `utils/vector_store.py` for open-ended queries.
- **Cross-session working memory**: Promote high-confidence working-memory facts to persistent storage automatically.
