---
id: plan
title: Study Plan & Hands-on Checklist
weight: 0
---

# Study plan

> **Want a day-by-day version?** Open the [Daily plan](#/plan): a 14-day checklist from **November 7** (the day after the GenAI exam)
> to the exam on **November 20**. Set the start date to November 7 so the dashboard's "Today" card lines up.

Two weeks is enough for an associate exam when a third of it is review. Spend the time where it's new:

| Priority | Sections | Why |
|---|---|---|
| **1. New and heavy** | §4 Memory (18 %), §1 Foundations (16 %) | 34 % of the exam, little overlap with the GenAI exam |
| **2. New, medium** | §7 Multi-agent (13 %), §5 Tools (13 %), §6 Compaction (11 %) | 37 %; concepts are simple once seen, the questions are diagnostic |
| **3. Review** | §3 Retrieval & Genie (20 %), §2 Instructions (9 %) | mostly known from GenAI; focus on Genie's knowledge store, UC metadata and authoritative sources |

**Daily rhythm (≈90–120 min):** 10 min flashcards → 45 min notes + diagram → 20–30 min lab → 20 min practice questions → 5 min
writing down what you got wrong and why.

**You're ready when** mock scores are steadily ≥ 80 %, and for every wrong option you can name the reason it's wrong: wrong
category, breaks the constraint, or heavy-handed.

## Before November 6 (optional, while you study for GenAI)

Don't study this exam yet. Two habits that help both exams:

- When you review GenAI retrieval, MCP, governance and evaluation, go one level deeper. Those topics count twice.
- Learn the current product names next to the old ones (AI Search = Vector Search). The GenAI notes already show them in brackets.

## Hands-on checklist

| # | Task | Where | Objectives |
|---|---|---|---|
| 1 | Measure what a context is made of; find the biggest low-signal element | Lab 00 | §1 |
| 2 | Diagnose four traces; run a needle test and find the knee | Lab 01 | §1 |
| 3 | Pick few-shot examples by coverage; run a prompt ablation in MLflow | Lab 02 (MLflow on Databricks) | §2 |
| 4 | In a Genie space: column description, synonym, SQL expression (measure, filter), example SQL, general instruction, benchmark | Databricks UI | §2, §3 |
| 5 | Tag a table `system.certification_status = certified` and another `deprecated`; search with `certificationStatus:certified` | Databricks UI / SQL | §3 |
| 6 | Recursive splitter, hybrid vs ANN, stale triggered index | Lab 03 | §3 |
| 7 | (Optional) Create an AI Search index; try `query_type="HYBRID"` and the reranker | Databricks | §3 |
| 8 | Checkpointer by `thread_id`, long-term store by user, memory routing, state table | Lab 04 (Lakebase if available) | §4 |
| 9 | Compare MLflow runs with the **parallel coordinates** chart | MLflow UI | §4 |
| 10 | Progressive disclosure token math, overlapping tool descriptions, result clearing, skills | Lab 05 | §5 |
| 11 | Sliding window vs compaction prompts; recall then precision | Lab 06 (real model on Databricks) | §6 |
| 12 | Dispatch with trace summary, condensed returns, boundaries, strategy fit | Lab 07 | §7 |
