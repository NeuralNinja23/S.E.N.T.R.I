Implementation Plan — Sentri V2 - Capability 0.1 - Persistent Memory

Sentri V2 has successfully achieved stable natural conversation through the Conversation Runtime. The next milestone is to introduce a dedicated Memory Runtime, responsible for storing and retrieving long-term user memories.

The objective of this phase is not to build a complete cognitive memory system. It is to give Sentri the ability to remember structured facts about the user across conversations.

This runtime should follow the same architectural principles as the Conversation Runtime:

Thin orchestration
Strong contracts
Decoupled providers
Typed models
Local-first
Extensible architecture
Design Philosophy

The Memory Runtime answers one question:

"What does Sentri know about the user?"

This runtime is not responsible for:

Planning
Reasoning
RAG
Reflection
Memory consolidation
Importance scoring

Those belong to future versions.

Architecture
backend/app/memory/

├── __init__.py
├── runtime.py
├── contracts.py
├── registry.py
├── metrics.py
│
├── providers/
│     ├── __init__.py
│     └── sqlite_provider.py
│
└── storage/
      ├── __init__.py
      └── sqlite_store.py
Runtime Responsibilities

MemoryRuntime is the only public interface.

Nothing outside the memory package should directly query SQLite.

Public API

remember()

recall()

update()

delete()

list_memories()
Contracts

Create strongly typed dataclasses.

MemoryEntry

Represents a stored memory.

Fields

id
category
subject
predicate
object
confidence
created_at
updated_at
MemoryQuery

Represents a retrieval request.

Fields

category
subject
predicate
limit
MemoryResult

Represents retrieval results.

Fields

memories
count
Storage Model

SQLite is the source of truth.

Create a single table.

memories

id

category

subject

predicate

object

confidence

created_at

updated_at

Example rows

Category	Subject	Predicate	Object
Career	Nisarg	WORKS_AT	Anti Noob Media
Career	Nisarg	FOUNDED	GenxAI Labz
Preference	Nisarg	LIKES	Coffee
Lifestyle	Nisarg	LIVES_WITH	Friends
Categories

Implement only

Identity
Career
Preference
Lifestyle
Relationship
Goal
Project
Fact

No additional categories.

SQLite Store

Responsibilities

Initialize database.
Create tables.
CRUD operations.
Search.
Update existing memories.

Must not contain business logic.

SQLite Provider

Responsibilities

Translate Runtime requests into SQLite operations.

Example

remember()

↓

SQLiteProvider

↓

SQLiteStore.insert()
Memory Runtime

Responsibilities

remember()

Receives a MemoryEntry.

Routes to provider.

Returns success.

recall()

Receives MemoryQuery.

Returns MemoryResult.

update()

Updates existing memories.

delete()

Archives or removes memory.

list_memories()

Returns all stored memories.

Memory Retrieval Flow
Conversation Runtime

↓

MemoryRuntime.recall()

↓

SQLite Provider

↓

SQLite Store

↓

MemoryResult

↓

Conversation Runtime
Memory Store Flow
Conversation Runtime

↓

MemoryRuntime.remember()

↓

SQLite Provider

↓

SQLite Store

↓

Database
Update Logic

When storing a memory:

If the same

Subject

Predicate

already exists

↓

Update Object

instead of creating duplicates.

Example

Nisarg
LIKES
Coffee

Later

Nisarg
LIKES
Tea

Should update the previous memory rather than insert another conflicting one.

Integration

Modify the Conversation Runtime so that it can call

memory_runtime.remember(...)

and

memory_runtime.recall(...)

No automatic extraction yet.

For V1, memories are inserted explicitly.

Metrics

Track

Store operations
Recall operations
Update operations
Delete operations
SQLite latency
Future Compatibility

The runtime should be designed so future versions can add

Reflection
Memory consolidation
Forgetting
RAG
Knowledge Graph
Embeddings

without changing the public MemoryRuntime API.

Verification Plan
Automated
Verify SQLite database initializes correctly.
Verify CRUD operations.
Verify duplicate memories update correctly.
Verify retrieval by category.
Verify retrieval by subject.
Verify retrieval by predicate.
Manual

Confirm Sentri can

Store

My favorite drink is coffee.

Later answer

Your favorite drink is coffee.

Store

I work at Anti Noob Media.

Later answer

You currently work at Anti Noob Media.

Update

My favorite drink is tea.

Later answer

Your favorite drink is tea.

without creating duplicate memories.

Final Rule

The Memory Runtime must store structured long-term knowledge, not conversation history.

Every stored memory should represent a stable fact about the user or their world, using a simple subject–predicate–object model that can evolve into a richer knowledge graph in future versions while keeping the V1 implementation simple, reliable, and easy to extend.