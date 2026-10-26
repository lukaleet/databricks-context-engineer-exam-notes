# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 07: Multi-agent context: dispatch, returns, boundaries and long-horizon strategy
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §7 Diagnose failures caused by sub-agents receiving individual task messages instead of the coordinator's trace, and fix it without expanding their windows
# MAGIC - §7 Identify the sub-agent output design change that reduces orchestrator context load
# MAGIC - §7 Diagnose boundary placement failures (handoff overhead vs context growth)
# MAGIC - §7 Select the long-horizon strategy that fits a task's dependency structure
# MAGIC
# MAGIC **Time:** ~30 min · **Runs:** locally or on Databricks (with a model, Step 1 uses real sub-agent calls)

# COMMAND ----------
# %%
# ---- shared helper cell (identical in every lab) ----
import os, re, json
ON_DATABRICKS = ("DATABRICKS_RUNTIME_VERSION" in os.environ or "dbutils" in globals()
                 or os.path.isdir("/Workspace") or os.path.isdir("/databricks"))
PREFERRED = ["databricks-claude-sonnet-4-5", "databricks-claude-3-7-sonnet", "databricks-meta-llama-3-3-70b-instruct",
             "databricks-gpt-oss-120b", "databricks-llama-4-maverick"]
MODEL, _client = None, None
if ON_DATABRICKS:
    try:
        from databricks.sdk import WorkspaceClient
        _w = WorkspaceClient()
        _client = _w.serving_endpoints.get_open_ai_client()
        _names = [e.name for e in _w.serving_endpoints.list()]
        MODEL = next((m for m in PREFERRED if m in _names), None) or next(
            (n for n in _names if n.startswith("databricks-") and any(k in n for k in ("claude", "llama", "gpt"))), None)
    except Exception as e:  # missing openai package, no permission, ...
        print("LLM unavailable, using the offline stand-in:", type(e).__name__, e)


def tokens(x):
    """Rough token estimate (~4 characters per token for English). Good enough to compare context elements."""
    return max(1, round(len(x if isinstance(x, str) else json.dumps(x)) / 4))


def llm(messages, max_tokens=600):
    """Call the Foundation Model endpoint, or return None when running offline."""
    if not MODEL:
        return None
    r = _client.chat.completions.create(model=MODEL, messages=messages, max_tokens=max_tokens, temperature=0)
    return r.choices[0].message.content


