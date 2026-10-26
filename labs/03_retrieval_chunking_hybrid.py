# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 03: Chunking, hybrid retrieval, stale indexes and authoritative sources
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §3 Select an appropriate chunking strategy given document structure, embedding context length and query types
# MAGIC - §3 Diagnose which AI Search configuration is the root cause of a retrieval quality problem
# MAGIC - §3 Design a governance strategy that constrains retrieval to authoritative sources
# MAGIC
# MAGIC **Time:** ~35 min · **Runs:** locally or on Databricks (pure Python mechanics; the last cell shows the AI Search equivalents)

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
# MAGIC ## Step 1: A recursive splitter with overlap
# MAGIC Split on the largest separator that keeps chunks under the target size (paragraph → line → sentence → word),
# MAGIC then add ~10–15 % overlap. This is what "recursive character text splitter" means.

# COMMAND ----------
# %%
def recursive_split(text, size_tokens=120, overlap=0.12, seps=("\n\n", "\n", ". ", " ")):
    def split(t, level):
        if tokens(t) <= size_tokens or level == len(seps):
            return [t]
        out, cur = [], ""
        for part in t.split(seps[level]):
            cand = (cur + seps[level] + part) if cur else part
            if tokens(cand) <= size_tokens:
                cur = cand
            else:
                if cur:
                    out.append(cur)
                if tokens(part) > size_tokens:          # still too big: split it on the next, smaller separator
                    out.extend(split(part, level + 1))
                    cur = ""
                else:
                    cur = part
        return out + ([cur] if cur else [])
    pieces = split(text, 0)
    ov = int(size_tokens * overlap * 4)            # overlap in characters
    return [(pieces[i - 1][-ov:] + " " if i and ov else "") + p for i, p in enumerate(pieces)]


wiki = ("Deployment pipeline overview. Our pipeline builds, tests and promotes artifacts through dev, staging and prod. "
        "Each promotion requires a green test suite and an approval.\n\n"
        "Job scheduler. The scheduler runs nightly jobs. The retry limit for the job scheduler is 3 attempts with exponential "
        "backoff starting at 30 seconds. Jobs that exceed the limit page the on-call engineer.\n\n" +
        "Background. " + "Historical notes about the platform migration and the teams involved. " * 25)
chunks = recursive_split(wiki)
for i, c in enumerate(chunks):
    print(f"[{i}] {tokens(c):>3} tok | {c[:90]!r}…")

# COMMAND ----------
# MAGIC %md
# MAGIC **Compare with the alternatives:** one chunk per article makes one vector represent many topics (narrow lookups like
# MAGIC "retry limit" match poorly); sentence chunks lose the surrounding context for broad questions. The embedding model's context
# MAGIC length is a **ceiling**: anything longer is truncated before embedding (e.g. 512 tokens for `databricks-bge-large-en`).

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Vector vs keyword vs hybrid (RRF)
# MAGIC A toy "semantic" scorer (word overlap with synonyms, blind to codes, like embeddings often are) and BM25-style keyword
# MAGIC scoring, fused with **Reciprocal Rank Fusion**, which is what `query_type="HYBRID"` does in AI Search.

# COMMAND ----------
# %%
import math
from collections import Counter

DOCS = {"kb-1": "Error E-4012 means the payment gateway timed out; retry after 60 seconds.",
        "kb-2": "Payment problems: when a payment fails, check the card and contact your bank.",
        "kb-3": "Timeouts in general: slow networks can cause requests to fail.",
        "kb-4": "Error E-4013 means the card was declined by the issuer.",
        "kb-5": "Shipping delays happen during holidays."}
SYN = {"failed": "fail", "fails": "fail", "failing": "fail", "payments": "payment", "timed": "timeout", "timeouts": "timeout",
       "means": "mean"}


def words(t, keep_codes=True):
    ws = re.findall(r"[A-Za-z]+(?:-\d+)?|\d+", t.lower())
    ws = [SYN.get(w, w) for w in ws]
    return ws if keep_codes else [w for w in ws if not re.search(r"\d", w)]


def semantic(q, d):
    return len(set(words(q, False)) & set(words(d, False)))     # shared meaning-words; codes are invisible


N = len(DOCS)
DF = Counter(w for d in DOCS.values() for w in set(words(d)))


def bm25(q, d, k1=1.2, b=0.75):
    tf, dl = Counter(words(d)), len(words(d))
    avg = sum(len(words(x)) for x in DOCS.values()) / N
    return sum(math.log(1 + (N - DF[w] + .5) / (DF[w] + .5)) * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * dl / avg))
               for w in words(q) if w in tf)


