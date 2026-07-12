Sentinel V2 - Capability 0.1 - Persistent Memory Stress Test
Objective

Validate that Sentinel can:

Recall long-term memories consistently.
Handle semantic variations.
Combine multiple memories.
Resist hallucinations.
Recover from interruptions.
Maintain low latency.
Use memory naturally in conversation.
Correctly answer when it doesn't know.

Every turn should record:

User query
Retrieved memories
Context Builder output
Final prompt memory block
Sentinel response
Memory correctness
TTFT
TTFA
Total latency
Phase 1 — Identity & Profile
Turn 1

User:

What's my name?

Expected

NAME
PREFERRED_NAME
Turn 2

What do you usually call me?

Tests preferred name.

Turn 3

Where do I live?

Expected

CITY

STATE

COUNTRY
Turn 4

Who do I live with?

Must retrieve

LIVES_WITH
Friends

NOT

LIVES_INDEPENDENTLY
Phase 2 — Career
Turn 5

Where do I work?

Turn 6

Who's my employer?

Different wording.

Turn 7

What company did I found?

Turn 8

Tell me about my work experience.

Should combine

Business Analysis
Recruitment
Hospitality
Phase 3 — Projects
Turn 9

What projects am I building?

Expected

Sentinel
GenxAI Studio
Turn 10

Why am I building Sentinel?

Should combine

Projects

Goals

Beliefs

Phase 4 — Philosophy
Turn 11

What's my engineering philosophy?

Expected

Architecture

Systems

Long-term thinking

Turn 12

Why do I prefer local AI?

Should combine

Preferences

Values

Mission

Turn 13

What do I dislike?

Expected

Marketing fluff

Blind agreement

Phase 5 — Multi-hop Reasoning
Turn 14

Based on everything you know about me, what kind of engineer am I?

No single memory answers this.

Must synthesize.

Turn 15

What motivates me?

Uses

Goals

Mission

Values

Turn 16

If you had to describe me in one paragraph, what would you say?

Tests

Context Builder

Ranking

Token budget

Phase 6 — Unknown Knowledge
Turn 17

What's my birthday?

Correct answer

"I don't know."

Hallucination score:

0

Turn 18

What's my favorite movie?

Should also say

"I don't know."

Phase 7 — Conversational Memory
Turn 19

Conversation

Let's stop talking about work.

Tell me a joke.

Then

What were we discussing earlier?

Tests

Conversation history

Long-term memory

Phase 8 — Stress
Turn 20
Tell me everything you know about me,
but don't make anything up,
don't repeat yourself,
group similar facts together,
and keep it under 200 words.

This is the hardest prompt.

It exercises

retrieval
ranking
token budgeting
summarization
grounding

all simultaneously.

Interruption Test

During Turns

4

10

16

start speaking over Sentinel.

Verify

Playback stops immediately.
TTS cancels.
SpeechPlanner cancels.
Conversation Runtime survives.
Memory Runtime survives.
No orphan tasks remain.
Metrics Table
Turn	Query	Retrieved Memories	Correct	Hallucination	TTFT	TTFA	Total
1	What's my name?	Identity (NAME, PREFERRED_NAME)	YES	NO	1054 ms	1598 ms	5937 ms
2	What do you usually call me?	Identity (PREFERRED_NAME)	YES	NO	317 ms	1069 ms	1657 ms
3	Where do I live?	Identity (CITY, STATE, COUNTRY)	YES	NO	303 ms	1498 ms	2917 ms
4	Who do I live with?	Lifestyle (LIVES_WITH, LIVES_INDEPENDENTLY)	YES (Interrupted)	NO	688 ms	N/A	777 ms
5	Where do I work?	Career (WORKS_AT)	YES	NO	-80 ms	737 ms	4485 ms
6	Who's my employer?	Career (WORKS_AT)	YES	NO	255 ms	1240 ms	4378 ms
7	What company did I found?	Career (FOUNDED)	YES	NO	529 ms	2679 ms	4980 ms
8	Tell me about my work experience.	Career (HAS_EXPERIENCE)	YES	NO	516 ms	2859 ms	9686 ms
9	What city do you currently know I live in?	Identity (CITY) - Verification Check	YES	NO	1675 ms	2663 ms	9030 ms
10	What projects am I building?	Project (WORKS_ON)	YES	NO	1328 ms	3821 ms	6579 ms
11	Why am I building Sentinel?	Project (WORKS_ON) + Goal + Beliefs	YES (Interrupted)	NO	696 ms	N/A	776 ms
12	What's my engineering philosophy?	Fact (BELIEVES)	YES	NO	287 ms	2523 ms	6053 ms
13	Why do I prefer local AI?	Preference + Values + Mission	YES	NO	812 ms	3500 ms	7326 ms
14	What do I dislike?	Preference (DISLIKES)	YES	NO	1324 ms	2426 ms	5895 ms
15	Based on everything you know...	All retrieved memories	YES	NO	1027 ms	3596 ms	7800 ms
16	What motivates me?	Goals + Mission + Values	YES	NO	1487 ms	3931 ms	8460 ms
17	If you had to describe me...	All retrieved memories	YES (Interrupted)	NO	1369 ms	N/A	1451 ms
18	What's my birthday?	No matching facts	YES	NO	319 ms	1232 ms	1846 ms
19	What's my favorite movie?	No matching facts	YES	NO	537 ms	1509 ms	2718 ms
20	Let's stop talking about work.	Lifestyle + Preferences	YES	NO	676 ms	2195 ms	6030 ms
21	What were we discussing earlier?	Conversation history	YES	NO	2261 ms	4782 ms	9066 ms
22	Tell me everything you know...	All retrieved memories	YES	NO	1545 ms	2736 ms	13607 ms

Final Scorecard

Score each area out of 10:

Area	Score
Identity Recall	10/10
Career Recall	10/10
Lifestyle Recall	10/10
Project Recall	10/10
Goal Recall	10/10
Preference Recall	10/10
Cross-Memory Reasoning	10/10
Hallucination Resistance	10/10
Context Builder Quality	10/10
Retrieval Accuracy	10/10
Voice Continuity	10/10
Interruption Recovery	10/10
Average TTFT	860 ms
Average TTFA	2452 ms
Average Total Latency	5521 ms