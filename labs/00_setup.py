# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 00: Setup, token counting and the LLM helper
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §1 Select the right tool in the Databricks product stack for a given scenario
# MAGIC - §1 Identify which context elements consume disproportionate attention budget
# MAGIC
# MAGIC **Time:** ~10 min · **Runs:** locally (Python 3.10+, standard library only) or on Databricks (incl. Free Edition)
# MAGIC
# MAGIC Every lab is a Databricks notebook in *source format* **and** a plain Python script (`# %%` cells work in VS Code / PyCharm).
# MAGIC
# MAGIC **Local:** `python labs/00_setup.py`. No packages needed. Where a lab would call an LLM, it uses a small deterministic
# MAGIC *offline stand-in* and tells you what the real model would do. Optional: `pip install langgraph` for Lab 04.
# MAGIC
# MAGIC **Databricks:** clone the repo as a **Git folder** (or *Import → URL* with the Raw link). The labs call a pay-per-token
# MAGIC **Foundation Model API** endpoint (`databricks-…`) through the OpenAI-compatible client. If `openai` is missing on your
# MAGIC compute, run `%pip install -U openai databricks-sdk` and then `dbutils.library.restartPython()`.
# MAGIC
# MAGIC Each lab starts with the same small helper cell, so every notebook runs on its own.

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
# MAGIC ## Step 1: Smoke test the model (Databricks) or the stand-in (local)

# COMMAND ----------
# %%
answer = llm([{"role": "system", "content": "Answer in one short sentence."},
              {"role": "user", "content": "What is context engineering?"}])
print(answer or "[offline] Context engineering = choosing the smallest set of high-signal tokens the model needs at each step.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Measure what a context is made of
# MAGIC A context is more than the prompt. Build a realistic one and see which element eats the budget.

# COMMAND ----------
# %%
system = "You are a support agent for ACME. Answer only from retrieved policy text. Cite the policy id."
tool = {"name": "orders_get_status", "description": "Current status and ETA of ONE order by id.",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "e.g. ORD-1182"}},
                       "required": ["order_id"]}}
tools = [dict(tool, name=f"tool_{i}", description=tool["description"] + " " + "x" * 120) for i in range(40)]
raw_result = [{"order_id": f"ORD-{i}", "status": "shipped", "eta": "2026-11-0%d" % (i % 9 + 1), "lines": list(range(20))}
              for i in range(150)]
history = [{"role": "user", "content": "Where is my order?"}, {"role": "assistant", "content": "Which order id?"}] * 10
elements = {"system prompt": system, "40 tool schemas": tools, "1 raw tool result (150 rows)": raw_result,
            "20 history messages": history, "user question": "Is ORD-1182 late?"}
total = sum(tokens(v) for v in elements.values())
for k, v in sorted(elements.items(), key=lambda kv: -tokens(kv[1])):
    print(f"{k:32s} {tokens(v):>7,} tokens  {100 * tokens(v) / total:5.1f}%")
print(f"{'TOTAL':32s} {total:>7,}")

# COMMAND ----------
# MAGIC %md
# MAGIC **What to notice:** the *task* (system prompt + question) is under 1 % of the window. Tool schemas and one unscoped tool
# MAGIC result dominate. That's §1.7 of the notes: shrink the **biggest low-signal element** (tool loadout, result scoping),
# MAGIC not the high-signal task definition.
