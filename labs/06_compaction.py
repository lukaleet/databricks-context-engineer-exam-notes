# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 06: Trimming vs compaction, and tuning a compaction prompt
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §6 Evaluate whether hard-coded trimming heuristics are sufficient for a task's information-relevance pattern
# MAGIC - §6 Identify which category of information was discarded during compaction, and revise the prompt to preserve it cheaply
# MAGIC - §6 Tune a compaction prompt: maximize recall first, then improve precision
# MAGIC - §6 Identify which content is safe to remove during compaction
# MAGIC
# MAGIC **Time:** ~35 min · **Runs:** locally (rule-based summarizer stand-in) or on Databricks (the real model writes the summaries)

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
# MAGIC ## The trace
# MAGIC A research agent compares vendors for a data-catalog purchase over many turns. Each line has a hidden **category** tag
# MAGIC (used by the offline stand-in and by our checks, never shown to the model).

# COMMAND ----------
# %%
RAW = "x" * 1200   # stands in for a big raw tool payload
TRACE = [
    ("goal", "user", "Find the best data catalog for our 40-person data team; I need a recommendation by Friday."),
    ("constraint", "user", "Exclude any vendor that requires on-prem installation."),
    ("constraint", "user", "Budget is at most 60k EUR per year."),
    ("chatter", "assistant", "Thanks! Happy to help with that."),
    ("raw", "tool", "search_vendors(results=27) " + RAW),
    ("fact", "assistant", "Shortlist from search: Alation, Atlan, Collibra, DataHub (OSS), Unity Catalog (already licensed)."),
    ("preference", "user", "I prefer tools that integrate natively with Databricks."),
    ("raw", "tool", "fetch_pricing(Collibra) " + RAW),
    ("decision", "assistant", "Decision: drop Collibra (quote 95k EUR, over budget)."),
    ("failed", "assistant", "Tried scraping Atlan's pricing page: blocked by login wall; must ask sales instead."),
    ("raw", "tool", "fetch_docs(Alation) " + RAW),
    ("decision", "assistant", "Decision: drop Alation (on-prem server required for lineage connector)."),
    ("id", "assistant", "Opened sales ticket ATL-5531 with Atlan for a quote."),
    ("chatter", "user", "ok cool"),
    ("progress", "assistant", "Done: pricing for Collibra, Alation. Open: Atlan quote (ATL-5531), DataHub hosting cost."),
    ("raw", "tool", "search_reviews(DataHub) " + RAW),
    ("fact", "assistant", "DataHub hosted (Acryl) is about 38k EUR/yr for our size."),
]
PROBES = {  # what the agent must still know after compaction to continue correctly
    "on-prem exclusion": r"on-prem", "budget": r"60k", "Databricks preference": r"Databricks",
    "Collibra dropped": r"Collibra", "Atlan ticket id": r"ATL-5531", "Atlan scrape failed": r"login|sales",
    "Friday deadline": r"Friday",
}
full = "\n".join(f"{role}: {text}" for _, role, text in TRACE)
print(f"{len(TRACE)} messages, {tokens(full):,} tokens")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: Hard-coded trimming (keep the last 6 messages)
# MAGIC Is recency enough here? This task's **relevance pattern** says no: the constraints were stated at the very start.

# COMMAND ----------
# %%
def check(context, label):
    ok = {k: bool(re.search(p, context, re.I)) for k, p in PROBES.items()}
    lost = [k for k, v in ok.items() if not v]
    print(f"{label:30s} {tokens(context):>5,} tok  kept {sum(ok.values())}/{len(ok)}  lost: {lost or '-'}")
    return lost


trimmed = "\n".join(f"{r}: {t}" for _, r, t in TRACE[-6:])
check(full, "no compaction")
check(trimmed, "sliding window (last 6)")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Compaction prompts, from "facts only" to recall-first to precise
# MAGIC v1 is the prompt from the official sample question. Watch which **category** it loses, then fix it the exam's way:
# MAGIC add that category explicitly, compactly.

# COMMAND ----------
# %%
PROMPTS = {
    "v1 facts only": "Summarize the key facts and findings discovered so far.",
    "v2 recall-first": ("Summarize the session. Include: the user's goal and deadline; every constraint, exclusion and preference "
                        "the user stated; every decision with its reason; progress (done / open); all ids and ticket numbers; "
                        "failed approaches and why; key facts; and the full output of every tool call."),
    "v3 precise": ("Summarize the session. Include: the user's goal and deadline; a deduplicated list of constraints, exclusions "
                   "and preferences the user stated; decisions with a one-line reason; progress (done / open); ids and ticket "
                   "numbers exactly; failed approaches and why; key facts. Omit raw tool outputs and small talk."),
}
WANTS = {"goal": r"goal", "constraint": r"constraint|exclusion", "preference": r"preference", "decision": r"decision",
         "progress": r"progress", "id": r"\bids?\b|ticket", "failed": r"failed", "fact": r"facts", "raw": r"output of every tool",
         "chatter": r"small talk and all"}


def stand_in_summarize(prompt):
    keep = {cat for cat, pat in WANTS.items() if re.search(pat, prompt, re.I)}
    return "\n".join(f"- {text}" for cat, _, text in TRACE if cat in keep)


results = {}
for name, prompt in PROMPTS.items():
    summary = llm([{"role": "system", "content": prompt}, {"role": "user", "content": full}], max_tokens=700) if MODEL \
        else stand_in_summarize(prompt)
    results[name] = (check(summary + "\n" + trimmed.split("\n")[-1], name), tokens(summary))

# COMMAND ----------
# MAGIC %md
# MAGIC **Read the results:**
# MAGIC - **v1** loses the **constraints/preferences** and the deadline (and, depending on the model, ids and failed attempts too):
# MAGIC   after compaction the agent would happily recommend an on-prem tool over budget. That's the sample question's failure → add *a deduplicated list of constraints, exclusions and
# MAGIC   preferences*.
# MAGIC - **v2** (recall first) keeps everything, but the raw tool outputs make the summary several times bigger than needed.
# MAGIC - **v3** (precision pass) removes what the agent never needs again (raw outputs, chatter) and still passes every probe.
# MAGIC
# MAGIC That's the tuning loop from notes §6.5: **maximize recall, then trim for precision, re-checking the downstream probes each time.**

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: What was safe to remove?

# COMMAND ----------
# %%
removed = [(cat, text[:60]) for cat, _, text in TRACE if cat in ("raw", "chatter")]
for cat, t in removed:
    print(f"safe to drop [{cat:7s}] {t}…")
print("\nNot safe: constraints, decisions, ids (ATL-5531), failed approaches, open items. They're small and drive later steps.")
