# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 04: Agent memory: sessions, long-term store, routing and task state
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §4 Configure persistent agent memory across sessions using a Lakebase-backed durable store
# MAGIC - §4 Identify the mismatch between the memory type used and the information need
# MAGIC - §4 Identify whether AI Search or structured query retrieval fits a memory query type
# MAGIC - §4 Diagnose over-retrieval and under-retrieval; resolve intent before retrieval
# MAGIC - §4 Identify when a Delta-backed state object is required over an in-context scratchpad
# MAGIC
# MAGIC **Time:** ~40 min · **Runs:** locally (optional `pip install langgraph`) or on Databricks. To use **Lakebase**, create a
# MAGIC Lakebase instance, `%pip install -U "databricks-langchain[memory]" langgraph`, and set `LAKEBASE_INSTANCE` below.
# MAGIC Without it the lab uses LangGraph's in-memory saver/store (same API), or a tiny stand-in if LangGraph isn't installed.

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
# %%
LAKEBASE_INSTANCE = os.environ.get("LAKEBASE_INSTANCE", "")      # e.g. "agent-memory" (Databricks only)
try:
    from langgraph.graph import StateGraph, MessagesState, START
    HAVE_LANGGRAPH = True
except ImportError:
    HAVE_LANGGRAPH = False
print("LangGraph:", HAVE_LANGGRAPH, "| Lakebase:", LAKEBASE_INSTANCE or "not configured")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: Short-term memory = a checkpointer keyed by `thread_id`
# MAGIC The graph below remembers the user's name *within a thread*. Same `thread_id` → the conversation continues (also after a
# MAGIC restart, when the checkpointer is Lakebase). New `thread_id` → a fresh conversation.

# COMMAND ----------
# %%
def reply(messages):
    """The agent's 'model': answers from the conversation so far (uses the LLM when available)."""
    out = llm([{"role": "system", "content": "Answer in one short sentence."}] +
              [{"role": m["role"], "content": m["content"]} for m in messages], max_tokens=60)
    if out:
        return out
    names = [re.search(r"I'm (\w+)", m["content"]) for m in messages if m["role"] == "user"]
    names = [n.group(1) for n in names if n]
    return f"Your name is {names[-1]}." if names else "I don't know your name yet."


