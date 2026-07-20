# SENTRI V2 — Conversation Intelligence Domain Architecture (`capability_2`)

*   **Purpose**: Become a better conversational partner.
*   **Domain Question**: *"How should I improve?"*
*   **Responsibility**: Procedural Adaptation (Understanding, Planning, Responding, Reflecting, Learning, Adapting, and updating the Behavioral State).

Capability 2 does not merely generate responses. It continuously evaluates the quality of interactions, extracts procedural learning, maintains a Behavioral State, and applies that learning to improve future conversations. Its objective is not to remember the user; its objective is to become a better conversational partner.

Through the Self-Improving Conversation Loop, Capability 2 reflects on every interaction, learns from conversational feedback, adapts its behavioral state, and continuously improves future conversations.

---

## 🧠 Core Cognitive Principle: The Reflection Split

Every completed interaction produces two independent outputs:

1. **Knowledge (Declarative Facts)**: *"My favorite color is charcoal"* → **Delegated directly to Capability 1**. Capability 2 does not own or store facts.
2. **Behavior (Conversational State)**: *"Stop explaining so much"* → **Retained and handled within Capability 2**. It updates the local Behavioral State.

This split creates a clean contract between the capabilities: if it is a fact, Capability 2 delegates it; if it is behavioral or procedural learning, Capability 2 owns it.

---

## ⚖️ Core Boundary Rules & Delegation Contract

1. **Behavioral State Persistence**: Capability 2 maintains a persistent, mutable **Behavioral State**. Unlike declarative facts (which are verified or invalidated), behavioral states can strengthen with repeated feedback, weaken if unused, decay over time, or be overridden by newer preferences.
2. **Outer Dependency Boundary**: Outer execution planes depend on inner abstractions. Inner layers never depend on outer WebSockets or connection transport layers.

| ✅ Allowed | ❌ Forbidden |
|---|---|
| `Reflection Engine` → delegates facts to `Capability 1` | Storing declarative facts (*"Nisarg founded GenxAI Labz"*) inside Capability 2 |
| `Behavioral State` → guides prompts & planner decisions | Writing to SQLite database directly from Conversation workers |
| `websocket.py` → `process_user_turn()` | `pipeline.py` or `engine.py` references to `WebSocket` objects |

---

## 🎭 The Behavioral State Structure

The **Behavioral State** is an abstract representation of Sentri's execution posture. Underneath the hood, it influences:

* **Conversation Style**: Tone, pacing, verbosity boundaries, and vocabulary adjustments.
* **Planning Strategy**: Selection of routing policies, quick responses, or deep reasoning paths.
* **Dialogue Policies**: Handling of interruptions, barge-in thresholds, and recovery protocols.
* **Interaction Preferences**: Tool selection thresholds and active screen capture intervals.
* **Reflection History & Learning State**: Active reinforcement weights and habituation decay indices.

Whether these states influence prompts, routing rules, or a future fine-tuned model is an internal implementation detail of Capability 2.

---

## 1. Domain Architecture

```
app/api/websocket.py              ← Global WebSocket gateway (connection only)
    │
    ├── process_user_turn()       ┐
    └── process_user_text_turn()  ┘ ← app/capability_2/api/conversation.py
                │
                ▼
        ConversationEngine        ← owns turn routing (voice vs text)
                │
    ┌───────────┴──────────────────────┐
    ▼                                  ▼
ConversationRuntime             IntentAnalyzer (routing/)
(streaming_pipeline/pipeline.py)  RetrievalPlanner (routing/)
    │                             QuickResponseEngine (routing/)
    ├── ASRProvider (asr.py)
    ├── SpeechPlanner/Chunker (chunker.py)
    ├── ReasoningProvider (reasoning.py)
    └── TTSProvider (tts.py)
                │
                ▼
        ProviderRegistry          ← resolves ASR/LLM/TTS by config name
```

```
PromptBuilder (prompts/)
    ├── SystemPromptProvider      ← loads sentri.md system instructions
    └── MemoryProvider            ← fetches context from capability_1
            │
            └── retrieve_memory_context()  ← capability_1/api/memory.py
```

---

