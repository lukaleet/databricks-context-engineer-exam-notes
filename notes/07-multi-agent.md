---
id: d7
title: "Section 7: Multi-Agent and Long-Horizon Task Design"
weight: 13
---

# Section 7: Multi-Agent and Long-Horizon Task Design (13%)

> 🗺️ **Visual learner?** Dispatch with trace summaries, condensed sub-agent outputs, boundary placement and the long-horizon strategy chooser are drawn in the [Visual guide](#/notes/visual).

**Objectives**

1. Diagnose multi-agent failure modes caused by insufficient shared context: inconsistent outputs, conflicting decisions, degraded reliability
2. Given a coordinating agent that decomposed a task and dispatched sub-agents, and downstream failures, diagnose the root cause (sub-agents received individual task messages rather than full agent traces at dispatch) and select the configuration that resolves it without expanding each sub-agent's context window
3. Given a multi-agent system producing conflicting outputs, identify the context propagation change most likely to prevent the conflict
4. Given an orchestrator experiencing context saturation, identify the sub-agent output design change that most reduces orchestrator load without compromising coherence
5. Given agent boundaries that cause excessive handoff compression overhead or unmanageable context growth within agents, diagnose which boundary placement failure is occurring
6. Given a long-running task with documented failures, identify which long-horizon strategy mismatch causes them, select the replacement strategy for the task's dependency structure, and justify it

---

## 7.1 Why multi-agent, and what it costs

**Benefits:** each sub-agent has a **clean, focused context** (context quarantine); work can run **in parallel**; specialists can use
different tools and permissions. Breadth-first research is the classic win.

**Costs:** many more tokens overall, and **coordination failures**: a sub-agent sees only what you pass it. Every action carries
**implicit decisions** (style, assumptions, interpretations). When sub-agents can't see each other's decisions, their outputs conflict.

The two principles (Cognition, *Don't Build Multi-Agents*, 2025):

1. **Share context, and share full agent traces, not just individual messages.**
2. **Actions carry implicit decisions, and conflicting decisions carry bad results.**

The simplest design that respects both is a **single-threaded linear agent** with compaction for long tasks. Use multi-agent only
where subtasks really are independent.

## 7.2 Failure modes from insufficient shared context

| Symptom | What happened | Context propagation fix |
|---|---|---|
| **Inconsistent outputs** (different formats, terminology, assumptions) | each sub-agent got only its task line | dispatch with a **shared context brief**: goal, conventions, definitions, constraints |
| **Conflicting decisions** (two sub-agents choose incompatible designs) | implicit decisions made in parallel, never shared | share **decisions made so far** (trace summary) at dispatch; make dependent subtasks **sequential**; a single owner for shared decisions |
| **Degraded reliability** (works sometimes, fails on complex tasks) | context lost at every handoff | fewer handoffs, better boundaries (§7.5), richer handoff summaries |

## 7.3 Dispatching sub-agents: messages vs traces

**Failure:** the coordinator decomposes the task and sends each sub-agent **only its individual task message** ("build the bird"). The
sub-agent never sees the coordinator's reasoning, the user's constraints, or the other subtasks, so it guesses.

**Fix without expanding each sub-agent's context window:** attach a **compressed summary of the coordinator's trace** (the
relevant decisions, constraints, definitions and the overall plan) to each dispatch message. That gives the needed shared context
in a few hundred tokens, instead of the full raw trace (which would blow up every sub-agent's window).

[[diagram:dispatch]]

> **Read the evidence carefully.** In the official sample question, sub-agents' outputs were **mutually consistent but stale**, and
> their **retrieved context** referenced pre-update figures while the coordinator had the new ones. The cause was the **index not
> being synced**, not the dispatch. Consistent-but-wrong points to a **shared stale source**. Inconsistent-with-each-other points to
> **missing shared context**.

## 7.4 Orchestrator context saturation

Symptom: the orchestrator's window fills with sub-agent transcripts; it loses track of the plan and its quality drops.

**Fix by changing what sub-agents return:**

- a **condensed, structured result** (e.g. 1–2k tokens: findings, decisions, confidence, open issues) in a fixed schema
- **references instead of payloads**: write full results to a Delta table, volume or Lakebase row and return the **handle**
- **not** the full transcript or raw tool outputs

This reduces orchestrator load without losing coherence, because the orchestrator gets exactly what it needs to integrate results.
Truncating sub-agent outputs to N characters or dropping them is the wrong answer: it loses information arbitrarily.

## 7.5 Agent boundary placement

| Failure | Symptoms | Cause | Fix |
|---|---|---|---|
| **Boundaries too fine** | **excessive handoff compression overhead**: lots of summarizing between agents, details lost at each hop, coordination bugs | tightly coupled work split across many small agents | **merge** tightly coupled steps into one agent |
| **Boundaries too coarse** | **unmanageable context window growth inside one agent**, distraction, frequent compaction | one agent does many loosely related subtasks | **split** along loosely coupled subtasks with narrow interfaces |

Good boundaries follow **coupling**: put steps that share a lot of context in the same agent, and split where the interface between
parts is small (a clear input and a clear output).

[[diagram:boundaries]]

## 7.6 Long-horizon strategies and their fit

| Strategy | Fits tasks that… | Fails when… |
|---|---|---|
| **Compaction** | involve extensive back-and-forth and need conversational continuity in one thread | important state is exact and large (ids, per-item status); repeated compactions erode details |
| **Structured note-taking / external state** (progress file, todo list, Delta or Lakebase state table) | are iterative with **clear milestones**, or span sessions; exact progress tracking | — (needs the agent to write good notes) |
| **Sub-agent architecture** | have **independent, parallelizable** parts (broad research, many sources) | parts are **tightly sequential / interdependent**: decisions conflict, handoffs lose context |
| **Single linear agent** | strongly sequential tasks that fit in the window (with compaction) | the task is too big for one window |
| **Checkpoint and resume** (LangGraph checkpointer on Lakebase) | must survive interruptions, human-in-the-loop pauses | — |

[[diagram:long-horizon]]

**Diagnosing a strategy mismatch:** identify the task's **dependency structure** first.

- Sub-agents in parallel on steps that depend on each other → conflicting outputs → **sequential single agent with compaction or notes**.
- One agent compacting over and over on a 2,000-item batch job, losing which items are done → exact per-item state → **external
  state table / note-taking**.
- One agent researching 30 independent sources, window saturating → independent breadth → **sub-agents with condensed returns**.

The justification on the exam is always "**the specific characteristic** that makes the original strategy insufficient", for example
"items must be tracked exactly, and a summary can't hold exact per-item status".

## 7.7 On Databricks

- **Supervisor Agent** (Agent Bricks, formerly Multi-Agent Supervisor) routes to Genie spaces, Knowledge Assistants, UC functions,
  MCP servers and agent endpoints.
- Custom: LangGraph supervisor / agents-as-tools in a `ResponsesAgent`, deployed with Agent Framework.
- **MLflow tracing** shows each sub-agent's spans, so you can see exactly what context each one received at dispatch.
- Shared state for sub-agents: Lakebase (low latency) or Delta (batch, auditable).

### Quick self-check

- Two research sub-agents return reports with different definitions of "active customer". *(propagate a shared context brief / decisions at dispatch)*
- The orchestrator receives five 20k-token transcripts. *(sub-agents return condensed structured results + handles)*
- A pipeline of 12 tiny agents loses details at every hop. *(boundaries too fine → merge coupled steps)*
- Parallel sub-agents on tightly sequential refactoring steps conflict. Replacement? *(single sequential agent with compaction/notes)*
