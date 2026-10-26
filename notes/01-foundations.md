---
id: d1
title: "Section 1: Foundations of Context Engineering"
weight: 16
---

# Section 1: Foundations of Context Engineering (16%)

> 🗺️ **Visual learner?** The context window, failure modes and degradation curve are drawn in the [Visual guide](#/notes/visual).

**Objectives**

1. Given a described agent failure, identify the context management technique that would most directly address it
2. Given a Databricks agent design, identify which proactive context management strategies (minimal tool sets, just-in-time retrieval, tool result scoping) would reduce context window pressure before compaction becomes necessary
3. Diagnose context failure modes (context poisoning, distraction, confusion, clash) given an agent trace
4. Select the right tool in the Databricks product stack (Unity Catalog, Lakebase, MCP, MLflow 3) for a given scenario
5. Identify which context elements consume disproportionate attention budget and select the change most likely to improve model focus
6. Select the appropriate reasoning mode (standard, extended thinking, reduced thinking) based on token budget and context window impact
7. Identify the point at which context length causes measurable degradation, and select the intervention that restores performance

---

## 1.1 What "context" means

**Context** is *everything* the model sees on one inference call, not only your prompt:

| Element | Example | Who controls it |
|---|---|---|
| System prompt / instructions | role, rules, output format | you, static |
| Tool definitions | names, descriptions, JSON schemas of every tool the agent can call | you, static or loaded on demand |
| Few-shot examples | 2–5 input → output demonstrations | you, static |
| Retrieved knowledge | chunks from AI Search, rows from Genie or SQL | retrieval step / tools, dynamic |
| Memory | session history (short-term), user facts (long-term) | memory layer, dynamic |
| Message history | user turns, assistant turns, **tool calls and tool results** | grows every turn |
| Other agents' output | sub-agent summaries, handoff messages | orchestration |

**Prompt engineering** is writing good instructions. **Context engineering** is choosing, at every step, the *smallest set of
high-signal tokens* from all of the above that lets the model do the task. It's an ongoing, per-turn decision, not a one-time text.

[[diagram:context-anatomy]]

## 1.2 Attention budget and context rot

- **Attention budget.** Each token attends to every other token (n² pairs for n tokens). Like working memory, attention is finite:
  every extra token dilutes the attention that the important tokens get.
- **Context rot.** Recall and reasoning accuracy **drop as the context grows**, on every model, *long before* the hard limit.
  The "effective" window is much smaller than the advertised one.
- **Lost in the middle.** Information in the middle of a long context is used less reliably than the start or end.

> **Exam rule:** a bigger context window is **not** a fix for degradation. It only delays the hard error. The fix is to put *fewer, better*
> tokens in the window (compaction, clearing, retrieval scoping, sub-agents).

## 1.3 The four context failure modes

These names come from Drew Breunig's *How Long Contexts Fail* (2025) and are used exactly this way on the exam.

| Failure mode | Definition | Trace signature | Most direct fix |
|---|---|---|---|
| **Context poisoning** | A **hallucination or error enters the context** and is then **referenced repeatedly** | an early wrong "fact" (often in the agent's own summary, plan or notes) keeps reappearing in later steps; the agent pursues impossible goals | remove / quarantine the bad content, validate before writing to memory or summaries, start a fresh context from verified state |
| **Context distraction** | The context grows so long that the model **over-focuses on the context and neglects what it learned in training** | in long sessions the agent repeats past actions from history instead of making a new plan | summarization / compaction, keep the window short |
| **Context confusion** | **Superfluous** content (irrelevant docs, unneeded tools, old session history) **is used** to generate a low-quality response | the answer cites or mixes in material that is irrelevant to the task; wrong tool picked from too many tools | remove the irrelevant content: tool loadout, better retrieval scoping, pruning |
| **Context clash** | New information or tools **conflict** with information already in the context | two instructions or sources disagree; an early wrong attempt stays in the history and the model can't recover | prune the outdated / conflicting part, resolve which source wins, restart with a consolidated context |

[[diagram:failure-modes]]

**How to tell them apart on a trace:**

- Is the bad content **wrong** (made up, error) and **reused**? → **poisoning**.
- Is the content **correct but irrelevant**, and it **leaks into the answer**? → **confusion**.
  (Official sample: a previous session's licensing agreement left in context, and the answer drifts into its terms.)
- Are two pieces of content **contradicting each other**? → **clash**.
- Is the context simply **very long** and the agent **repeating history** instead of reasoning? → **distraction**.

## 1.4 Fixes, matched to the failure

| Technique | What it does | Fixes mainly |
|---|---|---|
| **RAG / just-in-time retrieval** | add only the relevant knowledge, when needed | confusion |
| **Tool loadout** | give the model only the tools relevant to the task (e.g. retrieve tools by description) | confusion (quality drops with many tools; tens of tools is already risky) |
| **Context quarantine** | isolate work in separate threads / sub-agents with their own context | distraction, confusion, poisoning spreading |
| **Context pruning** | remove irrelevant or outdated content | confusion, clash |
| **Summarization / compaction** | replace a long history with a faithful summary | distraction, window pressure |
| **Context offloading** | store notes, plans, intermediate results outside the window (scratchpad file, state table) | distraction, confusion |

## 1.5 Proactive strategies (before compaction is needed)

Compaction is **reactive**: it runs when the window is already under pressure. The exam wants you to also know the **proactive**
design choices that keep the window small from the start:

| Strategy | What it means in a Databricks agent |
|---|---|
| **Minimal tool sets** | register only the tools this agent needs; split big toolboxes across sub-agents; use progressive disclosure for MCP servers with many tools |
| **Just-in-time retrieval** | keep lightweight references (table names, doc ids, query templates) and load data with tools when needed, instead of stuffing documents up front |
| **Tool result scoping** | tools return **only the fields and rows the agent needs**: filters, `LIMIT`, pagination, projections, a summary instead of raw JSON |
| **Concise instructions** | right-altitude system prompt, no duplicated rules |
| **Skills** | rarely used procedures live in skills that load on demand, not in the system prompt |
| **Sub-agents** | heavy exploration happens in a sub-agent's own window; only a condensed result returns |

[[diagram:proactive-reactive]]

> **Exam pattern:** "which strategy reduces window pressure *before compaction becomes necessary*?" → pick a proactive one
> (minimal tools, JIT retrieval, result scoping). Compaction, trimming and clearing are the *reactive* answers.

## 1.6 The Databricks product stack: which tool for which job

| Need | Product | Why |
|---|---|---|
| Govern data, tools and models; find authoritative assets; PII masks; metadata the agent reads | **Unity Catalog** | permissions, comments/descriptions, tags (e.g. `system.certification_status`), lineage, UC functions as tools |
| Low-latency per-turn reads/writes: conversation checkpoints, user memories, task state | **Lakebase** (managed Postgres) | OLTP: millisecond row reads/writes. Delta tables are for analytics and batch, not per-turn chat state. |
| Connect the agent to tools and data sources through a standard protocol | **MCP** (managed, external, custom servers) | managed servers for UC functions, AI Search, Genie, DBSQL; external through UC connections; custom on Databricks Apps |
| Trace what entered the context, evaluate whether a change helped, compare configurations | **MLflow 3** | tracing, `mlflow.genai.evaluate`, judges/scorers, experiments and run comparison, prompt registry |
| Semantic retrieval over documents (and memories) | **AI Search** | ANN, hybrid, full-text, reranker, Delta Sync indexes |
| Natural-language questions over structured tables | **Genie space** | instructions, SQL expressions, example SQL, trusted assets over curated UC tables |

## 1.7 Finding what eats the attention budget

When a question gives you a configuration and asks what to change to "improve model focus", look for the **largest low-value
block**:

| Usually disproportionate | Better alternative |
|---|---|
| 40–100 full tool schemas loaded every turn | tool loadout / progressive disclosure |
| raw tool outputs (full JSON, 500 rows, whole files) kept in history | scope results, clear old results |
| long lists of edge-case rules in the system prompt | a few principles + diverse canonical examples |
| 15 few-shot examples showing the same path | 2–4 examples covering *different* paths |
| top-k = 20 overlapping chunks | lower k, rerank, dedupe |
| a whole previous session's transcript | a short, relevant summary or long-term memory facts |

The right answer removes or shrinks the **biggest low-signal element**, not the small, high-signal one (e.g. the task definition).

## 1.8 Reasoning modes and token budget

Reasoning ("thinking") tokens are generated **output tokens**. They cost money and latency, count against `max_tokens`, and if kept in
the conversation history they also take space in later turns.

| Mode | When to choose it |
|---|---|
| **Standard** (no thinking) | simple, well-specified steps: routing, classification, extraction, single lookups; latency-sensitive, high volume |
| **Extended thinking** | hard multi-constraint reasoning, planning, ambiguous analysis, math; few turns; quality matters more than tokens |
| **Reduced thinking** (low effort / small budget) | long agent loops with many tool calls where some reasoning helps but the window and cost are tight |

On Databricks Foundation Model APIs:

```python
# Hybrid reasoning models (e.g. Claude): a thinking budget, must be < max_tokens
client.chat.completions.create(
    model="databricks-claude-sonnet-4-5", messages=msgs, max_tokens=8000,
    extra_body={"thinking": {"type": "enabled", "budget_tokens": 4000}})

# Reasoning-only models (e.g. GPT OSS, Gemini 3): an effort level
client.chat.completions.create(model="databricks-gpt-oss-120b", messages=msgs, reasoning_effort="low")
```

> **Exam pattern:** a long-running agent hits the window limit sooner after someone turned on extended thinking with a large budget
> on every step → reduce the thinking budget / effort (or enable it only on planning steps), don't buy a bigger window.

## 1.9 Detecting degradation and restoring performance

**How to find the point of degradation:** use MLflow traces. Log the context size (tokens) per turn, then plot an evaluation metric
(correctness, groundedness, retrieval relevance, tool-call correctness) against context fill. Quality usually holds steady and then
**drops past a "knee"**, e.g. around 60–80 % of the window, before any hard limit.

[[diagram:degradation]]

**Interventions, from lightest to heaviest:**

1. **Tool result clearing:** drop old raw tool outputs that were already used.
2. **Trimming:** drop the oldest turns, or keep only the last *N* turns. This is cheap but **loses early facts**.
3. **Compaction:** summarize the history into a high-fidelity summary, then continue with the summary plus the most recent items.
   This **keeps the facts** and restores focus. It's the official answer when the requirement is "keep one uninterrupted session
   and don't discard retrieved facts".
4. **Structured notes / external memory:** write progress and decisions to a state store and reload them.
5. **Sub-agents:** move exploration out of the main window.

Trigger the intervention **before the knee** (e.g. compact at ~70 %), not at the hard limit.

### Quick self-check

- An agent's answer mixes in clauses from a previous customer's contract that is still in the history. Which failure mode is this? *(confusion)*
- An agent wrote a wrong order total into its own scratchpad in step 3 and keeps using it. Which mode? *(poisoning)*
- Name three proactive strategies. *(minimal tool set, JIT retrieval, tool result scoping)*
- Quality drops at 75 % of the window and the session must continue. Bigger model, sliding window, or compaction? *(compaction)*
