# Architecture Decision Records — Index

Architecture Decision Records (ADRs) document the **why** behind significant design choices in SENTRI V2. Each ADR is lightweight, permanent, and version-controlled.

---

## Status Definitions

| Status | Meaning |
|---|---|
| **Accepted** | Decision is in effect and enforced |
| **Proposed** | Under consideration, not yet implemented |
| **Superseded** | Replaced by a newer ADR |
| **Deprecated** | No longer relevant but kept for history |

---

## Decision Log

| ID | Title | Status |
|---|---|---|
| [ADR-0001](ADR-0001.md) | Conversation Engine Abstraction | Accepted |
| [ADR-0002](ADR-0002.md) | Speech Transport Layer | Accepted |
| [ADR-0003](ADR-0003.md) | Inference Runtime Manager | Accepted |
| [ADR-0004](ADR-0004.md) | Memory Retrieval Boundary | Accepted |
| [ADR-0005](ADR-0005.md) | Conversation Model Development | Accepted |
| [ADR-0006](ADR-0006.md) | Decommissioning World Awareness | Accepted |

---

## How to Add a New ADR

1. Copy the template below into a new file: `ADR-NNNN.md`
2. Increment the number sequentially
3. Add it to the table above
4. Commit with: `docs(adr): add ADR-NNNN <short title>`

---

## ADR Template

```markdown
# ADR-NNNN — Title

**Status:** Proposed | Accepted | Superseded | Deprecated
**Date:** YYYY-MM-DD
**Author:** 

---

## Context

Why does this decision need to be made?

## Decision

What was decided?

## Motivation

Why was this option chosen over alternatives?

## Consequences

What changes as a result? What new constraints exist?

## Compliance Rule

> One-sentence rule that enforces this decision.
```