print(f"Databricks={ON_DATABRICKS} | model={MODEL or 'offline stand-in'}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: Dispatching sub-agents with task messages vs a trace summary
# MAGIC The coordinator talked with the user for 30 turns and made decisions. Then it splits a churn report into three sub-tasks.
# MAGIC Compare what the sub-agents produce when they get **only their task line** vs the task line **plus a compressed trace summary**.

# COMMAND ----------
# %%
COORDINATOR_TRACE = ("30 turns with the user ... " * 150 +
                     "Decided: 'active customer' = at least one order in the last 90 days. Currency: EUR. "
                     "Period: Q3 2026. Exclude the B2B segment. Output: one table per region, same columns.")
TASKS = ["Compute churn for region EMEA.", "Compute churn for region AMER.", "Compute churn for region APAC."]
SUMMARY = ("Shared context: active customer = >=1 order in last 90 days; currency EUR; period Q3 2026; exclude B2B; "
           "columns: region, active_start, churned, churn_rate.")
ASSUMPTIONS = {"active": ["30 days", "90 days", "12 months"], "currency": ["USD", "EUR", "local"], "b2b": ["included", "excluded"]}


def sub_agent(task, context=""):
    if MODEL:
        return llm([{"role": "system", "content": "You are a sub-agent. State in one line the definition of active customer, "
                                                  "the currency, and whether B2B is included, that you will use."},
                    {"role": "user", "content": (context + "\n" if context else "") + task}], max_tokens=80)
    seed = sum(map(ord, task)) % 3                           # stand-in: without shared context each one guesses differently
    if "active customer =" in context:
        return "active=90 days, currency=EUR, B2B excluded"
    return f"active={ASSUMPTIONS['active'][seed]}, currency={ASSUMPTIONS['currency'][seed]}, B2B {ASSUMPTIONS['b2b'][seed % 2]}"


for label, ctx in [("task message only", ""), ("task + trace summary", SUMMARY)]:
    print(f"\n{label}  (extra context per sub-agent: {tokens(ctx) if ctx else 0} tokens; full trace would be {tokens(COORDINATOR_TRACE):,})")
    for t in TASKS:
        print(f"  {t:32s} -> {sub_agent(t, ctx)}")

# COMMAND ----------
# MAGIC %md
# MAGIC **What to notice:** with task lines only, each sub-agent makes its own **implicit decisions**, so the outputs conflict. The full
# MAGIC trace would fix it but multiply every sub-agent's context. The **compressed trace summary** fixes it for ~50 tokens.
# MAGIC
# MAGIC ⚠️ If instead all sub-agents agreed with each other but were all stale (old numbers), the cause would be a **shared stale
# MAGIC source** such as an unsynced index, not the dispatch. Check what they *retrieved*.

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: What sub-agents return to the orchestrator

# COMMAND ----------
# %%
transcript = "tool calls, intermediate SQL, reasoning, partial tables ... " * 400
condensed = {"region": "EMEA", "churn_rate": 0.071, "active_start": 18234, "churned": 1295,
             "notes": "Spike in August from a price change.", "full_result": "main.reports.churn_q3_emea"}   # handle, not payload
for label, payload in [("full transcripts", transcript), ("condensed + handle", json.dumps(condensed))]:
    print(f"{label:20s}: {3 * tokens(payload):>7,} tokens in the orchestrator for 3 regions")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: Boundary placement
# MAGIC The same 12-step job split three ways. Each handoff costs a compression (summary) and loses some detail; each agent's
# MAGIC window grows with the steps it owns. Steps 1–4, 5–8 and 9–12 are tightly coupled inside, loosely coupled between.

# COMMAND ----------
# %%
STEP_TOKENS, HANDOFF_LOSS = 9_000, 0.15
COUPLED_BLOCKS = [range(1, 5), range(5, 9), range(9, 13)]


def evaluate(split):
    agents = [list(r) for r in split]
    max_window = max(len(a) * STEP_TOKENS for a in agents)
    handoffs = len(agents) - 1
    cut_coupled = sum(1 for a in agents for b in COUPLED_BLOCKS if 0 < len(set(a) & set(b)) < len(b))
    fidelity = (1 - HANDOFF_LOSS) ** cut_coupled
    return max_window, handoffs, fidelity


for name, split in [("too fine (12 agents)", [range(i, i + 1) for i in range(1, 13)]),
                    ("too coarse (1 agent)", [range(1, 13)]),
                    ("along coupling (3 agents)", COUPLED_BLOCKS)]:
    w, h, f = evaluate(split)
    print(f"{name:26s} max window {w:>7,} tok | handoffs {h:2d} | detail kept across coupled cuts {f:.0%}")

# COMMAND ----------
# MAGIC %md
# MAGIC - **Too fine** → handoff compression overhead: many handoffs cut through tightly coupled steps and lose detail.
# MAGIC - **Too coarse** → one window grows to ~108k tokens and needs repeated compaction.
# MAGIC - **Along coupling** → small windows, few handoffs, none cutting a coupled block.

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4: Which long-horizon strategy fits?

# COMMAND ----------
# %%
def choose(task):
    if task["exact_per_item_state"]:
        return "structured note-taking / state table", "exact per-item status can't survive repeated summaries"
    if task["independent_parts"] and not task["sequential_dependencies"]:
        return "sub-agents with condensed returns", "parts are independent, so isolation and parallelism help"
    if task["sequential_dependencies"]:
        return "single agent + compaction", "each step depends on earlier decisions; splitting would scatter them"
    return "single agent", "fits in one window"


TASKS_LH = {
    "match 2,000 invoices to POs over 3 nights": dict(exact_per_item_state=True, independent_parts=True, sequential_dependencies=False),
    "survey 30 vendors' public docs": dict(exact_per_item_state=False, independent_parts=True, sequential_dependencies=False),
    "refactor a pipeline step by step with the user": dict(exact_per_item_state=False, independent_parts=False, sequential_dependencies=True),
}
for t, traits in TASKS_LH.items():
    s, why = choose(traits)
    print(f"{t:48s} -> {s:36s} ({why})")
