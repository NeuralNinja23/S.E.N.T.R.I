# Sentinel V2 — Conversation Domain Architecture

This document defines the architecture of the real-time conversation subsystem in Sentinel V2, outlining the transition from a cascaded pipeline to a native speech-to-speech model.

---

## 1. Why MiniOmni2?
Cascaded pipelines (ASR $\rightarrow$ LLM $\rightarrow$ TTS) suffer from high latency (usually 2 to 5 seconds) and lose vocal expressions, pauses, and emotional nuances during transcription. 
*   **MiniOmni2** is a native end-to-end speech-to-speech conversational model.
*   It accepts raw speech tokens and generates audio output tokens directly, bringing response latency down to **sub-second** bounds.
*   By executing MiniOmni2 locally on CUDA, we achieve an offline, premium, and human-like duplex interaction.

---

## 2. Interface Contracts
To remain model-agnostic, the conversation domain enforces clean abstract interfaces in [interfaces.py](file:///c:/Users/JARVIS/Desktop/Senitnel/backend/app/conversation/interfaces.py):

*   **`ISpeechToSpeechModel`**: All speech models must implement `process_audio_stream(input_stream) -> output_stream`.
*   **`ConversationEngine`**: Coordinates incoming text or voice turns, acting as the primary boundary between WebSockets and underlying models.
*   **`ConversationAdapter`**: Bridges legacy text reasoning (using local Ollama + Google ADK) to maintain support for text-only queries and memory tasks.

---

## 3. Session Lifecycle
A conversation session (defined in [session.py](file:///c:/Users/JARVIS/Desktop/Senitnel/backend/app/conversation/session.py)) spans the lifecycle of a single WebSocket connection:
1.  **Handshake**: Client connects to `/ws/voice`, receiving a `system` status indicating engine ready/missing state.
2.  **Duplex Stream**: Audio frames stream continuously over WebSocket.
3.  **Active Turn**: User speaks $\rightarrow$ Model generates audio stream $\rightarrow$ Client plays audio chunks.
4.  **Disposal**: Connection closes $\rightarrow$ Session parameters are reset and memory stats written.

---

## 4. Audio Flow & Streaming Model

```
[Browser Mic Input] 
       │ (16kHz 16-bit Mono PCM bytes)
       ▼
[WebSocket Route]
       │ (Audio Chunks)
       ▼
[ConversationEngine]
       │
       ├─► (Voice Turn) ──► [ISpeechToSpeechModel (MiniOmni2)] ──► (Audio Output) ──► [WebSocket Out]
       │
       └─► (Text Turn)  ──► [ConversationAdapter (Ollama)]     ──► (Text Response) ──► [WebSocket Out]
```

---

## 5. Future Training & Integration Roadmap
*   **Audio tokenization**: Integrate native audio tokenizers (e.g. SNAC or Encodec) to transform waveforms into discrete tokens.
*   **Tool Calling Alignment**: Instruct the text outputs of the speech model to produce function calls matching ADK schemas, allowing memory graph updates during voice conversations.
