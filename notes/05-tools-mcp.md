---
id: d5
title: "Section 5: Tool Design, MCP, and Agent Context"
weight: 13
---

# Section 5: Tool Design, MCP, and Agent Context (13%)

> 🗺️ **Visual learner?** Progressive disclosure, tool-result clearing and Agent Skills are drawn in the [Visual guide](#/notes/visual).

**Objectives**

1. Apply progressive disclosure to MCP tool access (staged tool discovery with context-efficient execution) to reduce token usage compared to raw tool dumps
2. Given two MCP tool descriptions an agent keeps confusing, identify the overlap causing ambiguous selection
3. Explain how progressive disclosure controls how much tool information enters the context at each stage, and why staging uses fewer tokens than loading full schemas up front
4. Given a deep message history near capacity, evaluate which raw tool outputs are candidates for clearing
5. Given a task and UC-registered tools (names, descriptions, parameter schemas), identify the most appropriate tool and justify it by functional fit, input/output compatibility and task requirements
6. Given a system prompt overloaded with rarely-invoked capability instructions, identify candidates for packaging as Agent Skills and select the loading strategy that minimizes baseline context cost without harming task success

---

## 5.1 Tools are context

Every tool you register costs tokens **on every call**: its name, description and full JSON schema sit in the context. Tool
**outputs** cost tokens too, and they stay in the history. Good tool design is context design:

- **Distinct purpose, minimal overlap.** If a human engineer can't say which tool to use, neither can the model.
- **Descriptive names with a namespace**: `orders_get_status`, `orders_search`, `billing_get_invoice`.
- **Descriptions that say when to use it, and when not**: "Use for the current status of ONE order by id. For searching orders by
  customer or date, use `orders_search`."
- **Typed, unambiguous parameters**: `order_id: str (e.g. 'ORD-1182')`, enums instead of free text.
- **Token-efficient outputs**: only the needed fields, sensible defaults for `limit`, pagination, filters, human-readable values
  (names rather than opaque UUIDs), short actionable error messages.

## 5.2 Diagnosing ambiguous tool selection

When an agent keeps confusing two tools, compare their **descriptions** for overlap in:

| Overlap | Example |
|---|---|
| same verb + object | "Gets order information" vs "Retrieves order details" |
| same inputs, no difference stated | both take `order_id` and nothing says what differs |
| outputs not described | the model can't tell that one returns shipping status and the other the invoice |
| scope not stated | both "search orders": one over the last 30 days, one the archive, but neither says so |

**Fixes, in order:** rewrite the descriptions with **distinct capability descriptors** (what each returns, when to use, when not);
merge true duplicates into one tool with a clear parameter; remove unused tools. Adding a system-prompt rule ("prefer tool A")
is a weaker patch.

## 5.3 Progressive disclosure for MCP tools

A large MCP server (say 60 tools) dumped into the context costs thousands of tokens per call and causes **confusion**. Progressive
disclosure loads tool information **in stages**, only as deep as needed:

| Stage | What enters the context | Size |
|---|---|---|
| 0. Index | a short catalog: tool (or tool group) names + one-line capability descriptors, or a single `search_tools` tool | tiny |
| 1. Discovery | the agent searches or browses by intent; the discovery step **scores candidates against the user's intent** and returns only the best match(es) | small |
| 2. Schema | the **full schema of the selected tool only** | one schema |
| 3. Execution | the tool runs and returns a **scoped result** (filtered, aggregated, or processed in code before it reaches the model) | small |

**Why it saves tokens:** unused tools' schemas never enter the window, and large intermediate results are filtered before the model
sees them. (Anthropic's code-execution-with-MCP write-up reports one workflow dropping from ~150k to ~2k tokens.)

[[diagram:progressive-disclosure]]

**Official sample-question lesson:** four near-duplicate order tools are all surfaced → enrich each tool's metadata with **distinct
capability descriptors** in the registry, and have discovery **score against intent and surface only the single best schema**.
Ranking the four **after** loading them all into context doesn't save the tokens.

## 5.4 Which tool outputs to clear

**Tool result clearing** is the lightest form of compaction: replace old, raw tool outputs deep in the history with a short stub, and
keep the call itself (so the model knows it happened).

| Clear it (candidates) | Keep it |
|---|---|
| large raw payloads (full JSON, file contents, search result lists) **already digested**: a later message states what was learned | the **most recent** results, still being worked on |
| results that can be **re-fetched** cheaply and deterministically | results the **pending steps still depend on** |
| superseded results (an earlier query re-run with better filters) | results that **can't be reproduced**: write confirmations, ids returned by a create, one-time codes |
| failed / empty results whose lesson is captured | user-provided information |

```text
[tool_result cleared: orders_search(customer="ACME", since="2026-01-01") returned 214 rows;
 key finding recorded in turn 12: 3 orders delayed (ORD-1182, ORD-1190, ORD-1207)]
```

[[diagram:tool-clearing]]

## 5.5 Choosing the right UC tool

UC functions (SQL or Python) become agent tools through managed MCP or toolkits; their **comments become the descriptions**, and their
**parameter types become the schema**. Pick by:

| Criterion | Question to ask |
|---|---|
| **Functional fit** | Does it do exactly the subtask (read vs write, the right entity, the right granularity)? |
| **Input compatibility** | Does the agent *have* every required input at this point, in the right type and format (an id vs a name, a date vs free text)? |
| **Output compatibility** | Does it return what the next step needs (the fields, the unit, one row vs a list)? |
| **Task requirements** | latency, freshness, permissions (who executes it), side effects |

Example: the task is "check whether order ORD-1182 is delayed". `orders_get_status(order_id STRING)` (returns status + ETA) beats
`orders_search(customer STRING, from DATE, to DATE)` (needs inputs the agent doesn't have, returns a list) and beats
`orders_update(order_id, status)` (a write).

## 5.6 Agent Skills: keep rarely used instructions out of the baseline

An **Agent Skill** is a folder with a `SKILL.md` (YAML front matter `name` + `description`, then instructions) plus optional
reference files and scripts. Loading is **progressive**:

1. **Metadata only** (name + description of every skill) sits in the system prompt: a few dozen tokens per skill.
2. The **SKILL.md body** loads only when the model decides the skill is relevant.
3. **Linked files** (reference docs, scripts) load only when that part of the task needs them.

| Good skill candidates | Keep in the system prompt |
|---|---|
| **rarely invoked**, self-contained capabilities (e.g. "generate the quarterly regulatory XML export", "handle a GDPR deletion request") | identity, safety and compliance rules that apply to **every** turn |
| long procedures, templates, reference tables | the core task definition and output format |
| capabilities used by a minority of conversations | instructions needed to decide *whether* to use a skill (that's the skill's description) |

**Loading strategy that minimizes baseline cost without hurting success:** metadata always loaded, body on demand. A **clear,
specific description** is what makes on-demand loading reliable; a vague description means the skill isn't loaded when needed.
Loading every skill body up front defeats the purpose, and dropping the capability entirely hurts task success.

[[diagram:skills]]

## 5.7 MCP on Databricks (recap from the GenAI exam)

| Kind | What | Example URL / notes |
|---|---|---|
| **Managed** MCP servers | hosted by Databricks over your governed assets | `/api/2.0/mcp/functions/{catalog}/{schema}` (UC functions), `/api/2.0/mcp/vector-search/{catalog}/{schema}` (AI Search), `/api/2.0/mcp/genie/{space_id}`, DBSQL |
| **External** MCP servers | third-party servers reached through a **UC connection** (credentials stored in UC, managed OAuth) | GitHub, web search… |
| **Custom** MCP servers | your own server hosted as a **Databricks App** | proprietary APIs |

Clients: `DatabricksMCPClient` (databricks-mcp) and `DatabricksMultiServerMCPClient` (databricks-langchain). Permissions are UC
permissions: the agent can only call functions and read indexes its identity is allowed to.

### Quick self-check

- 80 MCP tools; token usage per turn is huge and tool choice inconsistent. *(progressive disclosure: index → discover by intent → load one schema → scoped result)*
- Which tool result is *not* safe to clear: a 5k-row search done 30 turns ago that was summarized, or the order id returned by `orders_create` 3 turns ago? *(keep the create result)*
- The system prompt has a 2,000-token section for a yearly audit export used in 1 % of chats. *(package as an Agent Skill, metadata-only baseline)*
