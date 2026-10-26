# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 05: Progressive disclosure, ambiguous tools, result clearing and skills
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §5 Apply progressive disclosure to MCP tool access to reduce token usage compared to raw tool dumps
# MAGIC - §5 Identify the description overlap that causes ambiguous tool selection
# MAGIC - §5 Evaluate which raw tool outputs are candidates for clearing
# MAGIC - §5 Identify capabilities to package as Agent Skills and the loading strategy that minimizes baseline cost
# MAGIC
# MAGIC **Time:** ~30 min · **Runs:** locally or on Databricks

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
# MAGIC ## Step 1: A 60-tool MCP server, dumped raw vs disclosed progressively

# COMMAND ----------
# %%
DOMAINS = {"orders": ["status", "search", "cancel", "update_address", "list_items", "refund_eligibility"],
           "billing": ["get_invoice", "list_payments", "issue_credit", "update_card", "tax_breakdown", "dunning_status"],
           "shipping": ["track", "carrier_info", "reschedule", "return_label", "pickup", "customs_docs"],
           "catalog": ["get_product", "search_products", "stock_level", "price_history", "variants", "reviews"],
           "crm": ["get_customer", "search_customers", "notes", "tier", "consents", "merge"],
           "support": ["open_ticket", "update_ticket", "close_ticket", "escalate", "sla_status", "macros"],
           "hr": ["policy_lookup", "pto_balance", "org_chart", "job_codes", "benefits", "payroll_dates"],
           "it": ["reset_password", "device_status", "license_seats", "vpn_status", "incident", "change_request"],
           "finance": ["gl_lookup", "cost_center", "budget_vs_actual", "fx_rate", "close_calendar", "accruals"],
           "legal": ["contract_lookup", "clause_search", "nda_status", "retention_policy", "litigation_hold", "dpa"]}


def schema(domain, action):
    return {"name": f"{domain}_{action}",
            "description": f"{action.replace('_', ' ').capitalize()} in the {domain} system. " + "Detailed usage notes. " * 8,
            "inputSchema": {"type": "object", "properties": {
                "id": {"type": "string", "description": f"The {domain} record id"},
                "filters": {"type": "object", "description": "Optional filters", "additionalProperties": {"type": "string"}},
                "limit": {"type": "integer", "default": 20}}, "required": ["id"]}}


TOOLS = {f"{d}_{a}": schema(d, a) for d, acts in DOMAINS.items() for a in acts}
raw_dump = tokens(list(TOOLS.values()))

index = [{"group": d, "summary": f"{d}: " + ", ".join(acts)} for d, acts in DOMAINS.items()]   # stage 0: tiny catalog
intent = "Where is my parcel? It was supposed to arrive Monday."
stage0 = tokens(index)
group = max(DOMAINS, key=lambda d: sum(w in intent.lower() for w in {"shipping": ["parcel", "arrive", "deliver", "where"]}.get(d, [d])))
stage1 = tokens([{"name": f"{group}_{a}", "description": TOOLS[f'{group}_{a}']['description'][:60]} for a in DOMAINS[group]])
stage2 = tokens(TOOLS[f"{group}_track"])
print(f"raw dump of {len(TOOLS)} schemas, every turn : {raw_dump:>6,} tokens")
print(f"stage 0 catalog (10 groups)            : {stage0:>6,}")
print(f"stage 1 '{group}' names + short descriptions: {stage1:>6,}")
print(f"stage 2 one full schema ({group}_track)   : {stage2:>6,}")
print(f"progressive total                      : {stage0 + stage1 + stage2:>6,}  ({100 * (stage0 + stage1 + stage2) / raw_dump:.0f}% of the dump)")

# COMMAND ----------
# MAGIC %md
# MAGIC **Stage 3 (execution)** keeps the saving going: process the result **before** it reaches the model.

# COMMAND ----------
# %%
tracking_events = [{"ts": f"2026-11-0{d}T{h:02d}:00", "event": e, "facility": f"HUB-{h}", "raw": "x" * 80}
                   for d in range(1, 5) for h, e in enumerate(["scanned", "in transit", "sorted", "delayed: weather"])]
