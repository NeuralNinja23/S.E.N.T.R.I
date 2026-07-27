# SENTRI V2.2.0 System Resilience Test Plan
## Local AI Runtime Validation Suite

### Objective
Validate that Sentri operates reliably as a single-user, local-first AI assistant on consumer hardware. The goal is to verify stability, recovery, memory integrity, voice reliability, learning plane stability, and long-term resource usage under single-user constraints.

All testing files, the resilience runner, telemetry logs, and final evaluation reports will be isolated in the folder: **`Docs/Tests/System Resilience/`**.

---

## User Review Required

> [!IMPORTANT]
> **New Directory Isolation**: We will create a new directory at `Docs/Tests/System Resilience/` to house all resilience test scripts, telemetry logs, and the final report. This decouples the resilience suite from capability-specific regression folders.
>
> **Internal Health Monitoring**: We will instrument the backend with a thread-safe `TelemetryCollector` in `app/utils/telemetry.py` to record queue lengths, active tasks, SQLite write times, prompt build times, etc. This telemetry will be exposed via the `/api/system-stats` endpoint.
>
> **Subprocess Server Execution**: The stress test runner (`resilience_tester.py` inside the new folder) will automatically launch the FastAPI uvicorn server in a subprocess to run tests against the real network layer (WebSockets and REST), collecting telemetry in real-time.

---

## Proposed Test Suite Structure

### Phase 0 — Runtime Warm-Up
*   **Purpose**: Exclude one-time initialization costs from steady-state measurements.
*   **Load**:
    *   Initialize Faster-Whisper, Kokoro TTS, and warm HTTP connection pools.
    *   Load the Ollama model fully into memory/VRAM.
    *   Execute 5–10 dummy text turns and 5–10 dummy voice turns.
*   **Pass Criteria**: Ollama, ASR, and TTS state show `READY` without errors; connection pool established.

### Phase 1 — Core Stability
*   **Test 1 — Conversation Stability (Text)**:
    *   **Run**: 500 consecutive conversations mixing questions, memory operations, long reasoning, tool calls, and follow-ups.
    *   **Pass Criteria**: 0 crashes, 0 unhandled exceptions, 100% identity consistency, reflection completes for all turns, memory retrieval succeeds, and no database corruption.
*   **Test 2 — Voice Stability (Voice)**:
    *   **Run**: 200 voice conversations including normal turns, long/fast responses, silent pauses, and repeated wake-ups.
    *   **Pass Criteria**: 0 audio pipeline deadlocks, 0 orphaned playback tasks, 100% WebSocket connection recovery, and no RAM/VRAM resource leaks.

### Phase 2 — User Interaction Stress
*   **Test 3 — Barge-In Stress**:
    *   **Simulate**: Interruptions before thinking, before first audio, mid-sentence, final sentence, double interrupts, and triple interrupts.
    *   **Pass Criteria**: Playback stops immediately, queues clear, 0 orphaned asyncio tasks, and the next turn continues correctly.
*   **Test 4 — Context Pressure**:
    *   **Run**: Conversations with 20, 50, 100, and 250 turns. Inject large memories (100+ entries) and long system prompts.
    *   **Pass Criteria**: 0 token overflow errors, prompt truncation executes successfully within limits, and prompt build time remains under 2.0 seconds.

### Phase 3 — Memory Validation
*   **Test 5 — Memory Hammer**:
    *   **Run**: 1,000+ simultaneous operations (`remember`, `forget`, `update`, `retrieve`) in parallel async tasks.
    *   **Pass Criteria**: Database integrity verified, 0 duplicated memories, 100% retrieval correctness, and no SQLite write deadlocks/locking errors.
*   **Test 6 — Reflection Stress**:
    *   **Run**: Flood conversations faster than background reflections complete.
    *   **Pass Criteria**: Active reflection queue does not grow unboundedly, learning state updates complete eventually, and user TTFT is completely unaffected by reflection queue backlog.

### Phase 4 — Recovery Testing
*   **Test 7 — Local Failure Recovery**:
    *   **Trigger**: Ollama shutdown, Ollama restart, WebSocket disconnect, ASR failure, Kokoro timeout, and SQLite timeout.
    *   **Pass Criteria**: Graceful failure alerts sent, no server process crashes, and conversations resume normally once connection is restored.
*   **Test 8 — Resource Pressure**:
    *   **Simulate**: Peg CPU to 100%, limit RAM, and restrict GPU VRAM.
    *   **Pass Criteria**: Graceful degradation (e.g. falling back to fast prompts or trimmed contexts) without deadlocks or unhandled crashes.

### Phase 5 — Long-Term Reliability
*   **Test 9 — 12-Hour Soak Test**:
    *   **Run**: Continuous conversations, reflections, memory writes, and voice sessions for 12 hours.
    *   **Monitor**: RAM, VRAM, CPU, asyncio tasks, threads, and queue sizes every minute.
    *   **Pass Criteria**: Zero cumulative RAM/VRAM leakage (flatline trend after warm-up), active tasks and threads return to baseline on idle, and no queue backlogs.

---

## Internal Health Monitoring Telemetry

We will collect the following telemetry from the server during runs:
*   **Performance**: TTFT, TTFA, Total Latency.
*   **Memory**: Retrieved Memories, Working Memory Size, Prompt Size, Context Tokens.
*   **Runtime**: Active asyncio Tasks, Active Threads, Queue Lengths (Token, Phrase, Audio, Reflection).
*   **Resources**: RAM, VRAM, CPU, SQLite Write Time.

---

## Verification Plan

### Test Run Commands
*   Execute the resilience tester script:
    `venv\Scripts\python Docs/Tests/"System Resilience"/resilience_tester.py --run-all`
*   Verify output:
    Check `Docs/Tests/System Resilience/Sentri System Resilience Report - V2.2.0.md` containing the final evaluation report:
    1.  **System Overview**: Hardware, model, configuration.
    2.  **Test Results Table** (Pass/Fail for all 9 tests).
    3.  **Peak Metrics**: Peak RAM, VRAM, CPU, Queue sizes, max TTFT/TTFA.
    4.  **Stability Summary**: Crashes, deadlocks, leaks, orphaned tasks, SQLite errors, recovery events.
    5.  **Regression Summary Table** (Baseline vs. Current comparison of TTFT, TTFA, Memory, Reflection, Voice, Resource Usage).
    6.  **Overall Verdict**: PASS, PASS WITH OBSERVATIONS, or FAIL.