## 2. Streaming Pipeline (Decoupled ASR → LLM → TTS)

The pipeline runs three concurrent workers coordinated by `RuntimeSupervisor`:

```
[Audio bytes]
      │
      ▼
ASRWorker           → transcript text     → token_queue
      │
      ▼
ReasoningWorker     → LLM token stream    → phrase_queue  (via SpeechPlanner)
      │
      ▼
TTSWorker           → PCM16 audio chunks  → audio_queue
      │
      ▼
[WebSocket: text + audio streamed to client]
```

Each stage is fully async. Cancellation propagates hierarchically via `TurnContext.cancel_token` (an `asyncio.Event`). When the user barges in, `cancel_token` is set and all three workers drain and exit gracefully.

### RuntimeSupervisor

`RuntimeSupervisor` manages the worker task groups:
- **`reasoning` group**: LLM token generation worker
- **`synthesis` group**: TTS audio synthesis worker

It health-monitors tasks and coordinates graceful shutdown on cancellation or error.

---

## 3. Intent Routing Layer (`routing/`)

Before any LLM call, the user's utterance is classified locally:

```
User utterance
      │
      ▼
IntentAnalyzer.analyze()      ← TF-IDF cosine similarity, sub-ms, fully deterministic
      │                           Returns: IDENTITY_QUERY | CAREER_QUERY | LIFESTYLE_QUERY |
      │                                    PROJECTS_QUERY | GOALS_QUERY | PREFERENCES_QUERY |
      │                                    PROFILE_QUERY | UNKNOWN_QUERY
      ▼
QuickResponseEngine.respond() ← If intent is deterministic (greeting, time, Sentri identity)
      │                           → returns instant response, skips LLM entirely
      │                           → returns None → falls through to LLM
      ▼
RetrievalPlanner.plan()       ← Maps intent → [memory categories] + budget limit
      │
      ▼
retrieve_memory_context()     ← Fetches from capability_1 and formats context block
```

### QuickResponseEngine bypass

For high-frequency, deterministic intents, the LLM is bypassed entirely:

| Trigger | Response |
|---|---|
| Greeting (`hi`, `hello`, etc.) | Dynamic greeting with time-of-day |
| `"What is your name?"` | `"I am Sentri"` (hardcoded, prevents identity confusion) |
| `"What is my name?"` | User's name from memory (deterministic lookup) |
| `"What time is it?"` | Live system clock |
| `"What day is it?"` | Live system date |

### RetrievalPlanner budget policy

| Intent | Categories | Budget (entries) |
|---|---|---|
| `IDENTITY_QUERY` | Identity | 2 |
| `CAREER_QUERY` | Career, Identity | 6 |
| `LIFESTYLE_QUERY` | Lifestyle, Identity | 6 |
| `PROJECTS_QUERY` | Project, Goal | 20 |
| `GOALS_QUERY` | Goal, Fact, Preference | 20 |
| `PREFERENCES_QUERY` | Preference, Fact | 6 |
| `PROFILE_QUERY` | All categories | 60 |
| `UNKNOWN_QUERY` | All categories | 15 |

---

## 4. Provider System (`streaming_pipeline/providers/`)

All inference providers are registered and resolved by `ProviderRegistry` using config keys from `config.py`. No code outside the provider files knows the concrete implementation.

| Provider type | Config key | Current default |
|---|---|---|
| ASR | `ASR_PROVIDER` | `faster_whisper` |
| LLM | `REASONING_PROVIDER` | `ollama` |
| LLM model | `REASONING_MODEL` | `phi4-mini:latest` |
| TTS | `TTS_PROVIDER` | `kokoro` |
| TTS voice | `TTS_SPEAKER_VOICE` | `bm_george` |

Swapping any provider requires only a `.env` change — no code changes.

---

## 5. Core Contracts (`core/contracts.py`)

