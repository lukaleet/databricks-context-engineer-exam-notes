---
id: visual
title: Visual Guide (Diagrams)
weight: 0
---

# Visual guide

Every mechanism the exam asks about, in pictures: what fills the window, where knowledge and memory come from, how tools and
summaries enter the context, and how context moves between agents. Each diagram comes with the 2–3 facts questions are built on and
a link to the full notes. The same diagrams also appear inside the section notes.

<div class="dg-legend"><span><i class="k-app"></i>users, agent / orchestrator code, instructions</span><span><i class="k-data"></i>UC data, AI Search, Lakebase memory &amp; state</span><span><i class="k-model"></i>LLM, context window, summaries</span><span><i class="k-tool"></i>tools, MCP, Genie, skills, sub-agents</span><span><i class="k-gov"></i>governance, constraints, failures</span><span><i class="k-eval"></i>MLflow tracing &amp; evaluation</span></div>

On a phone, scroll a diagram sideways to see all of it.

---

## 1. Foundations (§1 · 16%)

### 1.1 What fills the window

[[diagram:context-anatomy]]

- Tool schemas and **raw tool results** are the usual budget hogs, not the instructions.
- Fix the **biggest low-signal element** first. [§1.7](#/notes/d1)

### 1.2 The four failure modes

[[diagram:failure-modes]]

- Irrelevant but correct content **used** in the answer = **confusion**. A wrong fact **reused** = **poisoning**. [§1.3](#/notes/d1)

### 1.3 Degradation before the limit

[[diagram:degradation]]

- Quality drops at a knee well before the hard limit → **compact before the knee**. A bigger window isn't the fix. [§1.9](#/notes/d1)

### 1.4 Proactive vs reactive

[[diagram:proactive-reactive]]

- "Before compaction becomes necessary" → **minimal tools, JIT retrieval, result scoping**. [§1.5](#/notes/d1)

---

## 2. Instructions and Genie (§2 · 9%, §3 · 20%)

### 2.1 What goes where in a Genie space

[[diagram:genie-config]]

- Jargon → **general instructions**. KPIs → **SQL expressions**. "Florida" → **entity matching**. Verified answers → **trusted assets**.
- **Sample questions only help users.** [§2.4](#/notes/d2)

---

## 3. Retrieval (§3 · 20%)

### 3.1 Up front or just in time?

[[diagram:retrieval-modes]]

- Stable corpus, self-contained question → **pre-inference**. Multi-step, live data, the need emerges → **just-in-time**. [§3.1](#/notes/d3)

### 3.2 RAG over a governed corpus

[[diagram:rag-uc]]

- Triggered index + daily data → **sync right after the ingestion task**. [§3.5–3.6](#/notes/d3)

### 3.3 Only authoritative sources

[[diagram:authoritative]]

- **Certify** the source of truth, **deprecate** copies, index and grant only certified assets. [§3.9](#/notes/d3)

---

## 4. Memory (§4 · 18%)

### 4.1 The memory layers

[[diagram:memory-layers]]

- Same chat → **checkpointer** (`thread_id`). Across chats → **store** (user namespace). Exact long-job progress → **state table**.
- Async: `AsyncPostgresSaver(pool)` → `await setup()` → `compile(checkpointer=…)`. [§4.5](#/notes/d4)

### 4.2 Semantic search or SQL?

[[diagram:memory-router]]

- Meaning → semantic search. Ids, dates, counts, "last N" → **SQL on Lakebase**. [§4.6](#/notes/d4)

### 4.3 Intent before retrieval

[[diagram:intent-first]]

- "Accurate but contextually mismatched" → add an **intent-resolution stage before retrieval**. [§4.9](#/notes/d4)

---

## 5. Tools (§5 · 13%)

### 5.1 Progressive disclosure

[[diagram:progressive-disclosure]]

- Filter **before** loading: catalog → discover by intent → one schema → scoped result. [§5.3](#/notes/d5)

### 5.2 Clearing tool results

[[diagram:tool-clearing]]

- Clear **old, digested, re-fetchable** outputs. Keep recent results, pending dependencies, and create/write confirmations. [§5.4](#/notes/d5)

### 5.3 Agent Skills

[[diagram:skills]]

- Baseline = **metadata only**. Bodies load when relevant. [§5.6](#/notes/d5)

---

## 6. Compaction (§6 · 11%)

### 6.1 The ladder

[[diagram:compaction-ladder]]

- Trimming is fine only when relevance is **recency-local**. [§6.2](#/notes/d6)

### 6.2 What survives a good compaction

[[diagram:compaction-keep]]

- Contradicting earlier decisions after compaction → the summary lost **constraints / preferences / decisions**. [§6.4](#/notes/d6)

### 6.3 Tuning the prompt

[[diagram:compaction-tuning]]

- **Recall first, then precision.** [§6.5](#/notes/d6)

---

## 7. Multi-agent and long-horizon (§7 · 13%)

### 7.1 Dispatch and returns

[[diagram:dispatch]]

- Task line only → conflicting implicit decisions. Fix with a **compressed trace summary** at dispatch.
- Orchestrator saturated → sub-agents return **condensed results + handles**. [§7.3–7.4](#/notes/d7)

### 7.2 Where to draw agent boundaries

[[diagram:boundaries]]

- Many lossy handoffs = **too fine**. One exploding window = **too coarse**. [§7.5](#/notes/d7)

### 7.3 Picking a long-horizon strategy

[[diagram:long-horizon]]

- Name the **dependency structure** first; the strategy follows. [§7.6](#/notes/d7)
