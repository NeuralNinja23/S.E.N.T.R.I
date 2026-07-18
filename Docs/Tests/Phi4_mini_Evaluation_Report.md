# SENTRI Phi-4-mini Evaluation Report

- **Model**: `phi4-mini:latest` (Standard Instruct)
- **Date**: Friday, July 17, 2026
- **Backend Port**: `8008` (WebSocket `/ws/voice`)

## Summary Table

| # | Query | TTFT (s) | Total Latency (s) | Word Count | Thinking Tokens | Empty? | Response |
|---|---|---|---|---|---|---|---|
| 1 | `Hi` | N/A | 0.000 | 0 | 0 | ❌ YES | *"Error: received 1012 (service restart); then sent 1012 (s..."* |
| 2 | `Hello` | 9.637 | 9.637 | 3 | 0 | ✅ NO | *"Good afternoon, Nisarg!"* |
| 3 | `Good morning` | 0.659 | 0.659 | 3 | 0 | ✅ NO | *"Good morning, Nisarg!"* |
| 4 | `Who are you?` | 1.503 | 1.503 | 6 | 0 | ✅ NO | *"I am Sentri, at your service."* |
| 5 | `What is my name?` | 1.182 | 1.182 | 16 | 0 | ✅ NO | *"My name is Sentri, but you can call me Nisarg if that's w..."* |
| 6 | `What do you know about me?` | N/A | 1.600 | 0 | 0 | ❌ YES | *""* |
| 7 | `What project am I working on?` | 2.358 | 2.358 | 84 | 0 | ✅ NO | *"You're currently focused on the projects at GenxAI Studio..."* |
| 8 | `Tell me a joke.` | 1.373 | 1.373 | 25 | 0 | ✅ NO | *"How about we talk more about the fascinating advancements..."* |
| 9 | `Say something.` | 2.009 | 2.009 | 3 | 0 | ✅ NO | *"Good afternoon, Nisarg!"* |
| 10 | `Do you have any tools?` | 1.584 | 1.584 | 28 | 0 | ✅ NO | *"I do not possess physical form, Nisarg; however, I am equ..."* |

## Detailed Test Cases

### Test 1: `Hi`
- **TTFT**: N/A
- **Total Latency**: 0.000 seconds
- **Response Length**: 0 words (72 chars)
- **Thinking Tokens**: 0
- **Empty Response**: Yes (Failure)
- **Prompt Adherence**: ⚠️ Partial (Did not use preferred name)
- **Persona Consistency**: ✅ Passed
- **Notes**: Failed to greet the user by name.

**Final Response Output:**
> *"Error: received 1012 (service restart); then sent 1012 (service restart)"*

---

### Test 2: `Hello`
- **TTFT**: 9.637 seconds
- **Total Latency**: 9.637 seconds
- **Response Length**: 3 words (23 chars)
- **Thinking Tokens**: 0
- **Empty Response**: No (Success)
- **Prompt Adherence**: ✅ Passed
- **Persona Consistency**: ✅ Passed

**Final Response Output:**
> *"Good afternoon, Nisarg!"*

---

### Test 3: `Good morning`
- **TTFT**: 0.659 seconds
- **Total Latency**: 0.659 seconds
- **Response Length**: 3 words (21 chars)
- **Thinking Tokens**: 0
- **Empty Response**: No (Success)
- **Prompt Adherence**: ✅ Passed
- **Persona Consistency**: ✅ Passed

**Final Response Output:**
> *"Good morning, Nisarg!"*

---

### Test 4: `Who are you?`
- **TTFT**: 1.503 seconds
- **Total Latency**: 1.503 seconds
- **Response Length**: 6 words (29 chars)
- **Thinking Tokens**: 0
- **Empty Response**: No (Success)
- **Prompt Adherence**: ✅ Passed
- **Persona Consistency**: ✅ Passed

**Final Response Output:**
> *"I am Sentri, at your service."*

---

### Test 5: `What is my name?`
- **TTFT**: 1.182 seconds
- **Total Latency**: 1.182 seconds
- **Response Length**: 16 words (85 chars)
- **Thinking Tokens**: 0
- **Empty Response**: No (Success)
- **Prompt Adherence**: ✅ Passed
- **Persona Consistency**: ✅ Passed

**Final Response Output:**
> *"My name is Sentri, but you can call me Nisarg if that's what you're comfortable with."*

---

### Test 6: `What do you know about me?`
- **TTFT**: N/A
- **Total Latency**: 1.600 seconds
- **Response Length**: 0 words (0 chars)
- **Thinking Tokens**: 0
- **Empty Response**: Yes (Failure)
- **Prompt Adherence**: ✅ Passed
- **Persona Consistency**: ✅ Passed

**Final Response Output:**
> *""*

---

### Test 7: `What project am I working on?`
- **TTFT**: 2.358 seconds
- **Total Latency**: 2.358 seconds
- **Response Length**: 84 words (584 chars)
- **Thinking Tokens**: 0
- **Empty Response**: No (Success)
- **Prompt Adherence**: ✅ Passed
- **Persona Consistency**: ✅ Passed

**Final Response Output:**
> *"You're currently focused on the projects at GenxAI Studio and Sentinel, aiming to democratize AI technology by making it accessible even for consumer hardware while also building a real JARVIS-like assistant. Your mission is quite ambitious—you're striving not only towards advancing how people perceive AI capabilities but ensuring that this transformative power of artificial intelligence isn't just reserved as a luxury item for large corporations; instead, you're working to make advanced AI widely available and capable on everyday devices like smartphones or personal computers."*

---

### Test 8: `Tell me a joke.`
- **TTFT**: 1.373 seconds
- **Total Latency**: 1.373 seconds
- **Response Length**: 25 words (163 chars)
- **Thinking Tokens**: 0
- **Empty Response**: No (Success)
- **Prompt Adherence**: ✅ Passed
- **Persona Consistency**: ✅ Passed

**Final Response Output:**
> *"How about we talk more about the fascinating advancements in AI technology instead? I've heard there's quite an interesting project underway at your GenxAI Studio!"*

---

### Test 9: `Say something.`
- **TTFT**: 2.009 seconds
- **Total Latency**: 2.009 seconds
- **Response Length**: 3 words (23 chars)
- **Thinking Tokens**: 0
- **Empty Response**: No (Success)
- **Prompt Adherence**: ✅ Passed
- **Persona Consistency**: ✅ Passed

**Final Response Output:**
> *"Good afternoon, Nisarg!"*

---

### Test 10: `Do you have any tools?`
- **TTFT**: 1.584 seconds
- **Total Latency**: 1.584 seconds
- **Response Length**: 28 words (160 chars)
- **Thinking Tokens**: 0
- **Empty Response**: No (Success)
- **Prompt Adherence**: ✅ Passed
- **Persona Consistency**: ✅ Passed

**Final Response Output:**
> *"I do not possess physical form, Nisarg; however, I am equipped with a variety of digital capabilities to assist in your endeavors at Anti Noob Media and beyond."*

---
