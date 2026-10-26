# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 02: Few-shot selection under a budget and prompt ablation
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §2 Justify which few-shot examples to include or exclude based on their marginal contribution
# MAGIC - §2 Determine whether a higher-token prompt configuration is justified and identify the element driving the tradeoff
# MAGIC - §2 Select the targeted revision that resolves a failure with the least increase in token cost
# MAGIC
# MAGIC **Time:** ~30 min · **Runs:** locally or on Databricks. Uses MLflow if installed (it is on Databricks) to log each configuration as a run.

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
# MAGIC ## Step 1: Pick few-shot examples by marginal contribution
# MAGIC Eight candidate examples for a ticket-routing agent, each tagged with what it **covers**. Budget: 220 tokens.
# MAGIC A greedy pick maximizes *new coverage per token*, so redundant examples never make it in.

# COMMAND ----------
# %%
CANDIDATES = [
    ("billing: double charge", {"path:billing"}, 'Ticket: "Charged twice for ORD-12" -> {"route": "billing"}'),
    ("billing: refund", {"path:billing"}, 'Ticket: "I want my money back for ORD-9" -> {"route": "billing"}'),
    ("billing: invoice copy", {"path:billing"}, 'Ticket: "Send me the invoice for March" -> {"route": "billing"}'),
    ("shipping: late parcel", {"path:shipping"}, 'Ticket: "ORD-3 is a week late" -> {"route": "shipping"}'),
    ("technical: app crash", {"path:technical"}, 'Ticket: "The app crashes at login" -> {"route": "technical"}'),
    ("ambiguous -> clarify", {"ambiguous", "format"},
     'Ticket: "It doesn\'t work" -> {"route": "clarify", "question": "Is this about an order, a payment or the app?"}'),
    ("format with reason", {"format"}, 'Ticket: "Card declined" -> {"route": "billing", "reason": "payment failure"}'),
    ("long edge case essay", {"path:billing"}, 'Ticket: "' + "very long story about a partial refund " * 12 + '" -> {"route": "billing"}'),
]
NEEDED = {"path:billing", "path:shipping", "path:technical", "ambiguous", "format"}
BUDGET, chosen, covered, used = 220, [], set(), 0
while True:
    best = max(((len(cov - covered) / tokens(txt), name, cov, txt) for name, cov, txt in CANDIDATES
                if name not in [c[0] for c in chosen] and cov - covered and used + tokens(txt) <= BUDGET), default=None)
    if not best:
        break
    _, name, cov, txt = best
    chosen.append((name, cov, txt)); covered |= cov; used += tokens(txt)
print("chosen:", [c[0] for c in chosen], f"({used} tokens)")
print("uncovered:", NEEDED - covered or "nothing")
print("dropped:", [n for n, _, _ in CANDIDATES if n not in [c[0] for c in chosen]])

# COMMAND ----------
# MAGIC %md
# MAGIC **Why these drop:** the second and third billing examples cover a path that's already covered; the long essay covers the
# MAGIC same path at 10× the tokens. The ambiguous example earns its place twice: it covers the *clarify* path **and** the output structure.

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Ablation: which prompt element is worth its tokens?
# MAGIC The "big" prompt adds two elements on top of a lean one: the selected examples, and a long company-policy section.
# MAGIC We evaluate each configuration on the same 12 tickets and log quality **and** tokens.

# COMMAND ----------
# %%
CORE = ("Route the support ticket to one of: billing, shipping, technical. If the ticket doesn't say what it is about, "
        "route to clarify and ask one question.")
FORMAT = 'Return only JSON: {"route": "<billing|shipping|technical|clarify>"}.'
EXAMPLES = "Examples:\n" + "\n".join(c[2] for c in chosen)
POLICY = "Company background and policy history: " + ("ACME was founded in 1987 and has many policies. " * 60)
EVAL = [("Charged twice for my order", "billing"), ("Refund not received yet", "billing"), ("Where is my parcel?", "shipping"),
        ("Courier lost the package", "shipping"), ("App freezes on checkout", "technical"), ("Password reset email never arrives", "technical"),
        ("It doesn't work", "clarify"), ("Help please", "clarify"), ("Something is wrong", "clarify"),
        ("Invoice shows wrong VAT", "billing"), ("Tracking number invalid", "shipping"), ("Error 500 on the website", "technical")]
CONFIGS = {"lean (core+format)": [CORE, FORMAT], "lean+examples": [CORE, FORMAT, EXAMPLES],
           "lean+policy": [CORE, FORMAT, POLICY], "big (all)": [CORE, FORMAT, EXAMPLES, POLICY]}


def stand_in(system, ticket):
    t = ticket.lower()
    route = ("billing" if re.search(r"charg|refund|invoice|vat|card", t) else "shipping" if re.search(r"parcel|package|track|courier", t)
             else "technical" if re.search(r"app|password|error|website", t) else ("clarify" if "-> {\"route\": \"clarify\"" in system else "technical"))
    return json.dumps({"route": route})


def run(name, parts):
    system = "\n\n".join(parts)
    correct = 0
    for ticket, gold in EVAL:
        out = llm([{"role": "system", "content": system}, {"role": "user", "content": ticket}], max_tokens=60) if MODEL else stand_in(system, ticket)
        m = re.search(r'"route"\s*:\s*"(\w+)"', out or "")
        correct += bool(m and m.group(1) == gold)
    return correct / len(EVAL), tokens(system)


try:
    import mlflow
    if not ON_DATABRICKS:
        mlflow.set_tracking_uri("file:" + os.path.join(os.path.expanduser("~"), ".ctxlab-mlruns"))
    mlflow.set_experiment("/Shared/ctxlab_prompt_ablation" if ON_DATABRICKS else "ctxlab_prompt_ablation")
except Exception:
    mlflow = None
rows = []
for name, parts in CONFIGS.items():
    acc, tok = run(name, parts)
    rows.append((name, acc, tok))
    if mlflow:
        with mlflow.start_run(run_name=name):
            mlflow.log_metrics({"accuracy": acc, "prompt_tokens": tok})
print(f"{'config':22s} accuracy  prompt tokens")
for name, acc, tok in rows:
    print(f"{name:22s} {acc:7.0%}  {tok:>8,}")
print("\nMLflow runs logged" if mlflow else "\n(MLflow not installed: results printed only)")

# COMMAND ----------
# MAGIC %md
# MAGIC **Read the table like the exam does:**
# MAGIC - *lean+examples* vs *lean*: the examples buy the **clarify** path (and format robustness) for a few hundred tokens → justified.
# MAGIC - *lean+policy* vs *lean*: ~1,000 more tokens per call, no quality gain → the policy section is pure cost.
# MAGIC - *big* vs *lean+examples*: same quality, much higher cost → **not justified**. The element driving the gain is the examples, not the policy.
# MAGIC
# MAGIC In MLflow: select the four runs → **Compare** → chart `accuracy` vs `prompt_tokens`.