def rank(scorer, q):
    """{doc: rank}; equal scores share the same rank (a tie is a tie, not a win)."""
    scores = {k: round(scorer(q, d), 6) for k, d in DOCS.items()}
    ordered = sorted(set(scores.values()), reverse=True)
    return {k: ordered.index(s) + 1 for k, s in scores.items()}


def rrf(*ranks, k=60):
    fused = Counter()
    for r in ranks:
        for doc, pos in r.items():
            fused[doc] += 1 / (k + pos)
    return [d for d, _ in fused.most_common()]


def top(r, n=3):
    return [f"{d}(#{p})" for d, p in sorted(r.items(), key=lambda kv: kv[1])[:n]]


for q in ["what does error E-4012 mean", "my payment failed, what should I do"]:
    sem, kw = rank(semantic, q), rank(bm25, q)
    print(f"\nQ: {q}\n  ANN-like : {top(sem)}\n  keyword  : {top(kw)}\n  hybrid   : {rrf(sem, kw)[:3]}")

# COMMAND ----------
# MAGIC %md
# MAGIC **What to notice:** the semantic scorer can't tell `E-4012` from `E-4013`; keyword search nails the code; hybrid keeps the
# MAGIC exact hit on top for the code query **and** stays good on the paraphrased one. Diagnosis rule: *misses exact identifiers → HYBRID*.

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: The stale triggered index
# MAGIC A Delta Sync index in **TRIGGERED** mode only changes when you call `sync()`. The source table can be correct while the index
# MAGIC still serves old text, which is exactly the official sample question.

# COMMAND ----------
# %%
source_table = {"clause-7.1": "Termination requires 30 days notice."}
index = dict(source_table)                                       # initial sync
source_table["clause-7.1"] = "Termination requires 90 days notice (amended 2026-10-02)."   # daily pipeline amends the clause
print("source:", source_table["clause-7.1"])
print("index :", index["clause-7.1"], "  <- stale: no sync since the amendment")


def daily_job():
    # task 1: ingest (already ran above) · task 2: index.sync()  <- the cost-effective fix
    index.update(source_table)


daily_job()
print("after the job's sync task:", index["clause-7.1"])

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4: Constrain retrieval to authoritative sources
# MAGIC Two copies of the travel policy exist: the certified gold table and a stale sandbox copy. Governance happens **before**
# MAGIC retrieval: index only certified sources (and filter on the tier as defense in depth). Prompting the model to "prefer official
# MAGIC sources" is not governance.

# COMMAND ----------
# %%
ASSETS = [
    {"table": "main.policies.travel", "certification": "certified", "text": "Hotel cap is 180 EUR per night."},
    {"table": "sandbox.tmp.travel_copy", "certification": None, "text": "Hotel cap is 150 EUR per night."},
    {"table": "main.policies.travel_2024", "certification": "deprecated", "text": "Hotel cap is 120 EUR per night."},
]
naive_index = [a for a in ASSETS]
governed_index = [a for a in ASSETS if a["certification"] == "certified"]
print("naive index serves   :", [a["text"] for a in naive_index])
print("governed index serves:", [a["text"] for a in governed_index])

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5: The same ideas in AI Search (reference, needs your own index)
# MAGIC ```python
# MAGIC from databricks.ai_search.client import AISearchClient          # package databricks-ai-search (was databricks-vectorsearch)
# MAGIC from databricks.ai_search.reranker import DatabricksReranker
# MAGIC idx = AISearchClient().get_index(endpoint_name="ctx-lab", index_name="main.rag.policy_chunks_index")
# MAGIC idx.similarity_search(query_text="error E-4012", columns=["chunk_id", "text", "source"], num_results=5,
# MAGIC                       query_type="HYBRID",                                   # exact codes
# MAGIC                       filters={"source_tier": "authoritative"},              # standard endpoint: dict filters
# MAGIC                       reranker=DatabricksReranker(columns_to_rerank=["text"]))
# MAGIC idx.sync()                                                                   # TRIGGERED index: run after the ingestion task
# MAGIC ```
# MAGIC ```sql
# MAGIC SET TAG ON TABLE main.policies.travel `system.certification_status` = `certified`;
# MAGIC SET TAG ON TABLE main.policies.travel_2024 `system.certification_status` = `deprecated`;
# MAGIC ```
