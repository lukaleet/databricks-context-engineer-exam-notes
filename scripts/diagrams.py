"""Diagrams for the Visual guide page (and section notes), drawn as inline SVG.

Each diagram is a function returning a Diagram. Notes reference them with a line `[[diagram:<id>]]`,
which scripts/build.py replaces with the rendered <figure>. Colours come from CSS classes in
docs/assets/style.css (k-data, k-model, ...) so every diagram follows the light/dark theme.

Box kinds (the colour code, shown as a legend on the page):
  data  = UC tables and volumes, AI Search indexes, Lakebase memory and state
  model = LLM calls, the context window, summaries the model writes
  tool  = agent tools, MCP servers, Genie, skills, sub-agents
  gov   = governance, and what must not be lost (constraints) or goes wrong (failures)
  eval  = MLflow tracing and evaluation
  app   = users, your agent / orchestrator code
  plain = everything else
"""
from html import escape

LABEL_PX, SUB_PX = 13, 11
CHAR_W = {"label": 0.62 * LABEL_PX, "sub": 0.56 * SUB_PX, "mono": 0.61 * SUB_PX}
warnings = []


class Diagram:
    def __init__(self, did, w, h, claim, caption):
        self.id, self.w, self.h, self.claim, self.caption = did, w, h, claim, caption
        self.els, self.boxes = [], {}

    # ---------- primitives ----------
    def box(self, key, x, y, w, h, label, sub=(), kind="plain", num=None, mono=False, accent=False, top=False):
        """A rounded box. `label` may contain '\n'. `sub` is a list of smaller lines (mono=True for code)."""
        self.boxes[key] = (x, y, w, h)
        labels = label.split("\n") if label else []
        sub = [sub] if isinstance(sub, str) else list(sub)
        cls = f"dg-box k-{kind}" + (" dg-hl" if accent else "")
        out = [f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/>']
        block = len(labels) * 16 + len(sub) * 14
        ty = y + (16 if top else (h - block) / 2) + 12
        for line in labels:
            self._fit(key, line, "label", w)
            out.append(f'<text class="dg-label" x="{x + w / 2}" y="{ty:.1f}" text-anchor="middle">{escape(line)}</text>')
            ty += 16
        for line in sub:
            self._fit(key, line, "mono" if mono else "sub", w)
            out.append(f'<text class="dg-sub{" dg-mono" if mono else ""}" x="{x + w / 2}" y="{ty:.1f}" text-anchor="middle">{escape(line)}</text>')
            ty += 14
        if num is not None:
            out.append(f'<circle class="dg-num" cx="{x}" cy="{y}" r="10"/>'
                       f'<text class="dg-numt" x="{x}" y="{y + 4}" text-anchor="middle">{num}</text>')
        self.els.append("".join(out))
        return self

    def chip(self, x, y, w, text, kind="plain", h=20, mono=True):
        """A small pill (versions, aliases, strips). Not an arrow target."""
        self.els.append(f'<rect class="dg-box k-{kind}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}"/>'
                        f'<text class="dg-sub{" dg-mono" if mono else ""} dg-strong" x="{x + w / 2}" y="{y + h / 2 + 4}" text-anchor="middle">{escape(text)}</text>')
        return self

    def rect(self, x, y, w, h, kind="plain", accent=False, rx=4):
        self.els.append(f'<rect class="dg-box k-{kind}{" dg-hl" if accent else ""}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"/>')
        return self

    def group(self, x, y, w, h, label, kind="plain", bottom=False):
        ly = y + h - 10 if bottom else y + 18
        self.els.append(f'<rect class="dg-group k-{kind}" x="{x}" y="{y}" width="{w}" height="{h}" rx="12"/>'
                        f'<text class="dg-glabel" x="{x + 12}" y="{ly}">{escape(label)}</text>')
        return self

    def text(self, x, y, s, cls="dg-note", anchor="start"):
        self.els.append(f'<text class="{cls}" x="{x}" y="{y}" text-anchor="{anchor}">{escape(s)}</text>')
        return self

    def line(self, pts, dashed=True, cls="dg-guide"):
        d = " ".join(f"{px},{py}" for px, py in pts)
        self.els.append(f'<polyline class="{cls}{" dg-dash" if dashed else ""}" points="{d}" fill="none"/>')
        return self

    def anchor(self, key, side, off=0.0):
        """Point on a box edge. side in l/r/t/b; off in [-0.5, 0.5] slides along the edge."""
        x, y, w, h = self.boxes[key]
        return {"l": (x, y + h / 2 + off * h), "r": (x + w, y + h / 2 + off * h),
                "t": (x + w / 2 + off * w, y), "b": (x + w / 2 + off * w, y + h)}[side]

    def arrow(self, a, b, label=None, sides=None, via=(), dashed=False, hot=False, lpos=None, lanchor="middle",
              aoff=0.0, boff=0.0):
        """Arrow from a to b. a/b are box keys or (x, y) points. sides='rl' means leave a's right edge,
        enter b's left edge; omitted sides are chosen from the relative position. `hot` = accent colour."""
        def center(k):
            if isinstance(k, tuple):
                return k
            x, y, w, h = self.boxes[k]
            return (x + w / 2, y + h / 2)
        ca, cb = center(a), center(b)
        if sides is None:
            dx, dy = cb[0] - ca[0], cb[1] - ca[1]
            sides = ("rl" if dx > 0 else "lr") if abs(dx) >= abs(dy) else ("bt" if dy > 0 else "tb")
        p0 = a if isinstance(a, tuple) else self.anchor(a, sides[0], aoff)
        p1 = b if isinstance(b, tuple) else self.anchor(b, sides[1], boff)
        pts = [p0, *via, p1]
        d = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        marker = f"{self.id}-ah" if hot else f"{self.id}-a"
        cls = "dg-edge" + (" dg-hot" if hot else "") + (" dg-dash" if dashed else "")
        out = [f'<polyline class="{cls}" points="{d}" fill="none" marker-end="url(#{marker})"/>']
        if label:
            if lpos is None:   # middle of the longest segment, nudged above horizontal lines
                segs = list(zip(pts, pts[1:]))
                (sx, sy), (ex, ey) = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
                lpos = ((sx + ex) / 2, (sy + ey) / 2 - (6 if abs(ex - sx) >= abs(ey - sy) else -4))
            out.append(f'<text class="dg-elabel" x="{lpos[0]:.1f}" y="{lpos[1]:.1f}" text-anchor="{lanchor}">{escape(label)}</text>')
        self.els.append("".join(out))
        return self

    # ---------- output ----------
    def _fit(self, key, line, kind, w):
        need = len(line) * CHAR_W[kind] + 14
        if need > w:
            warnings.append(f"{self.id}/{key}: '{line}' needs ~{need:.0f}px, box is {w}px")

    def svg(self):
        defs = (f'<defs>'
                f'<marker id="{self.id}-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="dg-head" d="M0,0 L10,5 L0,10 z"/></marker>'
                f'<marker id="{self.id}-ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="dg-head dg-hot" d="M0,0 L10,5 L0,10 z"/></marker>'
                f'</defs>')
        return (f'<svg class="dg" viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.claim)}" '
                f'xmlns="http://www.w3.org/2000/svg">{defs}{"".join(self.els)}</svg>')

    def figure(self):
        return (f'<figure class="diagram" id="dg-{self.id}">'
                f'<div class="fig-scroll" style="--fig-min:{min(self.w, 640)}px">{self.svg()}</div>'
                f'<figcaption>{escape(self.caption)}</figcaption></figure>')




# =====================================================================================
# The diagrams
# =====================================================================================

# ---------- §1 Foundations ----------

def context_anatomy():
    d = Diagram("context-anatomy", 880, 250,
                "The same 200k-token context window filled two ways: unmanaged, where tool schemas, raw tool results and "
                "history crowd out the task, and engineered, where only high-signal tokens remain.",
                "What fills the window on one call. Unmanaged agents spend most tokens on tool schemas, raw tool results and "
                "old history. Engineered context keeps the same elements, each trimmed to what this step needs, and stays "
                "well below the quality knee.")
    parts = [("instructions", "app"), ("tool schemas", "tool"), ("examples", "app"), ("retrieved", "data"),
             ("memory", "data"), ("history", "model"), ("tool results", "tool")]
    x = 150
    for name, kind in parts:
        w = len(name) * 7 + 28
        d.chip(x, 14, w, name, kind=kind, mono=False)
        x += w + 8
    x0, W = 150, 700
    for row, (label, sizes) in enumerate([("Unmanaged", [2, 18, 6, 14, 6, 22, 26]), ("Engineered", [2, 3, 3, 6, 2, 6, 4])]):
        y = 64 + row * 74
        d.text(20, y + 22, label, cls="dg-label")
        d.text(20, y + 38, f"{sum(sizes)}% of the window", cls="dg-sub")
        x = x0
        for (name, kind), pct in zip(parts, sizes):
            w = W * pct / 100
            d.rect(x, y, w, 36, kind=kind, accent=(row == 0 and name in ("tool schemas", "tool results")))
            x += w
        d.rect(x, y, x0 + W - x, 36, kind="plain")
        if row == 1:
            d.text(x + 12, y + 23, "free: room to work before compaction", cls="dg-sub")
    kx = x0 + W * 0.7
    d.line([(kx, 52), (kx, 196)])
    d.text(kx, 214, "quality knee (~70%)", cls="dg-note dg-govtext", anchor="middle")
    d.text(x0 + W, 214, "hard limit", cls="dg-note", anchor="end")
    d.text(20, 240, "Every token competes for the same attention budget: n tokens → n² pairwise relationships.", cls="dg-note dg-strong")
    return d


def failure_modes():
    d = Diagram("failure-modes", 880, 262,
                "The four context failure modes: poisoning, distraction, confusion and clash, each with its trace "
                "signature and most direct fix.",
                "Ask two questions of the trace: is the bad content wrong or just irrelevant, and is the problem one item or "
                "sheer length? That separates the four modes.")
    cells = [("p", 20, 20, "Context poisoning", "gov",
              ["an error or hallucination enters the context", "and is referenced again and again",
               "fix: remove it, validate before writing", "to memory/summaries, restart clean"]),
             ("d", 450, 20, "Context distraction", "model",
              ["context so long the model over-relies on it", "and repeats history instead of planning",
               "fix: compaction, keep the window short", ""]),
             ("c", 20, 132, "Context confusion", "data",
              ["superfluous content (old session, unneeded", "tools, irrelevant docs) is USED in the answer",
               "fix: remove it: tool loadout, scoped", "retrieval, pruning"]),
             ("x", 450, 132, "Context clash", "tool",
              ["two pieces of context contradict each other", "(instructions vs retrieved text, early wrong turn)",
               "fix: prune or reconcile, say which source wins", ""])]
    for k, x, y, label, kind, sub in cells:
        d.box(k, x, y, 410, 100, label, [s for s in sub if s], kind=kind)
    d.text(440, 254, "wrong + reused → poisoning · irrelevant + used → confusion · contradiction → clash · too long → distraction",
           cls="dg-note dg-strong", anchor="middle")
    return d


def degradation():
    d = Diagram("degradation", 880, 306,
                "Answer quality against context fill: flat at first, then dropping past a knee well before the hard limit. "
                "Compaction is triggered before the knee.",
                "Context rot: quality falls before the window is full. Measure it with MLflow (quality per turn against "
                "context size), then compact or clear before the knee. A bigger window only moves the hard limit.")
    ox, oy, W, H = 90, 250, 740, 200
    d.line([(ox, oy - H), (ox, oy), (ox + W, oy)], dashed=False, cls="dg-edge")
    d.text(ox - 10, oy - H + 4, "quality", cls="dg-sub", anchor="end")
    d.text(ox + W, oy + 38, "context fill →", cls="dg-sub", anchor="end")
    for f in (0, 25, 50, 75, 100):
        d.text(ox + W * f / 100, oy + 20, f"{f}%", cls="dg-sub", anchor="middle")
    pts = [(ox + W * f / 100, oy - H * q) for f, q in
           [(0, .92), (20, .92), (40, .91), (55, .89), (65, .84), (75, .72), (85, .55), (95, .40), (100, .34)]]
    d.line(pts, dashed=False, cls="dg-edge dg-hot")
    kx = ox + W * 0.68
    d.line([(kx, oy - H - 10), (kx, oy)])
    d.text(kx - 6, oy - H + 6, "compact here", cls="dg-note dg-oktext", anchor="end")
    d.line([(ox + W, oy - H - 10), (ox + W, oy)])
    d.text(ox + W - 6, oy - H + 6, "hard limit", cls="dg-note", anchor="end")
    d.text(ox + W * 0.80, oy - H * 0.62 - 26, "knee: mis-citations,", cls="dg-note dg-govtext")
    d.text(ox + W * 0.80, oy - H * 0.62 - 12, "ignored constraints", cls="dg-note dg-govtext")
    d.text(ox + 12, oy - H * 0.92 - 12, "stable", cls="dg-note")
    return d


def proactive_reactive():
    d = Diagram("proactive-reactive", 880, 300,
                "Proactive strategies keep the window small by design; reactive strategies shrink it once pressure builds, "
                "ordered from the lightest to the heaviest.",
                "Design first, react second. Exam questions that say 'before compaction becomes necessary' want a "
                "proactive strategy; the reactive ladder runs from clearing (lightest) to sub-agents.")
    d.group(20, 14, 400, 266, "Proactive · design time", kind="app")
    d.group(460, 14, 400, 266, "Reactive · window under pressure", kind="model")
    pro = [("Minimal tool set", "only the tools this agent needs"), ("Just-in-time retrieval", "load data via tools when needed"),
           ("Tool result scoping", "filters, LIMIT, fields, summaries"), ("Agent Skills", "rare procedures load on demand")]
    for i, (l, s) in enumerate(pro):
        d.box(f"p{i}", 40, 44 + i * 56, 360, 44, l, [s], kind="tool" if i != 1 else "data")
    rea = [("Tool result clearing", "stub out old raw outputs"), ("Trimming", "sliding window: loses early facts"),
           ("Compaction", "summary + recent items"), ("Offload / sub-agents", "notes, state tables, clean windows")]
    for i, (l, s) in enumerate(rea):
        d.box(f"r{i}", 480, 44 + i * 56, 360, 44, l, [s], kind="model", num=i + 1, accent=(i == 2))
    for i in range(3):
        d.arrow(f"r{i}", f"r{i + 1}", sides="bt")
    return d


# ---------- §2 Instructions ----------

def genie_config():
    d = Diagram("genie-config", 880, 420,
                "Where each kind of knowledge goes in a Genie space: UC metadata, knowledge store, SQL expressions, example "
                "SQL and trusted assets, and general instructions feed Genie; sample questions only help users; benchmarks "
                "measure accuracy.",
                "Each problem has a home. Jargon → general instructions. KPIs → SQL expressions. Values → entity matching. "
                "Verified answers → trusted assets. Sample questions don't teach Genie anything.")
    ins = [("uc", "UC descriptions + PK/FK", "which column? which join?", "data"),
           ("ks", "Synonyms + entity matching", "which value? 'Florida' → FL", "data"),
           ("expr", "SQL expressions", "measures · filters · fields (KPIs)", "tool"),
           ("ex", "Example SQL + trusted assets", "complex / verified questions", "tool"),
           ("gi", "General instructions", "jargon, fiscal calendar, rules", "app")]
    for i, (k, l, s, kind) in enumerate(ins):
        d.box(k, 20, 20 + i * 72, 280, 52, l, [s], kind=kind, accent=(k == "gi"))
    d.box("genie", 380, 150, 170, 90, "Genie space", ["NL → SQL", "(now Genie Agent)"], kind="tool")
    for i, (k, *_r) in enumerate(ins):
        d.arrow(k, "genie", sides="rl", boff=(i - 2) * 0.16)
    d.box("sq", 630, 40, 230, 52, "Sample questions", ["starter prompts for users"], kind="plain")
    d.box("users", 630, 150, 230, 52, "Business users", ["ask in their own words"], kind="app")
    d.box("bm", 630, 260, 230, 60, "Benchmarks", ["expected SQL / answers", "accuracy before/after changes"], kind="eval")
    d.arrow("sq", "users", "shown to users only", sides="bt")
    d.arrow("users", "genie", "question", sides="lr", aoff=-0.1, boff=-0.15)
    d.arrow("genie", "bm", sides="rl", aoff=0.3)
    d.text(20, 404, "Fix order: small clean data → descriptions → SQL expressions → example SQL → text instructions → benchmarks",
           cls="dg-note dg-strong")
    return d


# ---------- §3 Retrieval ----------

def retrieval_modes():
    d = Diagram("retrieval-modes", 880, 330,
                "Pre-inference retrieval fetches top-k chunks once before the model runs; just-in-time retrieval lets the "
                "model call retrieval tools during the task.",
                "Pre-inference: one fast pass, good for stable corpora and self-contained questions. Just-in-time: the "
                "agent decides what to load and when, good for multi-step tasks and live structured data.")
    d.group(20, 12, 840, 110, "Pre-inference · up front", kind="data")
    row = [("q", "Question", "", "app", 120), ("as", "AI Search", "top-k chunks", "data", 150),
           ("pr", "Prompt", "instructions + chunks", "model", 180), ("llm1", "LLM", "one pass", "model", 120)]
    x = 40
    for k, l, s, kind, w in row:
        d.box(k, x, 44, w, 52, l, [s] if s else [], kind=kind)
        x += w + 60
    for a, b in zip(row, row[1:]):
        d.arrow(a[0], b[0])
    d.group(20, 138, 840, 180, "Just-in-time · agentic", kind="tool")
    d.box("q2", 40, 196, 120, 52, "Task", kind="app")
    d.box("llm2", 220, 186, 160, 72, "LLM agent", ["decides what it needs", "step by step"], kind="model")
    tools = [("t1", "AI Search tool", "documents"), ("t2", "Genie / SQL on Delta", "live structured data"),
             ("t3", "UC function", "exact lookups")]
    for i, (k, l, s) in enumerate(tools):
        d.box(k, 560, 170 + i * 46, 280, 38, l, [s], kind="tool" if i else "data")
        d.arrow("llm2", k, sides="rl", aoff=(i - 1) * 0.3)
    d.arrow("q2", "llm2")
    d.text(220, 296, "keeps references in context, loads data when needed", cls="dg-note")
    return d


def rag_uc():
    d = Diagram("rag-uc", 880, 210,
                "A RAG pipeline over a Unity Catalog governed corpus: volume, parse, chunk into a Delta table with change "
                "data feed, Delta Sync AI Search index, retriever tool, and delimited chunks with citations in the agent "
                "context.",
                "Everything upstream of the index is governed by UC. A triggered index only changes when sync runs, so put "
                "sync right after the ingestion task. MLflow's RETRIEVER span shows what entered the context.")
    steps = [("vol", "UC volume", "raw docs", "data"), ("parse", "Parse", "ai_parse_document", "plain"),
             ("chunk", "Chunk table", "Delta · PK · CDF", "data"), ("idx", "AI Search", "Delta Sync index", "data"),
             ("ret", "Retriever", "top-k + rerank", "tool"), ("ctx", "Agent context", "delimited + cited", "model")]
    for i, (k, l, s, kind) in enumerate(steps):
        d.box(k, 16 + i * 146, 40, 130, 56, l, [s], kind=kind, mono=(k == "parse"))
    for a, b in zip(steps, steps[1:]):
        d.arrow(a[0], b[0])
    d.box("job", 210, 140, 300, 44, "Daily job: ingest → index.sync()", kind="app", accent=True)
    d.arrow("job", "idx", "triggered sync", sides="rb", via=[(527, 162)], lpos=(560, 128))
    d.box("ml", 600, 140, 260, 44, "MLflow trace: RETRIEVER span", kind="eval")
    d.arrow("ret", "ml", sides="bt", dashed=True)
    return d


def authoritative():
    d = Diagram("authoritative", 880, 300,
                "Constraining retrieval to authoritative sources: only certified assets are indexed and granted; derived and "
                "deprecated copies never enter the retrieval space.",
                "Govern before retrieval. Certify the source of truth, deprecate copies, index and grant only certified "
                "assets, and keep a metadata filter as defense in depth. Prompting 'prefer official sources' is not "
                "governance.")
    assets = [("a1", "main.policies.travel", "certified ✓ (gold, owned)", "data", True),
              ("a2", "sandbox.tmp.travel_copy", "derived copy, no owner", "gov", False),
              ("a3", "main.policies.travel_2024", "deprecated ⊘", "gov", False)]
    for i, (k, l, s, kind, ok) in enumerate(assets):
        d.box(k, 20, 30 + i * 84, 270, 56, l, [s], kind=kind, mono=True)
    d.box("gate", 360, 96, 200, 92, "Governance gate", ["certification tag", "UC grants (SELECT)", "lineage check"],
          kind="gov", accent=True)
    for i, (k, *_r) in enumerate(assets):
        d.arrow(k, "gate", sides="rl", boff=(i - 1) * 0.3, dashed=(i > 0))
    d.box("idx", 630, 60, 230, 56, "AI Search index", ["built from certified only"], kind="data")
    d.box("agent", 630, 170, 230, 56, "Agent", ["filter: source_tier = 'gold'"], kind="app")
    d.arrow("gate", "idx", "certified", sides="rl", aoff=-0.25, hot=True)
    d.arrow("idx", "agent", "retrieves", sides="bt")
    d.text(425, 236, "derived / deprecated: blocked", cls="dg-note dg-govtext", anchor="middle")
    d.text(20, 288, "SET TAG ON TABLE main.policies.travel `system.certification_status` = `certified`;", cls="dg-sub dg-mono")
    return d


# ---------- §4 Memory ----------

def memory_layers():
    d = Diagram("memory-layers", 880, 380,
                "Agent memory layers: the context window as working memory, a Lakebase checkpointer for the session keyed by "
                "thread id, a Lakebase store for long-term memory namespaced by user, a state table for task progress, and "
                "AI Search for knowledge.",
                "Match the memory to the information need. Same conversation → session checkpoint. Across conversations → "
                "long-term store. Exact progress of a long job → state table. Facts about the world → knowledge, not memory.")
    d.box("agent", 330, 20, 220, 60, "Agent (LangGraph)", ["thread_id + user_id from request"], kind="app")
    d.box("win", 330, 118, 220, 60, "Context window", ["working memory: this call"], kind="model", accent=True)
    d.arrow("agent", "win", "assembles", sides="bt")
    layers = [("sess", 20, "Session memory", ["checkpointer · Lakebase", "key: thread_id"]),
              ("lt", 240, "Long-term memory", ["store · Lakebase · vectors", "ns: (memories, user)"]),
              ("st", 460, "Task state", ["Delta / Lakebase table", "per-item status"]),
              ("kn", 680, "Knowledge", ["AI Search · Genie", "not 'memory'"])]
    for k, x, l, s in layers:
        d.box(k, x, 250, 180, 64, l, s, kind="data")
        d.arrow(k, "win", sides="tb", aoff=0, boff=(x - 350) / 700)
    d.text(110, 340, "resume the same chat", cls="dg-note", anchor="middle")
    d.text(330, 340, "preferences across chats", cls="dg-note", anchor="middle")
    d.text(550, 340, "batch jobs, multi-run tasks", cls="dg-note", anchor="middle")
    d.text(770, 340, "documents, tables", cls="dg-note", anchor="middle")
    d.text(440, 370, "setup(): async saver → await checkpointer.setup(), then compile(checkpointer=…, store=…)", cls="dg-sub dg-mono",
           anchor="middle")
    return d


def memory_router():
    d = Diagram("memory-router", 880, 250,
                "Routing memory queries: fuzzy preference questions go to semantic search, exact ids, dates and counts go to "
                "SQL on Lakebase, and known keys go to a key lookup.",
                "Embeddings are good at meaning and bad at exact ids, dates and counts. Route by the shape of the question.")
    d.box("q", 20, 96, 150, 56, "Memory query", kind="app")
    d.box("r", 220, 96, 140, 56, "Router", ["shape of question"], kind="plain")
    d.arrow("q", "r")
    outs = [("sem", "Semantic search", "AI Search / store.search()", "data", "“what does Ana prefer for reports?”"),
            ("sql", "SQL on Lakebase", "WHERE · ORDER BY · COUNT", "data", "“how many refunds in Q3?” · “last 5 tickets”"),
            ("key", "Key lookup", "store.get(ns, 'language')", "data", "“the language preference”")]
    for i, (k, l, s, kind, ex) in enumerate(outs):
        y = 20 + i * 78
        d.box(k, 420, y, 200, 56, l, [s], kind=kind, mono=False)
        d.arrow("r", k, sides="rl", aoff=(i - 1) * 0.3)
        d.text(636, y + 33, ex, cls="dg-sub")
    return d


def intent_first():
    d = Diagram("intent-first", 880, 230,
                "Retrieving on the raw message returns accurate but mismatched context; resolving intent with the session "
                "first rewrites the query so retrieval returns the right context.",
                "'Accurate but contextually mismatched' means retrieval ran on the raw message. Resolve references, entity "
                "and scope from the session first, then retrieve.")
    d.text(20, 24, "Without intent resolution", cls="dg-label")
    d.box("m1", 20, 36, 200, 50, "“What's the limit?”", kind="app")
    d.box("r1", 300, 36, 160, 50, "Retrieve", kind="data")
    d.box("o1", 540, 36, 320, 50, "credit limit: 5,000 EUR", ["accurate, but the wrong question"], kind="gov")
    d.arrow("m1", "r1"); d.arrow("r1", "o1")
    d.text(20, 132, "Intent first", cls="dg-label")
    d.box("m2", 20, 144, 200, 56, "“What's the limit?”", ["+ session: API, HTTP 429"], kind="app")
    d.box("ir", 250, 144, 190, 56, "Resolve intent", ["rewrite: API rate limit"], kind="model", accent=True)
    d.box("r2", 470, 144, 120, 56, "Retrieve", kind="data")
    d.box("o2", 620, 144, 240, 56, "API rate limit: 100/min", ["right context"], kind="eval")
    d.arrow("m2", "ir"); d.arrow("ir", "r2"); d.arrow("r2", "o2")
    return d


# ---------- §5 Tools ----------

def progressive_disclosure():
    d = Diagram("progressive-disclosure", 880, 320,
                "A raw dump puts all 60 tool schemas in every call; progressive disclosure loads a small catalog, discovers "
                "the right tool by intent, loads only its schema, and returns a scoped result.",
                "Raw dump: every schema, every turn. Progressive disclosure: catalog → discover by intent → one schema → "
                "scoped result. Unused schemas never enter the window.")
    d.group(20, 14, 260, 290, "Raw tool dump", kind="gov")
    for i in range(10):
        for j in range(6):
            d.rect(36 + j * 38, 46 + i * 20, 32, 14, kind="tool")
    d.text(150, 266, "60 full schemas", cls="dg-label", anchor="middle")
    d.text(150, 284, "~8k tokens on every call", cls="dg-note dg-govtext", anchor="middle")
    d.group(310, 14, 550, 290, "Progressive disclosure", kind="tool")
    stages = [("s0", "0 · Catalog", "group names + one-liners", "~300"), ("s1", "1 · Discover by intent", "score vs the user's need", "~150"),
              ("s2", "2 · Load ONE schema", "the best-matching tool", "~140"), ("s3", "3 · Execute, scope result", "filter in code first", "~20")]
    for i, (k, l, s, t) in enumerate(stages):
        d.box(k, 330, 44 + i * 64, 330, 48, l, [s], kind="tool", num=i)
        d.text(684, 44 + i * 64 + 29, f"{t} tokens", cls="dg-note dg-oktext")
        if i:
            d.arrow(stages[i - 1][0], k, sides="bt")
    return d


def tool_clearing():
    d = Diagram("tool-clearing", 880, 250,
                "Tool result clearing: old raw tool outputs that were already digested are replaced by short stubs, while "
                "recent results, write confirmations and results needed later are kept.",
                "Clear what is old, digested and re-fetchable. Keep the latest results, anything pending steps need, and "
                "anything you can't reproduce (ids from a create).")
    items = [("t3", "crm_search", "6.2k", True), ("t7", "orders_search", "9.1k", True), ("t9", "orders_create", "0.2k", False),
             ("t12", "shipping_track", "3.4k", False), ("t18", "list_payments", "5.2k", False)]
    for i, (k, l, size, clear) in enumerate(items):
        x = 20 + i * 172
        d.box(k, x, 40, 152, 60, f"turn {k[1:]}", [f"{l} · {size}"], kind="tool")
        d.box(k + "b", x, 150, 152, 60 if not clear else 40, "stub" if clear else "kept",
              ["see summary, turn 8"] if clear else [["id ORD-9921", "still needed", "latest"][i - 2]],
              kind="plain" if clear else "tool", accent=not clear)
        d.arrow(k, k + "b", "clear" if clear else "keep", sides="bt", hot=clear)
    d.text(20, 236, "Never clear: write confirmations, ids, user-provided facts, results pending steps depend on.", cls="dg-note dg-strong")
    return d


def skills():
    d = Diagram("skills", 880, 230,
                "Agent Skills load progressively: skill names and descriptions are always in the system prompt, the SKILL.md "
                "body loads when relevant, and linked reference files load only when needed.",
                "Baseline cost is only the metadata. A clear, specific description is what makes on-demand loading "
                "reliable.")
    lv = [("l1", "Level 1 · metadata", "name + description, always loaded", "~30 tok / skill", "app"),
          ("l2", "Level 2 · SKILL.md body", "loaded when the skill is relevant", "~1–3k tok", "tool"),
          ("l3", "Level 3 · linked files", "reference.md, scripts: on demand", "only if needed", "tool")]
    for i, (k, l, s, t, kind) in enumerate(lv):
        x = 20 + i * 290
        d.box(k, x, 40, 260, 70, l, [s, t], kind=kind, num=i + 1)
        if i:
            d.arrow(lv[i - 1][0], k)
    d.box("sp", 20, 150, 400, 52, "Keep in the system prompt", ["identity, safety rules, core task, output format"], kind="app")
    d.box("sk", 460, 150, 400, 52, "Move to skills", ["rare, long, self-contained procedures"], kind="tool")
    return d


# ---------- §6 Compaction ----------

def compaction_ladder():
    d = Diagram("compaction-ladder", 880, 250,
                "The compression ladder from the lightest technique to the heaviest: tool result clearing, trimming, "
                "compaction, offloading to notes, and sub-agents, with what each one loses.",
                "Climb only as far as the task needs. Trimming is fine when relevance is recency-local; compaction when early "
                "facts stay relevant; notes or state tables when exact progress matters.")
    rungs = [("Clear tool\nresults", "loses: old raw outputs"), ("Trimming\n(sliding window)", "loses: anything old"),
             ("Compaction\n(LLM summary)", "loses: what it omits"), ("Notes /\nstate table", "loses: nothing written"),
             ("Sub-agents", "loses: their details")]
    for i, (l, s) in enumerate(rungs):
        x, y = 20 + i * 172, 176 - i * 34
        d.box(f"c{i}", x, y, 160, 62, l, [s], kind="model", accent=(i == 2))
    d.text(20, 24, "lighter, cheaper", cls="dg-note")
    d.text(860, 24, "heavier, more powerful", cls="dg-note", anchor="end")
    d.line([(150, 20), (690, 20)], dashed=True)
    return d


def compaction_keep():
    d = Diagram("compaction-keep", 880, 340,
                "Before compaction the window holds instructions, many turns and raw tool outputs; after compaction it holds "
                "instructions, a structured summary of goals, constraints, decisions, progress, ids, failures and facts, and "
                "the last few turns verbatim.",
                "A good summary is small and structured. It keeps the categories that later steps depend on and drops raw "
                "outputs, chatter and superseded plans.")
    d.group(20, 14, 330, 312, "Before · 92% full", kind="gov")
    blocks = [("system prompt", "app", 22), ("turns 1–40", "model", 90), ("raw tool outputs", "tool", 110), ("last 4 turns", "model", 40)]
    y = 44
    for l, kind, h in blocks:
        d.rect(40, y, 290, h, kind=kind)
        d.text(185, y + h / 2 + 4, l, cls="dg-sub dg-strong", anchor="middle")
        y += h + 6
    d.group(520, 14, 340, 312, "After · 18% full", kind="eval")
    d.rect(540, 44, 300, 22, kind="app")
    d.text(690, 59, "system prompt", cls="dg-sub dg-strong", anchor="middle")
    d.box("sum", 540, 74, 300, 186, "Structured summary",
          ["goal + deadline", "constraints · exclusions · preferences", "decisions + one-line reasons", "progress: done / open",
           "ids, paths, ticket numbers (exact)", "failed approaches + why", "key facts with sources"], kind="model", accent=True, top=True)
    d.rect(540, 268, 300, 40, kind="model")
    d.text(690, 292, "last 4 turns verbatim", cls="dg-sub dg-strong", anchor="middle")
    d.arrow((350, 170), (520, 170), "compact", hot=True)
    d.text(435, 196, "drop: raw outputs,", cls="dg-note dg-govtext", anchor="middle")
    d.text(435, 212, "chatter, old plans", cls="dg-note dg-govtext", anchor="middle")
    return d


def compaction_tuning():
    d = Diagram("compaction-tuning", 880, 250,
                "Tuning a compaction prompt: first maximize recall until downstream checks pass, then remove superfluous "
                "content for precision while re-checking that task success holds.",
                "Recall first: a short summary that silently loses a constraint is the expensive failure. Then trim for "
                "precision, re-running the same downstream checks each time.")
    d.box("p", 20, 92, 160, 64, "Compaction prompt", ["vN"], kind="model")
    d.box("run", 230, 92, 180, 64, "Run on long traces", ["compact, then continue"], kind="app")
    d.box("ev", 460, 92, 180, 64, "Downstream checks", ["MLflow eval: task", "success + summary size"], kind="eval")
    d.box("rec", 690, 44, 170, 56, "1 · Recall gaps?", ["add the missing category"], kind="gov")
    d.box("pre", 690, 148, 170, 56, "2 · Then precision", ["remove what's never used"], kind="tool")
    d.arrow("p", "run"); d.arrow("run", "ev")
    d.arrow("ev", "rec", sides="rl", aoff=-0.25); d.arrow("ev", "pre", sides="rl", aoff=0.25)
    d.arrow("rec", "p", "next version", sides="tt", via=[(775, 18), (100, 18)], dashed=True, lpos=(440, 13))
    d.arrow("pre", "p", sides="bb", via=[(775, 222), (100, 222)], dashed=True)
    d.text(440, 242, "stop trimming when removing more starts to hurt task success", cls="dg-note", anchor="middle")
    return d


# ---------- §7 Multi-agent ----------

def dispatch():
    d = Diagram("dispatch", 880, 360,
                "A coordinator dispatching sub-agents: with task messages only, each sub-agent makes its own implicit "
                "decisions and outputs conflict; with a compressed trace summary, they share decisions; sub-agents return "
                "condensed results plus handles.",
                "Share decisions, not whole transcripts: a compressed trace summary at dispatch, and condensed structured "
                "results (plus a handle to the full data) on the way back.")
    d.box("coord", 330, 16, 220, 64, "Coordinator", ["30-turn trace with decisions"], kind="app")
    d.box("sum", 330, 104, 220, 44, "Trace summary (~100 tok)", kind="model", accent=True)
    d.arrow("coord", "sum", "compress", sides="bt")
    subs = [("s1", 20, "EMEA"), ("s2", 330, "AMER"), ("s3", 640, "APAC")]
    for k, x, r in subs:
        d.box(k, x, 190, 220, 56, f"Sub-agent: {r}", ["task + shared summary"], kind="tool")
        d.arrow("sum", k, sides="bt", hot=True)
        d.box(k + "o", x, 290, 220, 52, "condensed result", ["metrics + handle to table"], kind="data")
        d.arrow(k, k + "o", sides="bt")
    d.text(20, 120, "✗ task line only →", cls="dg-note dg-govtext")
    d.text(20, 136, "30 / 90 / 365-day 'active'", cls="dg-note dg-govtext")
    d.text(860, 120, "✗ full raw trace →", cls="dg-note dg-govtext", anchor="end")
    d.text(860, 136, "every window explodes", cls="dg-note dg-govtext", anchor="end")
    return d


def boundaries():
    d = Diagram("boundaries", 880, 280,
                "Agent boundary placement: too fine creates many lossy handoffs through tightly coupled steps, too coarse "
                "makes one agent's context grow without control, and boundaries along coupling give small windows and few "
                "handoffs.",
                "Draw boundaries where the interface is narrow. Many summaries between agents mean too fine; one huge "
                "window means too coarse.")
    rows = [("Too fine", "handoff compression overhead", 12), ("Too coarse", "unmanageable window growth", 1),
            ("Along coupling", "few handoffs, small windows", 3)]
    for r, (label, note, n) in enumerate(rows):
        y = 24 + r * 86
        d.text(20, y + 24, label, cls="dg-label")
        d.text(20, y + 40, note, cls="dg-note dg-govtext" if r < 2 else "dg-note dg-oktext")
        x0, W = 250, 610
        gap = 10 if n > 1 else 0
        w = (W - gap * (n - 1)) / n
        for i in range(n):
            d.box(f"b{r}{i}", x0 + i * (w + gap), y, w, 50, "" if n == 12 else (f"steps {4 * i + 1}–{4 * i + 4}" if n == 3 else "steps 1–12"),
                  kind="tool" if n != 1 else "gov", accent=(n == 3))
            if i:
                d.arrow(f"b{r}{i - 1}", f"b{r}{i}")
    return d


def long_horizon():
    d = Diagram("long-horizon", 880, 330,
                "Choosing a long-horizon strategy by dependency structure: exact per-item state needs notes or a state table, "
                "independent parts suit sub-agents, sequential interdependent work suits one agent with compaction, and "
                "interruptions need checkpoints.",
                "Name the task's dependency structure first; the strategy follows. The exam's justification is the one "
                "characteristic the original strategy can't handle.")
    qs = [("q1", "Exact per-item progress across runs?", "a1", "Notes / state table", "Delta or Lakebase, resumable", "data"),
          ("q2", "Independent, parallel parts?", "a2", "Sub-agents", "condensed returns to the lead", "tool"),
          ("q3", "Sequential, decisions depend on earlier ones?", "a3", "Single agent + compaction", "keep decisions in one thread", "model"),
          ("q4", "Must survive interruptions / human pauses?", "a4", "Checkpoint and resume", "LangGraph checkpointer on Lakebase", "data")]
    for i, (qk, q, ak, a, s, kind) in enumerate(qs):
        y = 20 + i * 76
        d.box(qk, 20, y, 400, 48, q, kind="plain")
        d.box(ak, 500, y, 360, 48, a, [s], kind=kind)
        d.arrow(qk, ak, "yes")
        if i:
            d.arrow(qs[i - 1][0], qk, "no", lpos=(232, y - 10), lanchor="start")
    d.text(20, 324, "Mismatch example: parallel sub-agents on tightly sequential steps → conflicting outputs → single agent.",
           cls="dg-note dg-strong")
    return d


DIAGRAMS = {f().id: f for f in [context_anatomy, failure_modes, degradation, proactive_reactive, genie_config, retrieval_modes,
                                 rag_uc, authoritative, memory_layers, memory_router, intent_first, progressive_disclosure,
                                 tool_clearing, skills, compaction_ladder, compaction_keep, compaction_tuning, dispatch,
                                 boundaries, long_horizon]}


def render(did):
    return DIAGRAMS[did]().figure()


if __name__ == "__main__":
    for k in DIAGRAMS:
        render(k)
    print("\n".join(warnings) or "all labels fit")
