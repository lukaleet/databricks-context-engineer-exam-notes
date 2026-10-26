---
id: d3
title: "Section 3: Knowledge Retrieval and Genie Configuration"
weight: 20
---

# Section 3: Knowledge Retrieval and Genie Configuration (20%)

> 🗺️ **Visual learner?** Retrieval modes, AI Search configuration and authoritative-source governance are drawn in the [Visual guide](#/notes/visual).
> 🌉 Much of this section repeats GenAI exam §2 and §4. See the [bridge page](#/notes/bridge) for what you can skim.

**Objectives**

1. Given an underperforming agent and its Unity Catalog metadata, identify which missing or poorly specified metadata causes the accuracy gap and select the highest-impact configuration change
2. Select which UC objects (managed tables, views, parameterized queries, SQL functions) to curate into a Genie space for a business domain
3. Given documented retrieval quality problems, diagnose which AI Search configuration is the root cause and select the remediation that most directly improves signal quality
4. Design a RAG pipeline that retrieves chunks from a UC-governed document corpus and injects them into agent context
5. Select a chunking strategy given document structure, embedding model context length and query types
6. Given a task and available data sources, select the context elements required for the agent to correctly scope and execute the task
7. Distinguish pre-inference retrieval (embedding-based, up-front) from just-in-time agentic retrieval (tool calls, dynamic Delta queries) and select the appropriate strategy
8. Identify which retrieval failure mode is occurring from MLflow eval logs and UC metadata, and select the UC governance action that most directly resolves it
9. Design a governance strategy that constrains the agent's retrieval space to authoritative sources before deployment, in an environment with both authoritative and derived assets

---

## 3.1 Pre-inference vs just-in-time retrieval

| | **Pre-inference retrieval** (up-front) | **Just-in-time (agentic) retrieval** |
|---|---|---|
| How | embed the query, fetch top-k chunks, put them in the prompt **before** the model runs | the model decides **during** the task to call tools: AI Search retriever, Genie, SQL on Delta tables, UC functions |
| Latency | one retrieval, one LLM call: fast and predictable | extra tool-call round trips |
| Best for | single-shot Q&A over a stable document corpus; the question itself is a good search query | multi-step tasks; the need emerges as the agent works; structured or fast-changing data; very large spaces the model must explore |
| Risks | irrelevant chunks for vague or multi-part questions; context filled even when not needed | more tokens and steps; depends on good tool descriptions |
| Context cost | fixed k chunks every time | only what's needed, but tool results must be scoped |

**Hybrid** is common: load a small amount up front (e.g. the policy summary, user profile) and let the agent fetch details on demand.

> **Exam pattern:** "data changes every few minutes", "the agent must explore", "the needed table depends on earlier steps" →
> **just-in-time** (tools, dynamic Delta/SQL queries). "FAQ bot over a fixed handbook, lowest latency" → **pre-inference**.

[[diagram:retrieval-modes]]

## 3.2 Context the agent needs to scope a task

Before an agent can execute a task it needs:

| Element | Example | If missing |
|---|---|---|
| **Resolved intent** | "refund status for order 1182", not "where's my money?" | right data, wrong question (see §4.9) |
| **Entity identifiers** | order id, customer id, account | the agent guesses or searches broadly |
| **Scope / filters** | time range, region, business unit, product | over-broad retrieval, wrong aggregates |
| **Identity and permissions** | who the user is (on-behalf-of auth) | data leaks, or access errors |
| **Relevant policy or knowledge** | refund policy for that region | generic or wrong answer |
| **Available tools** | which tool fits which subtask | wrong tool, or a missing action |
| **Output requirements** | format, length, audience | unusable answer |

The exam asks you to pick the elements that are **required**. Leave out "nice to have" context that only costs tokens.

## 3.3 Unity Catalog metadata drives accuracy

Agents (and Genie) read UC metadata to choose tables, columns and joins. Typical gaps → highest-impact fix:

| Symptom | Missing / poor metadata | Highest-impact change |
|---|---|---|
| Picks the wrong column (`amount` vs `amount_usd`) | no column comments, ambiguous names | add **column descriptions** (units, meaning), synonyms |
| Wrong joins, duplicated totals | no PK/FK constraints | declare **PK/FK** (become Genie join relationships) |
| Uses an old staging copy of a table | no certification, nothing marks the authoritative table | tag the right one `system.certification_status = certified`, the old one `deprecated`, remove it from the space or index |
| Misreads coded values (`st = 'C'`) | no description of the value set | column comment listing the codes; entity matching |
| Wrong metric definition | KPI defined differently everywhere | a **metric view** or SQL expression as the single definition |

```sql
COMMENT ON COLUMN main.fin.positions.notional_bps IS 'Notional in basis points (1 bp = 0.01%)';
ALTER TABLE main.fin.positions ADD CONSTRAINT positions_pk PRIMARY KEY (position_id);
SET TAG ON TABLE main.fin.positions `system.certification_status` = `certified`;
SET TAG ON TABLE main.fin.positions_tmp `system.certification_status` = `deprecated`;
```

## 3.4 Curating a Genie space

| UC object | Put it in the space when… |
|---|---|
| **Managed tables** (gold, curated) | they hold the facts users ask about. Few, clean, well described |
| **Views** | you want to prejoin, filter, rename or hide complexity (e.g. one view instead of five raw tables) |
| **Metric views** | KPIs must be computed one governed way |
| **Parameterized example queries** | an anticipated question needs an exact, verified SQL (becomes a **trusted asset**) |
| **SQL functions** (UC) | logic too complex for a static query, or reusable with parameters (trusted asset; users need `EXECUTE`) |

Don't add: raw bronze tables, deprecated or duplicated derived tables, dozens of loosely related tables (start with ≤ 5), columns that
confuse (hide them).

## 3.5 Diagnosing AI Search configuration

**Reminder of the knobs:** index type (**Delta Sync** with CDF on the source, or **Direct Access** with your own upserts), sync mode
(**triggered** or **continuous**, continuous only on standard endpoints), endpoint type (standard or storage-optimized),
embeddings (managed: Databricks computes them from a text column; or self-managed vectors), `query_type` (**ANN** default,
**HYBRID** = vector + keyword with RRF, **FULL_TEXT** beta), **reranker** (`columns_to_rerank`), **filters**, `num_results`.

| Documented problem | Root cause | Most direct remediation |
|---|---|---|
| Agent cites text that has since been amended; the source table has the new text | **triggered** index not synced since the change | **sync after each ingestion run** (job task calling `index.sync()`). Continuous only if freshness within seconds is needed and worth the cost |
| Misses exact identifiers (SKUs, error codes, clause numbers) | pure ANN search | `query_type="HYBRID"` |
| Relevant chunk is retrieved but ranked 8th; top results are near-misses | ranking quality | enable the **reranker** (and rerank on the right columns) |
| Results from the wrong department / region / document type | no metadata filtering | add **filters** on metadata columns (and store that metadata in the index) |
| Many near-duplicate chunks fill the top-k | duplicated source docs or tiny overlapping chunks | dedupe at ingestion, fix chunking, lower k |
| Long chunks retrieved but the end of the chunk never matches | chunk longer than the **embedding model's context window**, so text was truncated | smaller chunks, or an embedding model with a longer window |
| Deleted documents still retrieved | Direct Access index without deletes, or no sync | delete via API / use Delta Sync, which propagates deletes |

> **Cost-effectiveness rule:** for data that changes once a day, a triggered sync scheduled right after the pipeline beats continuous
> sync and beats dropping and recreating the index.

## 3.6 RAG pipeline over a UC-governed corpus

1. Documents land in a **UC volume** (permissions by UC).
2. Parse with `ai_parse_document` (or a parser) into text, keeping **metadata** (source path, title, section, date, department).
3. Clean, mask PII, **chunk**, give each chunk a primary key.
4. Write chunks to a **Delta table with Change Data Feed** on.
5. Create a **Delta Sync AI Search index** (managed embeddings) on that table.
6. Expose it as a **retriever tool** (e.g. `VectorSearchRetrieverTool`, or the managed AI Search MCP server).
7. Inject results into context **with source metadata** for citations, clearly **delimited as data** (not instructions), and only the
   top few after reranking.
8. Trace with MLflow so the **RETRIEVER span** shows exactly what entered the context.

[[diagram:rag-uc]]

## 3.7 Chunking strategy

| Situation | Strategy |
|---|---|
| Mixed lengths, **no consistent headings**, both broad and narrow queries | **recursive character splitter**, ~512–1,024 tokens, **10–15 % overlap** (official sample answer) |
| Clear structure (Markdown headings, numbered clauses) | **structure-aware** (split on headings / sections), carry the heading as metadata |
| Need precise matching **and** broad context | **parent-child**: embed small chunks, return the parent section |
| Very short docs (FAQs) | one chunk per document is fine |
| Sentence-level chunks | too small: lose context and flood top-k. Rarely right |
| Whole long documents as one chunk "because the window is big" | one vector can't represent many topics, and retrieved tokens explode. Wrong |

**Embedding model context length:** text beyond it is **truncated** before embedding, so chunk size must fit
(e.g. `databricks-gte-large-en` 8,192 tokens, `databricks-bge-large-en` 512 tokens). Fitting is necessary, but a large window is no
reason to make chunks huge.

## 3.8 Retrieval failure modes: MLflow logs + UC metadata

Use the MLflow trace (RETRIEVER span: which chunks, from which source) and retrieval judges
(`RetrievalRelevance`, `RetrievalSufficiency`, `RetrievalGroundedness`), then check the source in UC (lineage, tags, owner, update time).

| Evidence | Failure mode | UC governance action |
|---|---|---|
| Retrieved chunks come from a **derived / copied / sandbox** table, not the source of truth | wrong source in the retrieval space | certify the authoritative asset, **deprecate** the derived one, rebuild the index only from the certified table, revoke the agent's access to derived schemas |
| Chunks are relevant but **outdated** | stale source or index | check lineage / freshness; fix the sync. Deprecate stale copies |
| **Sufficiency** low: the needed fact isn't in any retrieved chunk | coverage gap (doc not ingested or filtered out) | add the authoritative source to the governed corpus |
| Chunks from documents the user **shouldn't see** | permission gap | on-behalf-of-user auth, UC grants, row filters, separate indexes per audience |
| Relevance low on everything | query/embedding mismatch, chunking | not a governance issue: fix chunking, hybrid, reranker |

## 3.9 Constraining retrieval to authoritative sources (before deployment)

[[diagram:authoritative]]

1. **Classify assets**: authoritative (gold, owned, certified) vs derived (copies, aggregates, sandboxes, staging).
2. **Mark them in UC**: `system.certification_status = certified` / `deprecated`, plus your own governed tags (e.g. `data_tier = gold`).
3. **Build indexes and Genie spaces only from certified sources.** Use lineage to verify where each source comes from.
4. **Restrict access**: the agent's service principal (or the user, on-behalf-of) gets `SELECT` only on the authoritative schema.
   Derived schemas aren't granted.
5. **Filter in retrieval** on metadata (e.g. `source_tier = 'authoritative'`) as defense in depth.
6. **Evaluate** before deployment: check that the RETRIEVER spans only cite authoritative sources.

> **Exam pattern:** "prompt the agent to prefer official sources" is weak. Governance happens in **UC and the index definition**, so
> derived data never enters the retrieval space.

## 3.10 Governing what enters the context: PII, quality, policy

The exam guide's audience description says governance of what enters the context relies on Unity Catalog's metadata layer:
**data quality, PII handling and policy enforcement**. The rule is the same as in §3.9: enforce it **in UC, before retrieval**, not with a
prompt instruction.

| Concern | UC mechanism | Effect on the agent's context |
|---|---|---|
| Find sensitive columns | **Data classification** detects PII (names, emails, ids…) and applies **governed tags** | you know which sources need protection before indexing them |
| Hide or redact sensitive values | **Column masks** (`ALTER TABLE … ALTER COLUMN … SET MASK fn`) | the agent (or the user, on-behalf-of) sees redacted values in query results |
| Restrict which rows are visible | **Row filters** (`ALTER TABLE … SET ROW FILTER fn ON (col)`) | queries return only permitted rows |
| Apply both at scale | **ABAC policies** on governed tags | one policy protects every table carrying the tag |
| Keep PII out of a vector index | mask or drop PII **before chunking** (step 3 in §3.6), index only the cleaned table | embeddings and retrieved chunks never contain the raw values |
| Low-quality or stale data | expectations / constraints in pipelines, data quality monitoring, freshness checks via lineage | bad rows are stopped or flagged before they become context |

> **Exam pattern:** "the agent quoted a customer's phone number from a retrieved chunk" → mask/remove PII before indexing (and apply
> masks on the source), not "tell the model never to reveal phone numbers". Note: a column mask on the source table does not
> retroactively clean text already embedded in an index; re-index from the cleaned table.

### Quick self-check

- The index answers with last week's text and the source table is correct. Index type Delta Sync, triggered. Fix? *(sync after the ingestion job)*
- Users search by error code `E-4012` and get unrelated results. *(hybrid search)*
- Pre-inference or just-in-time for an agent reconciling invoices against live order tables? *(just-in-time)*
- Retrieved chunks come from `sandbox.tmp_policies`. Governance fix? *(deprecate it, certify the source, rebuild the index from certified data, remove access)*
- Retrieved chunks contain customers' email addresses. Fix? *(mask/remove PII before chunking, re-index the cleaned table; masks or ABAC on the source)*
