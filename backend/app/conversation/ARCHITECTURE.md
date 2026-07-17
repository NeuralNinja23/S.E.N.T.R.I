# SENTRI V2 — Conversation Domain Architecture

This document defines the architecture of the real-time conversation subsystem in SENTRI V2, outlining the transition from a cascaded pipeline to a native speech-to-speech model.

---

## ⚖️ Core Architecture Rule

> **Outer layers depend on inner abstractions. Inner layers never depend on outer implementations.**

This is the governing rule for every change to the conversation domain.

| ✅ Allowed | ❌ Forbidden |
|---|---|
| `websocket.py` → `ConversationEngine` | `miniomni.py` → `websocket.py` |
| `ConversationEngine` → `ISpeechTransport` | `transport.py` → `ConversationSession` |
| `InferenceRegistry` → `MiniOmni2Model` | `model_runtime.py` → `ConversationSession` |

The only places that should know `MiniOmni2Model` exists:
- `conversation/miniomni.py` — implementation
- `conversation/__init__.py` — registry registration
- `runtime/model_runtime.py` — process orchestration
- `config.py` — path configuration

Everything else interacts only with `ConversationEngine`, `ISpeechTransport`, `InferenceRuntimeManager`, or `InferenceRegistry`.

---

## 1. Domain Architecture

```
API (websocket.py)
    │
    ▼
ConversationEngine          ← owns turn routing and session streaming
    │
    ├─► InferenceRegistry   ← resolves model by ID, queries capabilities
    │       │
    │       ▼
    │   MiniOmni2Model      ← implements ISpeechToSpeechModel
    │       │
    │       ▼
    │   ISpeechTransport    ← protocol-agnostic I/O (HTTP, WS, gRPC…)
    │
    └─► ConversationAdapter ← text reasoning via Google ADK / Ollama
```

```
InferenceRuntimeManager     ← independent of ConversationEngine
    │
    ├── MiniOmni process
    ├── Health Monitor (HTTP probe)
    └── InferenceRuntimeState
```

---

## 2. Why Native Speech-to-Speech?

Cascaded pipelines (ASR → LLM → TTS) suffer from high latency (usually 2–5 seconds) and lose vocal expressions, pauses, and emotional nuances during transcription.

- **MiniOmni2** is a native end-to-end speech-to-speech model.
- It accepts raw speech tokens and generates audio output tokens directly.
- Executing locally on CUDA achieves an offline, low-latency duplex interaction.

---

## 3. Interface Contracts

Defined in [interfaces.py](file:///c:/Users/JARVIS/Desktop/Senitnel/backend/app/conversation/interfaces.py):

- **`ISpeechToSpeechModel`**: All speech models must implement `process_audio_stream(input_stream) → output_stream`.
- **`ISpeechTransport`**: All transport implementations must expose `send_audio_request(url, payload) → event_stream`.
- **`ConversationEngine`**: Routes text or voice turns, acting as the primary boundary between WebSocket and models.
- **`ConversationAdapter`**: Bridges text reasoning (Google ADK + Ollama) for text queries and memory tasks.

---

## 4. InferenceRegistry & Capability System

Models are registered at package import time with metadata:

```python
InferenceRegistry.register(
    id="miniomni2",
    version="2.0",
    modality="speech",
    implementation=MiniOmni2Model,
    runtime="http",
    capabilities={"speech_input", "speech_output", "streaming", "interruptible", "vision"}
)
```

SENTRI reasons about model capability without model-name branching:

```python
if engine.supports("vision"):
    ...  # attach screen frame

if engine.supports("streaming"):
    ...  # stream response chunks
```

---

## 5. Session Lifecycle

A `ConversationSession` (defined in [session.py](file:///c:/Users/JARVIS/Desktop/Senitnel/backend/app/conversation/session.py)) tracks one WebSocket connection:

1. **Handshake**: Client connects to `/ws/voice`.
2. **Audio accumulation**: Mic PCM bytes accumulate in `session.speech_buffer`.
3. **Turn trigger**: Client sends `turn_complete` → `session.consume_speech_buffer()` → `engine.run_voice_turn()`.
4. **Streaming**: Audio chunks and text tokens stream back over WebSocket; `SessionMetrics` records TTFT, TTFA, and total latency.
5. **Disposal**: Connection closes; session object is garbage collected.

`ConversationSession` owns only: buffer, transcript, history, speaking state, and metrics.
It does **not** own: memory retrieval, tool execution, runtime state, or watchdog state.

---

## 6. Metrics

[metrics.py](file:///c:/Users/JARVIS/Desktop/Senitnel/backend/app/conversation/metrics.py) tracks per-turn performance:

| Metric | Description |
|---|---|
| **TTFT** | Time to First Token |
| **TTFA** | Time to First Audio |
| **Total Latency** | Full turn round-trip |
| **Tokens/sec** | Generation throughput |
| **GPU inference time** | Model compute time |
| **Audio duration** | Total synthesized audio length |

---

## 7. Conversation Events

[events.py](file:///c:/Users/JARVIS/Desktop/Senitnel/backend/app/conversation/events.py) defines the reactive event contract:

`SpeechStarted` | `SpeechEnded` | `TranscriptReceived` | `ModelThinking` | `AudioChunkGenerated` | `ToolRequested` | `ToolFinished` | `ConversationFinished` | `ConversationInterrupted` | `ConversationError`

---

## 8. Future Roadmap

- **Model switching**: Add `sentri_voice_v1` to `InferenceRegistry` — no other code changes required.
- **Audio tokenization**: Native audio tokenizers (SNAC, Encodec) for waveform-to-token conversion.
- **Tool Calling Alignment**: Speech model text output mapped to ADK function call schemas for memory graph updates during voice.
- **Vision**: Screen frames injected per-turn when `engine.supports("vision")` is true.