scoped = {"latest": tracking_events[-1]["event"], "eta_changed": True, "last_scan": tracking_events[-1]["ts"]}
print(f"raw tracking result: {tokens(tracking_events):,} tokens  ->  scoped result: {tokens(scoped)} tokens: {scoped}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Why does the agent confuse these tools?
# MAGIC Compare descriptions pairwise. High word overlap + same inputs + no "when to use" = ambiguous selection.

# COMMAND ----------
# %%
ORDER_TOOLS = {
    "fetch_order_status": "Gets information about an order for a customer.",
    "get_order_status": "Retrieves order information for the customer.",
    "retrieve_order_info": "Gets order details and information.",
    "lookup_order_details": "Look up details of a customer order.",
}
STOP = {"a", "an", "the", "for", "of", "and", "about", "to"}
LEMMA = {"gets": "get", "retrieves": "get", "retrieve": "get", "look": "get", "lookup": "get", "fetch": "get",
         "details": "information", "detail": "information", "info": "information", "customer": "customer"}


def bag(t):
    return {LEMMA.get(w, w) for w in re.findall(r"[a-z]+", t.lower()) if w not in STOP and w != "up"}


names = list(ORDER_TOOLS)
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, b = bag(ORDER_TOOLS[names[i]]), bag(ORDER_TOOLS[names[j]])
        print(f"{names[i]:22s} vs {names[j]:22s} overlap={len(a & b) / len(a | b):.2f}  shared={sorted(a & b)}")

FIXED = {
    "orders_get_status": "Current fulfilment status and ETA of ONE order by order_id. Use for 'where is my order'. "
                         "Does not return items or prices.",
    "orders_get_invoice": "Invoice lines, prices and taxes of ONE order by order_id. Use for billing questions only.",
}
print("\nAfter rewriting with distinct capability descriptors (and merging the duplicates):")
for k, v in FIXED.items():
    print(f"  {k}: {v}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: Which tool outputs can be cleared?
# MAGIC A deep history near capacity. Clear only results that are **old, already digested and re-fetchable**. Keep the recent ones,
# MAGIC the ones pending steps depend on, and anything that can't be reproduced (e.g. ids returned by a create).

# COMMAND ----------
# %%
HISTORY = [
    {"turn": 3, "tool": "crm_search_customers", "tokens": 6200, "digested": True, "refetchable": True, "write": False, "needed_later": False},
    {"turn": 7, "tool": "orders_search", "tokens": 9100, "digested": True, "refetchable": True, "write": False, "needed_later": False},
    {"turn": 9, "tool": "orders_create_replacement", "tokens": 180, "digested": True, "refetchable": False, "write": True, "needed_later": True},
    {"turn": 12, "tool": "shipping_track", "tokens": 3400, "digested": True, "refetchable": True, "write": False, "needed_later": True},
    {"turn": 18, "tool": "billing_list_payments", "tokens": 5200, "digested": False, "refetchable": True, "write": False, "needed_later": True},
]
CURRENT_TURN = 19


def clearable(r):
    return r["digested"] and r["refetchable"] and not r["write"] and not r["needed_later"] and CURRENT_TURN - r["turn"] > 3


freed = 0
for r in HISTORY:
    verdict = "CLEAR" if clearable(r) else "keep"
    freed += r["tokens"] if verdict == "CLEAR" else 0
    print(f"turn {r['turn']:>2} {r['tool']:26s} {r['tokens']:>5} tok -> {verdict}")
print(f"freed {freed:,} tokens; stub left behind: '[cleared: orders_search(...) - findings recorded in turn 8]'")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4: Agent Skills: metadata always, body on demand

# COMMAND ----------
# %%
SKILLS = {
    "regulatory-xml-export": ("Build the quarterly regulator XML export. Use only when the user asks for the regulator report.", 2400),
    "gdpr-deletion": ("Handle a GDPR erasure request end to end. Use when a user asks to delete their personal data.", 1800),
    "contract-redlining": ("Redline a contract against the playbook. Use for contract review requests.", 3100),
    "bulk-price-update": ("Plan and validate a bulk price change. Use for catalog-wide price updates.", 1500),
}
always_loaded = sum(tokens(f"{n}: {d}") for n, (d, _) in SKILLS.items())
all_bodies = sum(body for _, body in SKILLS.values())
print(f"everything in the system prompt : {always_loaded + all_bodies:>5,} tokens on EVERY call")
print(f"skills, metadata only (baseline): {always_loaded:>5,} tokens on every call")
print(f"+ one skill body when relevant  : +{SKILLS['gdpr-deletion'][1]:,} tokens, only in the conversations that need it")
