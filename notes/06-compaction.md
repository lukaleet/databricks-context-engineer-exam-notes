---
id: d6
title: "Section 6: Context Compression and Compaction"
weight: 11
---

# Section 6: Context Compression and Compaction (11%)

> 🗺️ **Visual learner?** The compaction ladder, what survives compaction and the prompt-tuning loop are drawn in the [Visual guide](#/notes/visual).

**Objectives**

1. Given a compacted long-running task with downstream coherence failures, identify which category of information was incorrectly discarded and select the compaction prompt revision that preserves it without significantly increasing token cost
2. Tune a compaction prompt for an agent trace: maximize recall first, then iterate to improve precision
3. Given building window pressure, evaluate whether hard-coded trimming heuristics suffice for the task's information-relevance pattern, or a more sophisticated compaction approach is needed
4. Given an agent trace, identify which content is safe to remove during compaction without affecting downstream execution
5. Evaluate the tradeoffs between aggressive compaction (lower cost, risk of losing subtle context) and conservative compaction (higher fidelity, higher cost)

---

## 6.1 The compression ladder

From cheapest and safest to most powerful:

| Technique | How | Loses |
|---|---|---|
| **Tool result clearing** | replace old raw tool outputs with stubs | only re-fetchable raw data |
| **Trimming heuristics** | hard-coded rules: keep the system prompt + last *N* turns, drop the oldest, cap each message, sliding window | **anything old**, relevant or not |
| **Compaction (summarization)** | an LLM summarizes the history into a structured summary; continue with *system prompt + summary + most recent items* | whatever the summary prompt doesn't ask for |
| **Offloading / structured notes** | the agent keeps notes, plans, decisions in a file or state table outside the window and reloads them | nothing, if it writes the right things |
| **Sub-agents** | exploration happens in another window; only a condensed result returns (see §7) | details of the sub-agent's exploration |

[[diagram:compaction-ladder]]

## 6.2 Is trimming enough?

Decide by the task's **information-relevance pattern**:

| Relevance pattern | Example | Trimming enough? |
|---|---|---|
| **Recency-local**: only the last few turns matter; old turns are finished business | a help-desk chat where each question is independent; monitoring a stream of alerts | **Yes.** A sliding window is cheap and safe |
| **Early information stays relevant**: constraints, goals, decisions stated early are needed later | a research task where the user excluded sources in turn 2; a migration where decisions in step 5 constrain step 40 | **No.** Trimming silently drops them → **compaction** (or notes) |
| **Scattered dependencies**: any earlier result may be needed | a long investigation referencing many earlier findings | **No.** Compaction with key facts and identifiers, or a structured state store |

> **Exam pattern:** "after 40 turns the agent violates a constraint the user stated at the start, and the team uses a sliding window"
> → trimming is insufficient for this relevance pattern; use compaction that preserves constraints.

## 6.3 What a good compaction keeps

| Keep (high value, usually small) | Safe to remove |
|---|---|
| the **user's goal** and success criteria | raw tool outputs whose findings are already captured |
| **constraints, exclusions and preferences** the user stated | pleasantries, acknowledgements, repeated confirmations |
| **decisions made, with a one-line rationale** | superseded plans and drafts |
| **current progress**: done / in progress / next steps | redundant retries and duplicate retrievals (keep the *lesson*: "approach X failed because Y") |
| **identifiers**: ids, file paths, table names, record keys, URLs | verbose intermediate reasoning (chain-of-thought) |
| **open questions and unresolved errors** | exploratory dead-ends with no lasting outcome |
| key **facts discovered, with sources** | full text of documents that can be re-retrieved |
| the **last few messages verbatim**, and any pending tool call with its result | |

Never split a tool **call** from its **result** when cutting the history. Most APIs reject or confuse an orphaned tool result.

[[diagram:compaction-keep]]

## 6.4 Diagnosing coherence failures after compaction

When something goes wrong **after** a compaction, the symptom tells you which **category** the summary dropped:

| Symptom after compaction | Category lost | Revision to the compaction prompt |
|---|---|---|
| Contradicts earlier decisions or user requirements | **constraints / exclusions / preferences / decisions** | "Include a deduplicated list of constraints, exclusions and preferences the user stated, and decisions made" |
| Redoes work already done | **progress / task state** | "List completed steps and their outcomes" |
| Uses wrong or made-up ids, paths | **identifiers** | "Preserve all ids, paths and names exactly" |
| Retries an approach that already failed | **negative results** | "Record failed approaches and why they failed" |
| Loses the thread of an unanswered question | **open items** | "List open questions and next steps" |

The right fix adds **that category, in a compact, structured, deduplicated form**. "Append all user messages verbatim", "include all
tool outputs" or "include the full chain-of-thought" would also fix it, but at a large token cost. That is the exam's distractor.

**Official sample-question lesson:** prompt was *"Summarize the key facts and findings discovered so far."* The agent then contradicted
earlier decisions → add **a deduplicated list of constraints, exclusions and preferences the user has stated**.

## 6.5 Tuning a compaction prompt: recall first, then precision

1. **Maximize recall.** Start with a prompt that captures *everything* that could matter (goals, constraints, decisions, progress,
   ids, errors, open items, facts with sources). Run it on real, long agent traces and check that the agent **still completes the
   downstream task** after compaction. Fix every case where something needed went missing.
2. **Then improve precision.** Iteratively remove what the agent never needs afterwards (raw outputs, chatter, duplicate facts) and
   re-check that task success holds. Stop when removing more starts hurting.
3. Measure both sides: **task success / coherence after compaction** (MLflow evaluation on the compacted traces) and **summary token
   count**.

[[diagram:compaction-tuning]]

Why this order: a summary that is short but misses a constraint fails silently later and is hard to debug; extra tokens are a visible,
cheap problem you can trim afterwards.

## 6.6 Aggressive vs conservative compaction

| | **Aggressive** | **Conservative** |
|---|---|---|
| How | compact early and often, short summaries, small "recent" tail | compact late, detailed summaries, larger verbatim tail |
| Pros | lowest tokens and cost, maximum focus | high fidelity, subtle context survives |
| Cons | loses subtle context (tone, nuances, implicit decisions), compounding loss over repeated compactions | more tokens, compaction happens closer to the degradation knee |
| Fits | repetitive, recency-local tasks; cost-sensitive high volume | high-stakes tasks with long-range dependencies (legal, compliance, migrations) |

A good middle: trigger at a threshold **before** the degradation knee (e.g. ~70–80 % of the window), keep a structured summary plus
the last few turns, and offload exact state (ids, progress) to a store instead of the summary.

### Quick self-check

- Sliding window on a 3-hour data-migration agent; after a while it re-creates tables it was told never to touch. Why and fix? *(trimming dropped an early constraint → compaction that preserves constraints)*
- Which is safe to remove: the raw 300-line `DESCRIBE` output from turn 4 (findings noted in turn 5), or the table names chosen in turn 6? *(the raw output)*
- First step when tuning a compaction prompt? *(maximize recall)*