if HAVE_LANGGRAPH:
    def node(state: MessagesState):
        msgs = [{"role": "user" if m.type == "human" else "assistant", "content": m.content} for m in state["messages"]]
        return {"messages": [("assistant", reply(msgs))]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", node)
    builder.add_edge(START, "agent")

    if LAKEBASE_INSTANCE:
        from databricks_langchain import CheckpointSaver           # LangGraph PostgresSaver on a Lakebase pool
        checkpointer = CheckpointSaver(instance_name=LAKEBASE_INSTANCE)
        checkpointer.setup()                                        # creates the checkpoint tables (async saver: await setup())
    else:
        from langgraph.checkpoint.memory import InMemorySaver
        checkpointer = InMemorySaver()                              # same interface, not durable
    graph = builder.compile(checkpointer=checkpointer)

    def chat(text, thread):
        res = graph.invoke({"messages": [("user", text)]}, config={"configurable": {"thread_id": thread}})
        return res["messages"][-1].content
else:
    THREADS = {}                                                    # stand-in: thread_id -> message list

    def chat(text, thread):
        msgs = THREADS.setdefault(thread, [])
        msgs.append({"role": "user", "content": text})
        msgs.append({"role": "assistant", "content": reply(msgs)})
        return msgs[-1]["content"]

print("t-1:", chat("Hi, I'm Ana.", "t-1"))
print("t-1:", chat("What's my name?", "t-1"))
print("t-2:", chat("What's my name?", "t-2"), "  <- new thread, no session memory")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Long-term memory = a store namespaced by user, searched by meaning
# MAGIC Cross-session facts go into a **store**, namespaced by the **verified** user id. On Databricks with Lakebase this is
# MAGIC `DatabricksStore(instance_name=..., embedding_endpoint="databricks-gte-large-en", embedding_dims=1024)`. Locally we give
# MAGIC LangGraph's `InMemoryStore` a toy embedding function so `search(query=...)` works the same way.

# COMMAND ----------
# %%
VOCAB = ["currency", "eur", "usd", "report", "format", "pdf", "excel", "travel", "hotel", "window", "seat", "language",
         "polish", "english", "meeting", "morning", "team", "warehouse", "berlin"]
ALIAS = {"euro": "eur", "euros": "eur", "reports": "report", "spreadsheet": "excel", "xlsx": "excel", "flights": "travel",
         "flight": "travel", "trip": "travel", "aisle": "seat", "reporting": "report"}


def toy_embed(texts):
    vecs = []
    for t in texts:
        ws = [ALIAS.get(w, w) for w in re.findall(r"[a-z]+", t.lower())]
        v = [float(ws.count(term)) for term in VOCAB]
        n = sum(x * x for x in v) ** 0.5 or 1.0
        vecs.append([x / n for x in v])
    return vecs


MEMORIES = [("currency", "Prefers reports in EUR"), ("format", "Wants reports as Excel, not PDF"),
            ("seat", "Window seat on flights"), ("language", "Answers in Polish"), ("warehouse", "Manages the Berlin warehouse")]
if HAVE_LANGGRAPH and LAKEBASE_INSTANCE:
    from databricks_langchain import DatabricksStore
    store = DatabricksStore(instance_name=LAKEBASE_INSTANCE, embedding_endpoint="databricks-gte-large-en", embedding_dims=1024)
    store.setup()
elif HAVE_LANGGRAPH:
    from langgraph.store.memory import InMemoryStore
    store = InMemoryStore(index={"dims": len(VOCAB), "embed": toy_embed, "fields": ["text"]})
else:
    store = None
user_id = "ana@acme.com"                    # from the authenticated request, NEVER from the model's output
ns = ("memories", user_id.replace(".", "_"))  # LangGraph namespace labels can't contain periods
if store:
    for key, text in MEMORIES:
        store.put(ns, key, {"text": text})
    for q in ["how should I format the quarterly reporting?", "book me a trip to Berlin"]:
        hits = store.search(ns, query=q, limit=2)
        print(q, "->", [h.value["text"] for h in hits])
    print("exact key lookup:", store.get(ns, "language").value)
else:
    print("(install langgraph to run the store; the routing step below works without it)")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: Route memory queries: semantic search vs structured SQL
# MAGIC Fuzzy "what does the user prefer about X" → semantic search. Exact ids, dates, counts, "last N" → **SQL on Lakebase**.
# MAGIC We use SQLite locally as a stand-in for the Lakebase Postgres table.

# COMMAND ----------
# %%
import sqlite3

db = sqlite3.connect(":memory:")
db.execute("CREATE TABLE interactions (user_id TEXT, ts TEXT, kind TEXT, ref TEXT, note TEXT)")
db.executemany("INSERT INTO interactions VALUES (?,?,?,?,?)", [
    (user_id, "2026-07-02", "refund", "ORD-11", "damaged item"), (user_id, "2026-08-15", "refund", "ORD-31", "late"),
    (user_id, "2026-09-03", "ticket", "T-1182", "login issue"), (user_id, "2026-09-20", "refund", "ORD-44", "wrong size"),
    ("bob@acme.com", "2026-09-21", "refund", "ORD-50", "late")])


def route(question):
    structured = re.search(r"\b(how many|count|last \d+|status of|ORD-\d+|T-\d+|since|between|in Q[1-4])\b", question, re.I)
    return "SQL" if structured else "semantic"


for q in ["How many refunds did I request in Q3?", "What do I usually prefer for reports?", "Status of T-1182?"]:
    print(f"{route(q):8s} <- {q}")
print("Q3 refunds:", db.execute("SELECT COUNT(*) FROM interactions WHERE user_id=? AND kind='refund' "
                                "AND ts BETWEEN '2026-07-01' AND '2026-09-30'", (user_id,)).fetchone()[0])

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4: Over-retrieval vs under-retrieval
# MAGIC Too high `k` / no threshold → old and unrelated memories pollute the context. Too strict → the needed memory is missed.

# COMMAND ----------
# %%
def cos(a, b):
    return sum(x * y for x, y in zip(a, b))


qv = toy_embed(["prepare the monthly report for my team"])[0]
scored = sorted(((cos(qv, toy_embed([t])[0]), t) for _, t in MEMORIES), reverse=True)
for k, thr in [(5, 0.0), (1, 0.9), (3, 0.3)]:
    got = [t for s, t in scored[:k] if s >= thr]
    print(f"k={k} threshold={thr}: {got}")
print("-> k=5/no threshold pollutes (seat, language...), k=1/0.9 misses the format preference, k=3/0.3 is balanced.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5: Resolve intent **before** retrieval
# MAGIC "What's the limit?" retrieved literally returns the *credit* limit. With the session context, an intent-resolution step
# MAGIC rewrites it first: the user was talking about the API.

# COMMAND ----------
# %%
KB = {"credit limit": "Your credit limit is 5,000 EUR.", "api rate limit": "The API rate limit is 100 requests per minute."}
session = ["I'm calling your API from a batch job.", "Some requests get HTTP 429."]
question = "What's the limit?"


def resolve_intent(q, history):
    out = llm([{"role": "system", "content": "Rewrite the last question so it is self-contained, using the conversation. "
                                             "Return only the rewritten question."},
               {"role": "user", "content": "\n".join(history + [q])}], max_tokens=40)
    if out:
        return out
    return "What is the API rate limit?" if any(re.search(r"API|429", h) for h in history) else q


def retrieve(q):
    return max(KB.items(), key=lambda kv: sum(w in q.lower() for w in kv[0].split()))[1]


print("raw retrieval     :", retrieve(question))
print("resolved question :", resolve_intent(question, session))
print("intent-first      :", retrieve(resolve_intent(question, session)))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 6: A durable state object instead of a scratchpad
# MAGIC A batch agent processes 500 invoices over several runs. Progress lives in a **table** (Delta on Databricks; SQLite here),
# MAGIC so a crash or a new session resumes exactly where it stopped, and nothing about progress needs to sit in the context.

# COMMAND ----------
# %%
db.execute("CREATE TABLE invoice_state (invoice_id TEXT PRIMARY KEY, status TEXT, result TEXT)")
db.executemany("INSERT INTO invoice_state VALUES (?, 'pending', NULL)", [(f"INV-{i:04d}",) for i in range(500)])


def run_batch(limit, crash_after=None):
    todo = db.execute("SELECT invoice_id FROM invoice_state WHERE status='pending' ORDER BY invoice_id LIMIT ?", (limit,)).fetchall()
    for n, (inv,) in enumerate(todo):
        if crash_after is not None and n == crash_after:
            raise RuntimeError("worker crashed")
        db.execute("UPDATE invoice_state SET status='done', result='matched' WHERE invoice_id=?", (inv,))


try:
    run_batch(200, crash_after=137)
except RuntimeError as e:
    print("run 1:", e)
run_batch(1000)
print(dict(db.execute("SELECT status, COUNT(*) FROM invoice_state GROUP BY status").fetchall()))
print("A scratchpad would have lost the 137 completed items (or had to carry 500 statuses in the context).")
# On Databricks: the same table as Delta, e.g. spark.sql("MERGE INTO main.agents.invoice_state ...")
