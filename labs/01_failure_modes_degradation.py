# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 01: Failure modes, degradation curve and reasoning budgets
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §1 Diagnose context failure modes (poisoning, distraction, confusion, clash) given an agent trace
# MAGIC - §1 Identify the point at which context length causes measurable degradation and select the intervention
# MAGIC - §1 Select the appropriate reasoning mode based on token budget and context window impact
# MAGIC
# MAGIC **Time:** ~30 min · **Runs:** locally or on Databricks (a real model makes Step 2 much more interesting)

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
# MAGIC ## Step 1: Diagnose four traces
# MAGIC Read each trace, decide the failure mode **before** printing the answer. Use the decision questions from notes §1.3:
# MAGIC *wrong and reused?* → poisoning · *correct but irrelevant and leaking into the answer?* → confusion ·
# MAGIC *two things contradict?* → clash · *very long and repeating history instead of planning?* → distraction.

# COMMAND ----------
# %%
TRACES = {
    "A": ["step 1: retrieve(contract_2026) -> clause 4.2 limitation of liability",
          "context also holds: full transcript of last week's session about a SOFTWARE LICENSE (IP ownership, indemnification)",
          "answer: cites 4.2, then discusses indemnification and IP ownership (not in the retrieved clauses)"],
    "B": ["step 3: agent writes to notes: 'customer tier = PLATINUM' (tool actually returned GOLD)",
          "step 9: applies PLATINUM discount, quoting its notes",
          "step 15: escalates because PLATINUM SLA is breached"],
    "C": ["system prompt: 'Always answer in under 50 words.'",
          "retrieved style guide: 'Support answers must include all troubleshooting steps in full.'",
          "answers alternate between 1-line replies and 400-word walkthroughs"],
    "D": ["context: 180k tokens of game-play history",
          "agent keeps re-trying the same 3 moves seen many times in its history",
          "no new plan is formed despite the goal being unreachable that way"],
}
ANSWERS = {"A": "confusion: correct-but-irrelevant prior-session content is used in the answer",
           "B": "poisoning: an error entered the context (its own notes) and is referenced repeatedly",
           "C": "clash: two pieces of context conflict, so behaviour flips",
           "D": "distraction: very long context, the model over-relies on history instead of reasoning"}
for k, steps in TRACES.items():
    print(f"Trace {k}:\n  " + "\n  ".join(steps))
input_fn = input if (not ON_DATABRICKS and os.isatty(0)) else (lambda _: "")
input_fn("\nYour diagnoses? (press Enter to reveal) ")
for k, a in ANSWERS.items():
    print(f"{k} -> {a}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Measure degradation with a needle test
# MAGIC We hide **two related facts** at different depths in growing amounts of filler and ask a question that needs both.
# MAGIC On Databricks this calls the real model; offline a simulated model loses recall as the context grows, so you can see the
# MAGIC **harness** (that's what the exam asks about: find the knee, intervene before it).
# MAGIC
# MAGIC ⚠️ On Databricks this sends ~6 requests of up to ~60k tokens. Lower `SIZES` if your quota is small.

# COMMAND ----------
# %%
import random

random.seed(7)
FILLER = ("The quarterly operations review covered staffing, facilities and vendor renewals in routine detail. ")
FACT1, FACT2 = "The refund window for order ORD-77 is 14 days.", "ORD-77 was delivered on 3 November."
QUESTION = "Until which date can the customer return ORD-77? Answer with a date only."
EXPECTED = "17 November"
SIZES = [2_000, 8_000, 16_000, 32_000, 48_000, 60_000] if MODEL else [2_000, 8_000, 16_000, 32_000, 64_000, 96_000, 128_000]


def build(n_tokens):
    n = max(2, n_tokens * 4 // len(FILLER))
    chunks = [FILLER] * n
    chunks.insert(n // 5, FACT1 + " ")
    chunks.insert(n // 2, FACT2 + " ")
    return "".join(chunks)


def simulated_model(ctx_tokens, window=128_000):
    # stand-in: perfect until ~50% of the window, then recall drops (context rot)
    fill = ctx_tokens / window
    return EXPECTED if random.random() > max(0.0, (fill - 0.5) * 1.6) else "3 November"


results = []
for size in SIZES:
    ctx = build(size)
    hits = 0
    for trial in range(3 if not MODEL else 1):
        out = llm([{"role": "user", "content": ctx + "\n\n" + QUESTION}], max_tokens=20) if MODEL else simulated_model(tokens(ctx))
        hits += EXPECTED.split()[0] in (out or "")
    results.append((size, hits / (3 if not MODEL else 1)))
    print(f"{size:>7,} tokens  recall={results[-1][1]:.0%}")

knee = next((s for s, r in results if r < 1.0), None)
print(f"\nFirst size with errors: {knee:,} tokens" if knee else "\nNo degradation in this range")
print("Intervention: compact / clear before that point, keep facts in a summary. A bigger window would not move the knee earlier for free.")

# COMMAND ----------
# MAGIC %md
# MAGIC **In real systems** you do the same with MLflow traces: log the context size per turn as a trace attribute, evaluate each
# MAGIC turn with a judge (correctness, groundedness), and plot quality against context fill. The knee tells you where to trigger
# MAGIC compaction.

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: What thinking costs in a long agent loop
# MAGIC Reasoning tokens are output tokens. If you keep them in the history, each step's thinking also takes space in later steps.

# COMMAND ----------
# %%
WINDOW = 200_000
PER_STEP_IO = 2_500          # tool call + scoped tool result + message per step
for mode, think in [("standard", 0), ("reduced thinking (1k)", 1_000), ("extended thinking (8k)", 8_000)]:
    for keep in ((False,) if not think else (False, True)):
        used, steps = 8_000, 0             # system prompt + tools
        while used + PER_STEP_IO + think < WINDOW * 0.75:     # compact at 75%
            used += PER_STEP_IO + (think if keep else 0)
            steps += 1
        print(f"{mode:24s} thinking kept in history={keep!s:5}  -> {steps:3d} steps before compaction")

# COMMAND ----------
# MAGIC %md
# MAGIC **Takeaway:** extended thinking on every step of a long loop multiplies output cost and (when retained) fills the window
# MAGIC several times faster. Use **extended** thinking for hard planning steps, **reduced** for routine loop steps, **standard** for
# MAGIC simple routing/extraction. On Databricks: `extra_body={"thinking": {"type": "enabled", "budget_tokens": N}}` (N < max_tokens)
# MAGIC for hybrid models, `reasoning_effort="low|medium|high"` for reasoning-only models.
