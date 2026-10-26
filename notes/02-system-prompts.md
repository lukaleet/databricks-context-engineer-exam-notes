---
id: d2
title: "Section 2: System Prompt and Instruction Design"
weight: 9
---

# Section 2: System Prompt and Instruction Design (9%)

> 🗺️ **Visual learner?** What goes where in a Genie space is drawn in the [Visual guide](#/notes/visual).

**Objectives**

1. Given a business domain, select and validate the instructions, sample questions, and trusted SQL assets that together produce a production-ready Genie space
2. Given an agent, candidate few-shot examples and a token budget, justify which examples to include or exclude based on their marginal contribution (covering untested tool paths, demonstrating output structure, handling ambiguous inputs)
3. Given a miscalibrated system prompt and its observed failure pattern, select the targeted revision that resolves the failure with the least increase in token cost and maintenance burden
4. Given experiment tracking results comparing two system prompt configurations, determine whether the higher-token configuration is justified and identify the prompt element driving the cost-performance tradeoff

---

## 2.1 The right altitude

A system prompt fails in one of two directions:

| Too low (over-specified) | Right altitude | Too high (under-specified) |
|---|---|---|
| long `if X then say Y` rules for every edge case; brittle, expensive to maintain, breaks on cases nobody listed | clear role, goal, principles **with the reason**, tool guidance, output format; specific enough to steer, general enough to let the model judge | "Be a helpful assistant." Assumes context the model doesn't have |

**Good structure:** short sections (Markdown headers or XML tags) such as `<role>`, `<background>`, `<instructions>`,
`<tool_guidance>`, `<output_format>`. Start minimal, test on the best model you'll use, then **add instructions only for failures you
observed**.

## 2.2 Miscalibrated prompts: targeted revisions

The exam asks for the revision that fixes the failure **with the least extra tokens and maintenance**. Match the symptom:

| Observed failure | Likely cause in the prompt | Targeted revision |
|---|---|---|
| Agent follows a rule in situations where it shouldn't (over-triggering, e.g. always escalates) | absolute or SHOUTED rule ("ALWAYS", "MUST") without scope | scope the rule and give the reason ("escalate only when X, because Y") |
| Agent handles listed cases but fails on slight variations | brittle enumerated rules | replace the list with the **underlying principle** + one example |
| Agent ignores formatting | format buried in the middle, or conflicting examples | one explicit output spec (or structured output / JSON schema), consistent examples |
| Two behaviours alternate unpredictably | **conflicting instructions** (clash) | remove or reconcile the conflict; state which instruction wins |
| Prompt is huge, baseline cost is high, most capabilities rarely used | rarely-used capability instructions loaded every turn | move them to **Agent Skills** loaded on demand (see §5) |
| Answers use stale facts written into the prompt | dynamic data hard-coded in instructions | move the data to retrieval or a tool |
| Vague, generic answers | too little context about the domain / audience | add the missing background, not more rules |

> **Distractor:** "append more rules and several examples for every failure seen" fixes this one failure but grows cost and
> maintenance, and adds clash risk. The exam prefers the **smallest principled change**.

## 2.3 Choosing few-shot examples under a token budget

Examples are expensive (each one repeats a full input → output). Keep an example only if it adds **marginal value**:

| Keep it if it… | Drop it if it… |
|---|---|
| covers a **tool path** no other example or instruction covers | demonstrates the same path as another example |
| demonstrates the **exact output structure** you need (and the instruction alone failed) | only restates what an instruction already says clearly |
| shows how to handle an **ambiguous input** (e.g. ask a clarifying question) | covers a rare edge case that a one-line rule handles cheaper |
| is **diverse** from the others (different intent, length, phrasing) | is long and nearly identical to another one |

Pitfalls: models **copy surface details** of examples (names, lengths, values), so vary them; a list of edge cases as examples is worse
than a few **diverse, canonical** examples. Validate the choice with an evaluation run (§2.5): remove an example and check whether
the metric moves.

## 2.4 Genie space instructions: what goes where

A Genie space (now also called a *Genie Agent*) is "instruction design" for text-to-SQL. Each kind of knowledge has a proper home:

| Knowledge | Where it goes | Example |
|---|---|---|
| What a table / column means | **UC table and column comments** (descriptions); space-level descriptions and **synonyms** in the knowledge store | `bps_amt`: "amount in basis points"; synonym "revenue" → `net_sales` |
| Which values a column holds | **Prompt matching**: format assistance + **entity matching** (up to 120 string columns) | "Florida" → `FL`, avoiding `ILIKE '%Florida%'` |
| How tables join | **Join relationships** (UC PK/FK are picked up automatically) | `orders.customer_id = customers.id`, many-to-one |
| Business metrics and conditions | **SQL expressions**: **measures**, **filters**, **fields** (dimensions) | measure `win_rate`, filter `large_orders`, field `deal_size_tier` |
| Complex or multi-step question patterns | **Example SQL queries** (optionally parameterized) | "top 10 customers by revenue last quarter" |
| Verified answers for anticipated questions | **Trusted assets** = parameterized example queries + **UC SQL functions** | response marked *Trusted / verified*; users need `EXECUTE` on the function |
| Global context and **domain vocabulary**, fiscal calendar, formatting, when to ask for clarification | **General text instructions** (keep them few and organized) | "'bps' = basis points; 'last fixing' = latest ECB reference rate date" |
| Starter prompts shown to business users | **Sample questions** | these help users get started; **they don't teach Genie anything** |
| Measuring accuracy | **Benchmarks** (questions with expected SQL / answers) | run before and after each change |

[[diagram:genie-config]]

**Order of fixes (Databricks best practices):** clean, small data (≤ 5 tables to start, prejoined views or metric views, hidden
irrelevant columns) → good UC descriptions and synonyms → SQL expressions for business terms → example SQL for complex questions →
text instructions for what nothing else covers → re-test with benchmarks. Make sure instructions don't conflict with example SQL.

**Official sample-question lesson:** Genie handles numbers fine but misreads **domain jargon** ("rates desk", "bps", "last fixing")
→ define the vocabulary in **general instructions**. Sample questions don't teach terminology, and trusted assets only cover the
exact queries you registered.

**Limits worth knowing:** up to 50 tables/views/metric views per space (start with ≤ 5); the knowledge store holds up to 200 snippets
(table descriptions, joins, SQL expressions); up to 100 instructions (each example SQL, each SQL function and the general instruction
block count as one).

**Production-ready checklist:** curated (ideally certified) tables, descriptions on ambiguous columns, SQL expressions for KPIs,
trusted assets for the regulatory/critical queries, clear general instructions, benchmarks passing, users have access to the space,
`CAN USE` on the SQL warehouse and `SELECT` on the data (Genie respects their UC permissions).

## 2.5 Comparing two prompt configurations in MLflow

You run both configurations on the **same evaluation dataset** with `mlflow.genai.evaluate()` and log quality metrics plus **token
usage / cost and latency** per run. Then:

1. **Is the higher-token configuration justified?** Only if its quality gain is meaningful on the metrics that matter for the use case
   **and** the extra cost per request is acceptable at production volume. A +0.5 % correctness gain for +60 % tokens usually isn't.
2. **Which element drives the tradeoff?** Do an **ablation**: remove one element at a time (the examples, the long policy section,
   the tool guidance) and re-run. The element whose removal loses the quality is the one worth its tokens. The others are cost.
3. Keep prompt versions in the **MLflow Prompt Registry** so each run is tied to a prompt version.

| Comparison | Interpretation |
|---|---|
| B costs +40 % tokens, all metrics equal | not justified: keep A |
| B costs +40 % tokens, correctness +12 pts on the hard subset | probably justified: find which added element produced the gain and keep only that |
| B better on average but worse on one metric (e.g. safety) | not "more reliable" if that metric matters |

### Quick self-check

- Genie misreads "QoQ" and "the EMEA book". Where do you define these terms? *(general instructions or SQL expressions with synonyms if it's a computable filter/measure; not sample questions)*
- Which of 8 few-shot examples would you keep with a budget for 3? *(the ones covering distinct tool paths, the required output structure, and an ambiguous input)*
- How do you find which prompt element justifies its tokens? *(ablation runs in one MLflow experiment)*
