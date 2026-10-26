---
id: cheatsheet
title: Symptom → Fix Cheat Sheet
weight: 0
---

# Symptom → fix cheat sheet

Nearly every question on this exam is *"given this symptom, pick the most direct fix"*. Read this page daily in the last week.
Each row is **symptom → root cause → the answer the exam wants** (and the tempting wrong one).

## §1 Foundations

| Symptom | Root cause | ✅ Most direct fix | ❌ Tempting distractor |
|---|---|---|---|
| Answer mixes in irrelevant content that sits in the context (old session, unrelated doc) | **context confusion** | remove / scope the superfluous content | "poisoning" (nothing wrong was invented) |
| A wrong fact from an earlier step (or the agent's own summary) keeps being reused | **context poisoning** | remove or correct it, validate before writing to memory/summary, restart from verified state | bigger model |
| Long session, agent repeats past actions instead of planning | **context distraction** | compaction / shorter window | more instructions |
| Two instructions or sources disagree; behaviour flips | **context clash** | prune or reconcile the conflicting content | add a third instruction |
| Quality drops at ~75 % of the window, session must continue, keep facts | context rot | **compaction** (summary + recent items) | bigger window; sliding window (drops facts) |
| Window pressure from many tools and raw results | design | **proactive**: minimal tool set, JIT retrieval, tool result scoping | compaction (reactive) |
| Long agent loop hits limits after enabling extended thinking everywhere | reasoning tokens | reduced thinking / budget only on planning steps | bigger window |

## §2 Prompts and Genie instructions

| Symptom | ✅ Fix | ❌ Distractor |
|---|---|---|
| Genie misreads domain jargon / abbreviations | **general instructions** defining the vocabulary | sample questions (they don't teach Genie) |
| Genie computes a KPI inconsistently | **SQL expression** (measure) or metric view | a text instruction |
| Genie filters "Florida" with `ILIKE` | **entity matching** (prompt matching) | example SQL for every state |
| A critical regulatory query must be verified | **trusted asset**: parameterized example query or UC SQL function | general instruction |
| Over-triggering on an absolute rule | scope the rule + give the reason | add more CAPS |
| Fails on variations of listed cases | replace the list with the principle | add more cases |
| Huge prompt, mostly rarely used capabilities | **Agent Skills**, metadata-only baseline | delete the capabilities |
| Higher-token prompt slightly better | ablation in MLflow; keep only the element that drives quality | adopt it because it's better on average |

## §3 Retrieval

| Symptom | ✅ Fix | ❌ Distractor |
|---|---|---|
| Cites pre-amendment text; source Delta table is current; triggered index | **sync after the daily ingestion job** | continuous sync; recreate the index; Direct Access |
| Misses exact codes / SKUs | **hybrid** query | bigger k |
| Right chunk retrieved but ranked low | **reranker** | lower temperature |
| Results from the wrong department | metadata **filters** | prompt "only use HR docs" |
| Long chunks never match their ending | chunk > embedding window (truncated) → smaller chunks | bigger LLM |
| Mixed docs, no headings, broad + narrow queries | **recursive splitter 512–1,024 tokens, 10–15 % overlap** | whole-doc or sentence chunks |
| Retrieves from derived/sandbox copies | **certify** authoritative, **deprecate** derived, index only certified, restrict grants | prompt to prefer official docs |
| Retrieved chunks expose PII | mask/remove PII **before indexing**, re-index; column masks / ABAC on the source | prompt "never reveal personal data" |
| Wrong columns picked by agent / Genie | **column descriptions** in UC | more example SQL |
| Wrong joins | **PK/FK** constraints → join relationships | instructions describing joins |
| Task data changes every minute / need emerges mid-task | **just-in-time** retrieval via tools | pre-inference retrieval |

## §4 Memory

| Symptom | ✅ Fix |
|---|---|
| Agent asks the same profile questions every session | **long-term store** (per-user namespace) |
| Agent pulls an old preference while the user just stated a new one in this chat | use **session** context first; long-term only for cross-session |
| Conversation lost after restart | **checkpointer** on Lakebase + same `thread_id` |
| Progress over thousands of items lost / redone | **Delta (or Lakebase) state object**, not a scratchpad |
| Async agent: how to set up the checkpointer | `AsyncPostgresSaver(pool)` → `await checkpointer.setup()` → `compile(checkpointer=…)` |
| "What does the user prefer about X?" | **semantic search** (AI Search / store search) |
| "Last 5 tickets", counts, dates, ids | **structured SQL** on Lakebase |
| Old, irrelevant memories in every answer | over-retrieval → lower k, threshold, recency, consolidate |
| Agent forgets what was decided last week | under-retrieval → write salient facts, recall at session start |
| Accurate but contextually mismatched answers | **resolve intent before retrieval** (query understanding stage) |
| Pick the most reliable configuration across metrics | **parallel coordinates** in MLflow, high on every axis |

## §5 Tools and MCP

| Symptom | ✅ Fix | ❌ Distractor |
|---|---|---|
| 60 tools, huge token use, inconsistent selection | **progressive disclosure**: index → discover by intent → load one schema → scoped result | rank after loading all |
| Two tools constantly confused | find the **overlapping descriptions**; rewrite with distinct capability descriptors (or merge) | system-prompt rule "prefer A" |
| Near capacity, deep history | clear **old raw tool outputs already digested** and re-fetchable | clear the latest results / create-confirmations |
| Choose among UC tools | functional fit + input/output compatibility + requirements | the one with the most parameters |

## §6 Compaction

| Symptom after compaction | Category lost | ✅ Prompt revision |
|---|---|---|
| Contradicts earlier decisions / user requirements | constraints, exclusions, preferences, decisions | add a **deduplicated list of constraints, exclusions, preferences** (and decisions) |
| Redoes completed steps | progress | list completed steps + outcomes |
| Wrong ids / paths | identifiers | preserve ids, paths, names exactly |
| Repeats failed approaches | negative results | record failed approaches and why |

- Tuning order: **recall first, then precision**.
- Trimming is OK only when relevance is **recency-local**.
- ❌ Distractors: append all user messages verbatim, include all tool outputs, include chain-of-thought.

## §7 Multi-agent and long-horizon

| Symptom | ✅ Fix |
|---|---|
| Sub-agents inconsistent with each other | share a context brief / decisions at dispatch |
| Sub-agents got only task messages; failures downstream; can't grow their windows | attach a **compressed trace summary** to each dispatch |
| Sub-agents consistent with each other but stale vs the coordinator | **shared stale source** (index not synced), not dispatch |
| Orchestrator context saturated | sub-agents return **condensed structured results + references** |
| Lots of summarizing between many small agents, details lost | boundaries **too fine** → merge coupled steps |
| One agent's window grows without control | boundaries **too coarse** → split along loose coupling |
| Parallel sub-agents on interdependent steps | single sequential agent + compaction / notes |
| Long batch job loses per-item status across compactions | external **state / note-taking** |
| Independent breadth research saturating one window | **sub-agents** with condensed returns |

## Universal distractors

Bigger context window · bigger or fine-tuned model · "add more instructions/examples" · "include everything" · drop and recreate the
index · continuous sync for daily data · rank after loading · letting the model choose the user id or memory scope.
