---
id: bridge
title: GenAI → Context Engineer Bridge
weight: 0
---

# GenAI → Context Engineer bridge

You take the **GenAI Engineer Associate** exam on **November 6** and the **Context Engineer Associate** on **November 20**. This page
tells you what carries over, so the two weeks in between go to what's new.

## How much carries over

| Context Engineer section | Weight | Overlap with GenAI prep | Where you learned it |
|---|---|---|---|
| §1 Foundations | 16 % | **low**: failure modes, attention budget, reasoning modes are new; the product map is familiar | GenAI §1 (Agent Bricks, tools) |
| §2 System prompts & instructions | 9 % | **medium**: prompt design yes; Genie knowledge store and ablation are new | GenAI §1.1, §3.5, §3.13 |
| §3 Retrieval & Genie | 20 % | **high**: chunking, AI/Vector Search, hybrid, reranker, sync modes, RAG pipeline | GenAI §2, §4.4 |
| §4 Memory (Lakebase, MLflow) | 18 % | **low**: Lakebase checkpointers and stores are new; MLflow evaluation is familiar | GenAI §3.10, §6 |
| §5 Tools & MCP | 13 % | **medium**: MCP servers and UC functions yes; progressive disclosure, clearing, skills are new | GenAI §1.5, §4.10 |
| §6 Compaction | 11 % | **none** | — |
| §7 Multi-agent & long-horizon | 13 % | **low**: you know the Supervisor; context propagation is new | GenAI §1.6, §3.13 |

Rough total: about **a third** of the exam is review; **two thirds** is new material, concentrated in §1, §4, §6 and §7.

## What to skim (you already know it)

- Chunking strategies and overlap, embedding context length → skim [§3.7](#/notes/d3)
- AI Search index types, triggered vs continuous, hybrid and reranking → skim [§3.5](#/notes/d3)
- MCP server types (managed, external, custom) → skim [§5.7](#/notes/d5)
- MLflow evaluation and judges → skim [§4.10](#/notes/d4)

## What to study properly (new)

1. **Failure modes** (poisoning, distraction, confusion, clash) and **proactive vs reactive** strategies → [§1](#/notes/d1)
2. **Genie knowledge store**: SQL expressions, entity matching, trusted assets, *sample questions don't teach* → [§2.4](#/notes/d2)
3. **UC metadata and authoritative sources**: certification tags, deprecating derived assets → [§3.3, §3.9](#/notes/d3)
4. **Memory**: session vs long-term vs state, Lakebase checkpointers and stores, static vs dynamic, over/under-retrieval,
   intent before retrieval → [§4](#/notes/d4)
5. **Progressive disclosure, tool result clearing, Agent Skills** → [§5](#/notes/d5)
6. **Compaction**: what to keep, recall-then-precision, trimming vs compaction → [§6](#/notes/d6)
7. **Multi-agent context**: trace summaries at dispatch, condensed returns, boundary placement, long-horizon strategy fit → [§7](#/notes/d7)

## Names: switch from the GenAI exam's names to the current ones

The GenAI exam (March 2026 guide) uses the older names. This exam (July 2026 guide) uses the newer ones. After November 6, switch:

| GenAI exam said | Context Engineer exam says |
|---|---|
| Vector Search | **AI Search** |
| Genie space | Genie space (docs now also say **Genie Agent**) |
| Multi-Agent Supervisor | **Supervisor Agent** |
| (not covered) | **Lakebase**, Agent Skills, compaction, context failure modes |

## The mindset shift

The GenAI exam asked **"which component do you use?"** The Context Engineer exam asks **"what exactly should be in the model's
window at this step, and what went wrong when it wasn't?"** Think in terms of tokens: what entered, what was missing, what was noise,
and what is the smallest change that fixes it.
