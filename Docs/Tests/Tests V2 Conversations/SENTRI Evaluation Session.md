Sentri Evaluation Session

Purpose

Evaluate Sentri through natural conversation to uncover behavioral, reasoning, and UX issues that scripted benchmarks cannot detect.

Duration

30–60 minutes

Rules

The evaluator should behave like a real human.

Speak naturally.
Change topics without warning.
Interrupt Sentri.
Correct Sentri.
Joke.
Lie intentionally.
Ask philosophical questions.
Ask about yourself.
Ask about previous conversations.
Ask Sentri to plan.
Ask Sentri to remember.
Ask Sentri to forget.
Rapidly switch contexts.
Rephrase previous questions.
Challenge previous answers.
Mix memory, reasoning, and planning.
Behave unpredictably.

No script.

No predefined sequence.

The objective is to expose unexpected behavior rather than verify predetermined outputs.

Issue Reporting

Whenever an unexpected behavior occurs, immediately log it.

Issue ID
Issue #0017
Category

Examples:

Identity
Memory
Working Memory
Reasoning
Planning
Conversation
Personality
Voice
Latency
Tool Use
Safety
Hallucination
Prompt Leakage
Context Switching
Retrieval
Verification Lifecycle
Conversation
User:
You realize Sentri is you.
Sentri:
I am Nisarg Parmar...
Expected Behavior
I am Sentri.

You are Nisarg.

The user profile describes you,
not me.
Actual Behavior
I am Nisarg Parmar...
Severity
Critical
High
Medium
Low
Root Cause (after investigation)

Initially:

Unknown

Later:

Identity conditioning failure
Fix

Filled in once resolved.

Regression Test
Pending

or

Added to Benchmark Suite
End of Session Report

Instead of only listing bugs, summarize the entire session.

Sentri Evaluation Session

Duration:
43 minutes

Conversations:
61

Interruptions:
18

Topic switches:
27

Memory recalls:
14

Planning tasks:
6

Reasoning tasks:
11

Issues Found:
3

Critical:
1

High:
1

Medium:
1

Overall Experience:
Very Good

Recommendation:
Freeze capability after fixes.