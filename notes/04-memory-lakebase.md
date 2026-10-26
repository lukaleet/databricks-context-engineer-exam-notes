---
id: d4
title: "Section 4: Memory Architecture with Lakebase and MLflow"
weight: 18
---

# Section 4: Memory Architecture with Lakebase and MLflow (18%)

> 🗺️ **Visual learner?** The memory layers, the memory query router and intent-before-retrieval are drawn in the [Visual guide](#/notes/visual).
> This section is **new** compared to the GenAI exam. Give it the most study time.

**Objectives**

1. Given an agent whose context is populated from the wrong memory source (long-term storage when the info is in the current session, or session history when the need is cross-session), identify the mismatch and select the correct memory strategy
2. Identify when a Delta-backed state object is required over an in-context scratchpad for a multi-step task
3. Given an agent retrieving memories persisted in Lakebase, identify whether AI Search or structured query retrieval fits a query type
4. Given MLflow 3 experiment results across multiple runs, identify which context configuration produced the most reliable outcomes
5. Evaluate the tradeoffs of static vs dynamic retrieval from Lakebase
6. Diagnose risks of over-retrieval (context pollution) and under-retrieval (missing history)
7. Configure persistent agent memory across sessions using a Lakebase-backed durable store
8. Given a pipeline producing accurate but contextually mismatched responses, identify the stage where user intent should be resolved before context retrieval

---

## 4.1 The memory layers

| Layer | What it holds | Lifetime | Where on Databricks |
|---|---|---|---|
| **Working memory** (in-context) | the current messages, tool results, scratchpad notes inside the window | this call / until trimmed | the context window |
| **Short-term / session memory** | the full state of **one conversation thread** (messages, graph state) so it can continue or resume | one session (thread) | LangGraph **checkpointer** on **Lakebase**, keyed by `thread_id` (or Agent *sessions*) |
| **Long-term memory** | durable facts, preferences, decisions, procedures about a user/team, reused **across sessions** | months | LangGraph **store** on **Lakebase** (`DatabricksStore`), namespaced by user; or Agent *memory* stores |
| **Task state** | structured progress of a long multi-step job: which items are done, intermediate results, decisions | the job (may span runs) | a **Delta table** or Lakebase table (a state object) |
| **Knowledge** (not "memory") | documents, policies, product data | as long as the corpus | AI Search indexes, Genie, UC tables |

Memory research names: **episodic** (what happened in a session), **semantic** (facts), **procedural** (how to do things).
Databricks' docs call the session store *episodic* memory and the long-term store *derived* memory.

[[diagram:memory-layers]]

## 4.2 Memory-source mismatches

| Symptom | Mismatch | Correct strategy |
|---|---|---|
| User says "as I said a minute ago…" and the agent searches long-term memory, retrieves an old, different preference | retrieving from **long-term** when the info is **in the current session** | use the session history / checkpoint first; long-term only for cross-session needs |
| Every new chat, the agent asks again for the user's preferred currency and region | relying on **session history** for info that needs **cross-session persistence** | write durable facts to the **long-term store** (per-user namespace) and recall them at session start |
| Resumed conversation after a crash starts from scratch | no checkpointer, or a new `thread_id` | persist the thread with a checkpointer and reuse the same `thread_id` |
| Agent "remembers" another user's preferences | wrong namespace / scope | namespace memories by the **verified user id** from trusted app context |
| Agent loses track of which of 500 invoices it already processed | progress kept only in context | a **state table** (Delta/Lakebase) |

## 4.3 Delta-backed state object vs in-context scratchpad

Use a **durable state object** (a Delta table, or a Lakebase table for low-latency updates) instead of an in-context scratchpad when
**any** of these hold:

- the task has **many items or steps** (the progress list wouldn't fit, or would crowd the window)
- it must **survive failures, restarts or multiple runs / sessions** (resume where it stopped)
- **several agents or jobs** read and update the same progress
- you need **auditability** (who did what, when) or analytics over progress
- progress must be **exact** (counts, statuses, ids); summarizing it would lose precision

An **in-context scratchpad** is fine for a short, single-session reasoning task whose notes fit easily and don't need to outlive it.

## 4.4 Lakebase in one paragraph

**Lakebase** is Databricks' managed **Postgres** (OLTP) database, governed in Unity Catalog. It serves fast single-row reads and writes,
which is what an agent needs on every turn (load the thread, append a message, look up a memory). Delta tables are for analytics
and large batch reads. Lakebase tables can be synced from or to Delta. Two flavours exist (Provisioned instances and Autoscaling
projects); the `databricks-langchain` memory classes support both.

## 4.5 Configuring persistent memory with LangGraph on Lakebase

**Short-term (thread checkpoints):**

```python
# pip install "databricks-langchain[memory]"
from databricks_langchain import CheckpointSaver          # LangGraph PostgresSaver on a Lakebase pool

with CheckpointSaver(instance_name="agent-memory") as checkpointer:
    checkpointer.setup()                                    # creates the checkpoint tables once
    graph = builder.compile(checkpointer=checkpointer)
    graph.invoke({"messages": [("user", "Hi, I'm Ana")]},
                 config={"configurable": {"thread_id": "t-42"}})   # same thread_id = same conversation
```

**The async version** (agent running in an async environment, as in the official sample question):

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

checkpointer = AsyncPostgresSaver(pool)      # pool = async connection pool to the Lakebase instance
await checkpointer.setup()                   # async: must be awaited; creates the schema
graph = builder.compile(checkpointer=checkpointer)
```

`databricks_langchain.AsyncCheckpointSaver(instance_name=...)` wraps the same thing and builds the async Lakebase pool for you
(`async with … as checkpointer: await checkpointer.setup()`).

> **Traps:** there is no `AsyncCheckpointer` class in LangGraph; `setup()` on the async saver is a coroutine (**await** it, don't call it
> synchronously); schemas aren't auto-migrated on first write, so you call `setup()`; the checkpointer goes into
> `compile(checkpointer=...)`, not into `invoke`.

**Long-term (cross-session store with semantic search):**

```python
from databricks_langchain import DatabricksStore

store = DatabricksStore(instance_name="agent-memory",
                        embedding_endpoint="databricks-gte-large-en", embedding_dims=1024)
store.setup()
ns = ("memories", user_id.replace(".", "_"))               # trusted user id; namespace labels can't contain "."
store.put(ns, "currency", {"text": "Prefers reports in EUR"})
hits = store.search(ns, query="reporting preferences", limit=3)   # pgvector similarity in Lakebase
graph = builder.compile(checkpointer=checkpointer, store=store)
```

**Serving it:** pass the conversation id as `custom_inputs={"thread_id": ...}` (Databricks clients such as the Playground and Review
App send conversation and user ids automatically). When logging the agent, declare the database as a resource:
`mlflow.models.resources.DatabricksLakebase(database_instance_name="agent-memory")`.

**Newer managed option (Beta, after the exam guide):** Databricks now also offers managed **agent sessions** (short-term),
**agent memory** stores (long-term, searched with BM25 + semantic) and **memory pipelines** that distill sessions into memory on a
schedule, all backed by Lakebase. Know they exist; the exam guide's objectives are written around Lakebase + LangGraph.

## 4.6 AI Search or a structured query for memories?

| Query type | Mechanism | Why |
|---|---|---|
| "What does this user like / prefer / care about regarding X?" | **semantic search** (AI Search index, or the store's embedding search) | fuzzy meaning, wording differs from how it was stored |
| "Summarize what we discussed about the migration" (free text) | **semantic search** | similarity over text |
| "Last 5 orders", "status of ticket 1182", "memories created this week", "how many times did…" | **structured SQL query** on Lakebase | exact keys, filters, ordering, counts. Embeddings are bad at exact ids, dates and aggregates |
| "Preference with key `language`" | **key lookup** (`store.get(ns, "language")`) | you know the key |

[[diagram:memory-router]]

## 4.7 Static vs dynamic retrieval from Lakebase

| | **Static** (load at session start) | **Dynamic** (agent queries memory when needed) |
|---|---|---|
| What | a fixed profile / set of memories is inserted into every prompt | a memory tool or retrieval step per turn, based on the current need |
| Pros | simple, predictable latency, always available | relevant and fresh, no tokens wasted when not needed, scales to large memories |
| Cons | tokens on every call, may be **irrelevant (pollution)** or **stale** within a long session | extra latency/tool calls; if the agent doesn't ask, it **misses** history; depends on good queries |
| Fits | small, always-relevant profile (name, language, role) | large or growing memory, varied topics, long sessions |

Common answer: **small static core + dynamic recall** for everything else.

## 4.8 Over-retrieval vs under-retrieval

| | **Over-retrieval** (context pollution) | **Under-retrieval** (missing history) |
|---|---|---|
| Symptom | answers mix in old or unrelated memories, contradictions, higher cost, distraction | agent re-asks known facts, contradicts earlier decisions, "forgets" the user |
| Causes | top-k too high, no relevance threshold, no recency weighting, too broad a namespace, duplicated memories | memories never written, k too low, strict filters, poor queries, wrong namespace |
| Fixes | lower k, similarity threshold, recency / importance weighting, scope by user/topic, **consolidate and dedupe** memories, expire stale ones | write salient facts at the right time, query rewriting, raise k or loosen filters, recall at session start |

## 4.9 Resolve intent **before** retrieval

Symptom: responses are **accurate but contextually mismatched**. The facts are right but answer a different question
("What's the limit?" answered with the *credit card* limit while the user was talking about the *API* rate limit).

Cause: retrieval ran on the **raw message**. The pipeline needs an **intent-resolution / query-understanding stage** *before* retrieval
that uses the session context to: resolve references ("it", "that one"), identify the entity and domain, fill scope (time range,
product), and rewrite the query. Only then retrieve.

[[diagram:intent-first]]

## 4.10 Picking the most reliable context configuration with MLflow 3

Run each configuration (chunk size, k, memory strategy, prompt) in **one experiment** on the **same evaluation dataset**, logging the
same metrics (e.g. `answer_correctness`, `context_recall`, `faithfulness`), ideally **several runs per configuration** (LLMs are
non-deterministic).

- "Most reliable" = **high on all metrics, none lagging**, and **stable across repeated runs**.
- Use the **parallel coordinates chart** (or the run comparison table) to see which run stays high on every axis.
- Don't pick by the **mean** (hides a weak metric), by the **single best metric** (could fail on another), or by the **smallest
  spread** alone (could be uniformly mediocre).

```python
import mlflow
for cfg in configs:
    with mlflow.start_run(run_name=cfg.name):
        mlflow.log_params(cfg.params)
        mlflow.genai.evaluate(data=eval_ds, predict_fn=make_agent(cfg), scorers=scorers)
# MLflow UI → select runs → Compare → Parallel coordinates
```

### Quick self-check

- The agent asks every Monday which warehouse the user manages. *(long-term memory, per-user namespace)*
- Async LangGraph + Lakebase: the three steps? *(`AsyncPostgresSaver(pool)`, `await setup()`, `compile(checkpointer=…)`)*
- "How many refunds did this customer request in Q3?" from memories: AI Search or SQL? *(SQL)*
- A batch agent must process 10,000 contracts over several nights. Scratchpad or state table? *(Delta state table)*