| Contract | Purpose |
|---|---|
| `TurnContext` | Immutable domain state for one turn: audio bytes, transcript, memory context, system prompt, response |
| `TurnChannels` | Three async queues connecting pipeline workers: `token_queue`, `phrase_queue`, `audio_queue` |
| `ConversationClock` | Nanosecond-precision timestamps for every pipeline stage boundary |
| `VoiceMetrics` | Per-component latency: ASR, LLM, chunker, TTS, end-to-end, TTFT, TTFA |
| `ReasoningRequest` | Input payload to any LLM provider: system prompt, user input, memory, history |
| `ReasoningResponse` | Output payload from any LLM provider: generated text token |
| `AudioChunk` | PCM16 bytes + sample rate + duration for one TTS chunk |
| `ConversationTurn` | Full turn lifecycle record: transcript, memory, request, response, audio chunks, metrics |

---

## 6. Session Lifecycle

A `ConversationSession` (`core/session.py`) tracks one WebSocket connection:

1. **Handshake**: Client connects to `/ws/voice` → `websocket.py` creates session.
2. **Audio accumulation**: PCM bytes accumulate in `session.speech_buffer`.
3. **Text trigger**: Client sends `text_message` → `process_user_text_turn()` called directly.
4. **Voice trigger**: Client sends `turn_complete` → `session.consume_speech_buffer()` → `process_user_turn()` called.
5. **Streaming**: Text tokens and PCM audio chunks stream back over WebSocket concurrently.
6. **Interruption**: Client sends `barge_in` → `cancel_token` set → all workers cancelled → `interrupt` event sent to client.
7. **Disposal**: Connection closes → inactivity watchdog cancelled → WebSocket closed cleanly.

`ConversationSession` owns only: buffer, transcript, history, speaking state.  
It does **not** own: memory retrieval, tool execution, runtime state, or watchdog state.

---

## 7. Events System (`events/`)

`event_bus.py` defines the reactive turn lifecycle events used internally by the pipeline:

| Event | Fired when |
|---|---|
| `SpeechStarted` | ASR begins processing audio bytes |
| `SpeechFinished` | ASR produces the full transcript |
| `TranscriptReady` | Transcript confirmed and passed to reasoning |
| `ReasoningStarted` | LLM begins token generation |
| `TokenGenerated` | Each LLM output token |
| `ChunkReady` | SpeechPlanner emits a TTS-ready phrase chunk |
| `AudioStarted` | TTS begins synthesis |
| `AudioChunkEvent` | Each PCM audio chunk ready to stream |
| `AudioFinished` | Full TTS audio output complete |
| `Interrupted` | Barge-in received mid-turn |
| `Cancelled` | Turn cancelled before completion |
| `Error` | Any pipeline stage failure |

---

## 8. Metrics (`core/metrics.py`)

Per-turn performance tracking:

| Metric | Description |
|---|---|
| **TTFT** | Time to First Token (speech end → first LLM token) |
| **TTFA** | Time to First Audio (speech end → first PCM chunk) |
| **Total Latency** | Full turn round-trip |
| **ASR duration** | Transcription time |
| **LLM duration** | Full generation time |
| **TTS duration** | Full synthesis time |
| **Queue wait times** | Per-stage queue wait from `ConversationClock` |

---

## 9. Capability API (`api/conversation.py`)

The public API surface consumed by `websocket.py`:

| Function | Purpose |
|---|---|
| `process_user_turn(speech_bytes, websocket, session)` | Full voice turn: ASR → intent routing → memory retrieval → LLM → TTS → stream |
| `process_user_text_turn(text_query, websocket, session)` | Text turn: intent routing → memory retrieval → LLM → stream text |

Singletons instantiated at module load (cached for performance):
- `conversation_engine` — `ConversationEngine` instance
- `_intent_analyzer` — `IntentAnalyzer` instance  
- `_retrieval_planner` — `RetrievalPlanner` instance

---

## 10. Future Roadmap

- **Native speech-to-speech**: `MiniOmni2` integration via `InferenceRegistry` — swap into `ProviderRegistry` with no pipeline changes.
- **Streaming VAD**: Voice Activity Detection to auto-trigger turns without a client `turn_complete` signal.
- **Vision grounding**: Screen frame injection per-turn when model supports `"vision"` capability.
- **Tool calling alignment**: Map LLM text output to structured tool call schemas for memory graph updates during voice turns.
- **Multi-provider fallback**: Automatic failover to secondary LLM/TTS provider on timeout.
