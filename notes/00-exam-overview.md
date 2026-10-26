---
id: overview
title: Exam Overview & Traps
weight: 0
---

# Exam overview

| Item | Detail |
|---|---|
| Exam | Databricks Certified **Context Engineer Associate** |
| Version covered | Exam guide for the version **available from July 29, 2026** (a beta ran at Data + AI Summit, June 16–18, 2026) |
| Scored questions | **About 45**, multiple-choice **or multiple-selection** |
| Unscored questions | May appear, aren't identified, and the extra time is already included |
| Time | **90 minutes** (2 min per scored question) |
| Language | English. Code is **Python**, with some SQL. |
| Delivery | Online proctored (the certification page also lists test centers) |
| Fee / validity | USD 200 / 2 years (recertify by taking the current live exam) |
| Recommended experience | 6+ months of hands-on context engineering on Databricks. No formal prerequisite. |

> **Re-check the official exam guide about two weeks before your exam.** The guide on the
> [certification page](https://www.databricks.com/learn/certification/context-engineer-associate) is the source of truth.

## Section weights → approximate scored questions

| # | Section | Weight | ≈ Questions |
|---|---|---|---|
| 1 | Foundations of Context Engineering | 16% | 7 |
| 2 | System Prompt and Instruction Design | 9% | 4 |
| 3 | Knowledge Retrieval and Genie Configuration | **20%** | **9** |
| 4 | Memory Architecture with Lakebase and MLflow | **18%** | **8** |
| 5 | Tool Design, MCP, and Agent Context | 13% | 6 |
| 6 | Context Compression and Compaction | 11% | 5 |
| 7 | Multi-Agent and Long-Horizon Task Design | 13% | 6 |

Sections 3 and 4 (retrieval + memory) are **38%** of the exam. Section 3 overlaps heavily with what you learned
for the GenAI Engineer exam. Section 4 (Lakebase memory) and Sections 6–7 (compaction, multi-agent context) are mostly new.
See the [GenAI → Context Engineer bridge](#/notes/bridge) for exactly what carries over.

## Recommended preparation (from the exam guide)

- Databricks Academy, *Generative AI Engineering with Databricks*: Building RAG Agents with Agent Bricks · Building Agentic
  Applications on Databricks · Agent Evaluation on Databricks · Deploying and Monitoring Agent Applications · Building Reliable
  Conversational Agents with Genie.
- Databricks Academy, *Data Engineering with Databricks*: Get Started with Databricks for Data Engineering · Get Started with Data
  Governance · Data Governance at Scale.
- Background knowledge the guide lists: LLM context windows and how length affects performance; prompt engineering, system prompts and
  few-shot examples; agent frameworks and **MCP**; Agent Bricks, semantic search and embedding models; **Lakebase** for agent memory
  and **MLflow 3** for evaluation; Unity Catalog governance for tools and retrieval sources.

## How the questions are written

Every objective in the guide starts with **"Given a … , identify / diagnose / select …"**. In practice that means:

1. **A scenario with a symptom.** An agent trace, an MLflow result, a Genie space that misreads terms, sub-agents that disagree.
2. **Four plausible fixes.** Usually all four would *change something*. Only one fixes the **root cause** most **directly** and
   **cost-effectively**, often with an explicit constraint such as "without increasing token cost", "without expanding each sub-agent's
   context window" or "without discarding previously retrieved facts".

Three habits win this exam:

- **Read the constraint at the end of the question first.** It eliminates two options most of the time.
- **Find the evidence in the scenario.** If the sub-agents' *retrieved* passages are stale, the cause is the index, even when the
  question is in the multi-agent section and "share the trace" sounds right.
- **Prefer the smallest targeted change.** The exam consistently rewards "add the missing category to the compaction prompt" over
  "keep everything", and "sync the index after the daily job" over "switch to continuous sync".

### Lessons from the official sample questions

The guide has 10 sample questions (answers at the end of the PDF). You can read them yourself. These are the patterns they teach:

| Topic | The pattern behind the right answer |
|---|---|
| Failure modes | Irrelevant prior-session content that the model **mixes into** the answer = **context confusion** (superfluous content used). Not poisoning: nothing hallucinated got into the context and kept being reused. |
| Degradation at ~75% of the window | **Compaction** (high-fidelity summary + the most recent items). A bigger window doesn't stop context rot, and a sliding window throws away facts. |
| Genie misreads jargon ("bps", "the rates desk") | **General text instructions** that define the vocabulary. Sample questions only show users what to ask; they don't teach Genie. |
| Index serves pre-amendment text | Triggered Delta Sync index never re-synced → **call sync after the daily ingestion job** (cheapest). Continuous sync costs more for daily data. |
| Mixed-length docs, no headings, broad + narrow queries | **Recursive splitter**, 512–1,024 tokens, **10–15 % overlap**. |
| "Reliable = good on all metrics, none lagging" | **MLflow parallel coordinates chart**: pick the run that stays high on every axis. A mean hides a lagging metric, and a small spread can still be uniformly low. |
| Async LangGraph + Lakebase | `AsyncPostgresSaver(pool)` → **`await checkpointer.setup()`** → `graph.compile(checkpointer=checkpointer)`. |
| 60 MCP tools, 4 near-duplicates | **Progressive disclosure**: distinct capability descriptors in the registry, discovery scores against intent and surfaces only the best schema. Ranking *after* loading all four defeats the point. |
| Agent contradicts earlier decisions after compaction | Add a **deduplicated list of the user's constraints, exclusions and preferences** to the compaction prompt. Raw logs of all messages or all tool outputs cost too much. |
| Sub-agents consistent with each other but stale | Their *retrieved context* is stale while the coordinator has the new figures → **index not synced**. Read the evidence, not the section title. |

## Distractors that are almost always wrong

| Distractor | Why it's wrong |
|---|---|
| "Use a model with a bigger context window" | Context rot and distraction happen **well before** the hard limit. More room doesn't restore focus. |
| "Add more instructions / more examples / ALL-CAPS rules" | More tokens compete for the same attention budget. It can also cause clash and over-triggering. |
| "Include everything (all tool outputs, full history, every message)" | Fixes recall by destroying precision and cost. The exam wants the **missing category**, not the whole log. |
| "Fine-tune the model / the embedding model" | Context problems are fixed in the context. Fine-tuning is slow, expensive and doesn't fix stale or missing data. |
| "Drop and recreate the index" / "switch to continuous sync" | Heavy-handed. A scheduled or triggered sync after the source update is enough for daily data. |
| "Rank the candidates *after* loading them all into context" | The tokens are already spent. Progressive disclosure filters *before* loading. |
| "Let the model decide the memory scope / user id" | Identity and scope come from **trusted application context**, never from model output. |

## Product names: this exam uses the current ones

Unlike the GenAI Engineer exam (March 2026 names), this guide is from July 2026 and already says **Databricks AI Search**
(formerly Vector Search). Expect both names in study material:

| In this exam guide | Also called | Notes |
|---|---|---|
| Databricks AI Search | Vector Search (Mosaic AI Vector Search) | APIs and SQL still say `vector-search` / `vector_search()`. Python package `databricks-ai-search`, client `AISearchClient`. |
| Genie space | Genie Agent (docs, from ~Oct 2026) | Same feature: NL → SQL over curated UC tables. |
| Lakebase | Databricks managed Postgres (OLTP) | Low-latency row store used for agent memory and checkpoints. |
| MLflow 3 | | Tracing, `mlflow.genai.evaluate`, scorers and judges, experiment comparison. |
| Agent Bricks | | Knowledge Assistant, Supervisor Agent (formerly Multi-Agent Supervisor), Information Extraction. |

## Answering strategy

1. Read the **last sentence** (what is being asked and under which constraint), then the scenario.
2. Underline the **evidence**: what is stale, missing, repeated, conflicting, or too long?
3. Name the **failure category** before you look at the options (e.g. "lost constraints during compaction").
4. Eliminate options that (a) don't touch that category, (b) break the stated constraint, or (c) are heavy-handed.
5. Flag and move on after 2 minutes. Come back at the end.
