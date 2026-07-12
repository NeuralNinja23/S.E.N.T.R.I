# Sentinel Change Log & Capability Milestones

## Sentinel V2

### ✓ Capability 0.1: Persistent Memory

**Status**: Complete  
**Date**: 2026-07  
**Architecture**: Frozen  

#### Features
- Persistent semantic memory (SQLite-backed)
- Evidence tracking & version reinforcement
- Verification lifecycle state machine (Pending -> Verified)
- Memory Runtime Verification Boundary (Exclude unverified inferred facts from context builder)
- Retrieval planner (TF-IDF intent analysis & dynamic budget mapping)
- Working memory separation (short-term conversation history vs. long-term memory)
- Voice & WebSocket runtime integration

#### Benchmarks
- **Run 1**: Baseline memory integration tests (Scorecard: 10/10, Average Total Latency: 5,379 ms)
- **Run 2**: Prompts budget gating & dynamic category planners
- **Run 3**: Grounding priority fixes & ONNX CPU fallback execution session configurations
- **Run 4**: Verification Lifecycle State Machine promotion checks
- **Run 5 (Final)**: Category-based response category brevity limits, temporal Alignment grounding directives, and direct non-speculative factual checks (Average TTFT: 860 ms, Average TTFA: 2,452 ms, Average Total Latency: 5,521 ms)

*Note: Future changes to Capability 0.1 are strictly restricted to bug fixes only.*
