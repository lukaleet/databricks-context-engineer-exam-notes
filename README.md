# Databricks Context Engineer Associate: Exam Prep

An interactive study guide for the **Databricks Certified Context Engineer Associate** exam (the exam version available from
**July 29, 2026**), built as a two-week sprint for someone coming straight from the GenAI Engineer Associate exam.

**▶ Open the interactive guide: https://lukaleet.github.io/databricks-context-engineer-exam-notes/**

| What | Where |
|---|---|
| 📅 14-day plan as a checklist (start date alignable to your exam, with a "Today" card on the dashboard) | [`plan/daily-plan.yaml`](plan/daily-plan.yaml) and the site's *Daily plan* |
| 📚 Study notes for every exam objective (7 sections + exam overview & traps + study plan) | [`notes/`](notes/) and the site |
| 🗺️ Visual guide: 20 diagrams of the mechanisms the exam tests (also embedded in the section notes) | [`notes/10-visual-guide.md`](notes/10-visual-guide.md), drawn by [`scripts/diagrams.py`](scripts/diagrams.py) |
| 🩺 Symptom → fix cheat sheet, with the tempting wrong answer for each row | [`notes/08-cheatsheet.md`](notes/08-cheatsheet.md) |
| 🌉 GenAI → Context Engineer bridge: what carries over, what's new, which product names changed | [`notes/09-genai-bridge.md`](notes/09-genai-bridge.md) |
| ✍️ 166 exam-style scenario questions (single & multiple-selection) with explanations | [`questions/`](questions/) and the site's *Practice* page |
| ⏱️ Timed mock exams: 45 questions, 90 minutes, weighted by section | Site → *Mock exam* |
| 🧩 6 multi-step scenarios (forgetful agent, long research agent, treasury Genie space, 60-tool MCP server…) | [`scenarios/`](scenarios/) and the site |
| 🃏 Flashcards + glossary (91 terms) | Site → *Flashcards*, *Glossary* |
| 🧪 8 hands-on labs that run **locally with only the Python standard library**, or on Databricks with a real model and Lakebase | [`labs/`](labs/) |

## Exam at a glance

About 45 scored multiple-choice / multiple-selection questions · 90 minutes · online proctored · USD 200 · valid 2 years · code in Python
(some SQL).

| Section | Weight |
|---|---|
| 1. Foundations of Context Engineering | 16% |
| 2. System Prompt and Instruction Design | 9% |
| 3. Knowledge Retrieval and Genie Configuration | 20% |
| 4. Memory Architecture with Lakebase and MLflow | 18% |
| 5. Tool Design, MCP, and Agent Context | 13% |
| 6. Context Compression and Compaction | 11% |
| 7. Multi-Agent and Long-Horizon Task Design | 13% |

Almost every question is *"given this failure, pick the most direct fix"*. See [`notes/00-exam-overview.md`](notes/00-exam-overview.md)
for the question patterns, the lessons from the official sample questions, and the distractors that are almost always wrong.

## Hands-on labs

Each lab is a Databricks notebook in **source format** that is **also a plain Python script** (`# %%` cell markers work in VS Code / PyCharm).

**Locally:** Python 3.10+, no packages needed. Where a lab would call an LLM it uses a deterministic offline stand-in and says so.

```bash
python labs/00_setup.py
pip install langgraph          # optional: Lab 04 then uses the real LangGraph checkpointer and store
```

**On Databricks (including Free Edition):** clone this repo as a **Git folder** (or *Workspace → Import → URL* with a lab's *Raw* link).
The labs call a pay-per-token Foundation Model endpoint through the OpenAI-compatible client; if `openai` is missing, run
`%pip install -U openai databricks-sdk`. Lab 04 uses **Lakebase** when you set `LAKEBASE_INSTANCE` and install
`databricks-langchain[memory]`.

| Lab | Topic | Sections |
|---|---|---|
| 00 | Setup, token counting, what a context is made of | §1 |
| 01 | Diagnosing failure modes, a needle test to find the degradation knee, thinking budgets in long loops | §1 |
| 02 | Few-shot selection by marginal coverage, prompt ablation logged to MLflow | §2 |
| 03 | Recursive splitter, ANN vs keyword vs hybrid (RRF), stale triggered index, authoritative-only retrieval | §3 |
| 04 | Checkpointer by `thread_id`, long-term store by user, semantic vs SQL memory routing, over/under-retrieval, intent first, state tables | §4 |
| 05 | Progressive disclosure token math, overlapping tool descriptions, tool-result clearing, Agent Skills | §5 |
| 06 | Sliding window vs three compaction prompts, recall-then-precision, what's safe to remove | §6 |
| 07 | Dispatch with a trace summary, condensed returns, boundary placement, long-horizon strategy fit | §7 |

All labs were run end to end locally (Python 3.10, with and without LangGraph).

## Working on the content

Content is plain Markdown/YAML. The site (`docs/`) is static HTML/JS with no framework.

```bash
pip install pyyaml markdown
python3 scripts/build.py            # validates questions, renders diagrams, regenerates docs/data/content.js
python3 -m http.server -d docs 8000 # preview at http://localhost:8000
```

**Diagrams:** each one is a function in `scripts/diagrams.py`. Put `[[diagram:<id>]]` on its own line in any note to embed it. Colours
come from CSS variables (`--dg-*`), so diagrams follow the light/dark theme. The build fails if a label doesn't fit its box.

Question format (`questions/*.yaml`). Backticks render as code, and `code:` adds a code block under the stem:

```yaml
- id: d6-99
  objective: Identify which content is safe to remove during compaction
  q: >-
    Which item is safe to remove?
  options: ['A raw tool output already summarized', 'The user''s budget', '...', '...']
  answer: [A]          # letters; the count must match "TWO"/"THREE" in the stem
  explain: >-
    Why the right answer is right and the others are wrong.
```

## Sources & disclaimer

The exam outline comes from the official Databricks exam guide (version available from July 29, 2026). Databricks facts were checked
against [docs.databricks.com](https://docs.databricks.com) in October 2026 and, for the memory classes, against the
`databricks-langchain` 0.21 and MLflow 3.17 sources. Concepts follow the public context-engineering literature the exam is built on:
Drew Breunig's *How Long Contexts Fail* / *How to Fix Your Context*, Anthropic's *Effective context engineering for AI agents*,
*Code execution with MCP* and *Agent Skills*, and Cognition's *Don't Build Multi-Agents*. Check the
[official exam page](https://www.databricks.com/learn/certification/context-engineer-associate) again about two weeks before your exam.

These are personal study materials. They are **not affiliated with or endorsed by Databricks** and contain **no real exam questions**.
All practice questions are original.
