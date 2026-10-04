#!/usr/bin/env python3
"""One-shot HTML docs generator matching super/docs chrome. Run from repo root."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs"
GH = "https://github.com/aquinlabs/mom"
GH_ICON = (
    '<svg class="gh-icon" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">'
    '<path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 '
    "0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 "
    "1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15"
    "-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 "
    "1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 "
    '2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>'
)

NAV = [
    ("Getting started", ""),
    ("Install", "install/"),
    ("CLI", "cli/"),
    ("SDK", "sdk/"),
    ("Graphs", "graphs/"),
    ("Adapters", "adapters/"),
    ("Limits", "caveats/"),
]


def shell_block(lines: list[str], label: str = "shell") -> str:
    body = []
    for line in lines:
        body.append(
            f'<span class="line"><span class="prompt">$</span><span>{_esc(line)}</span></span>'
        )
    inner = "\n".join(body)
    return f"""<div class="codeblock" data-shell="1">
  <div class="codeblock-bar"><span>{label}</span><button type="button" class="copy-btn">Copy</button></div>
  <pre><code>{inner}</code></pre>
</div>"""


def py_block(code: str, label: str = "python") -> str:
    body = []
    for line in code.split("\n"):
        body.append(f'<span class="line"><span>{_esc(line)}</span></span>')
    inner = "\n".join(body)
    return f"""<div class="codeblock" data-shell="0">
  <div class="codeblock-bar"><span>{label}</span><button type="button" class="copy-btn">Copy</button></div>
  <pre><code>{inner}</code></pre>
</div>"""


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def page(slug: str, title: str, desc: str, body: str, h1: str | None = None, hero: bool = False) -> str:
    nested = slug != ""
    asset = "../../assets" if nested else "../assets"
    home = "../" if nested else "./"
    prefix = "../" if nested else ""
    nav = []
    for label, href in NAV:
        active = " active" if href == slug or (slug == "" and href == "") else ""
        if href == "":
            link = "../" if nested else "./"
        else:
            link = f"{prefix}{href}"
        nav.append(f'<a class="nav-link{active}" href="{link}">{label}</a>')
    h1_cls = ' class="hero"' if hero else ""
    heading = h1 or title
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(title)} · MoM Docs</title>
  <meta name="description" content="{_esc(desc)}" />
  <link rel="icon" href="{asset}/favicon.ico" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Host+Grotesk:wght@400;500;600;700&amp;family=IBM+Plex+Mono:wght@400;500;600&amp;display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="{asset}/docs.css" />
</head>
<body>
<div class="docs-frame">
    <aside class="docs-sidebar" aria-label="Documentation">
      <a class="brand sidebar-brand" href="{home}" title="Aquin Labs">
        <img src="{asset}/mainlogo2.png" alt="" width="22" height="22" />
        <span>Aquin<span class="brand-gap">Labs</span></span>
      </a>
      <nav>
        {chr(10).join(nav)}
      </nav>
      <div class="sidebar-footer">
        <a class="sidebar-github" href="{GH}" rel="noopener">
          {GH_ICON}
          <span>GitHub</span>
        </a>
      </div>
    </aside>
    <main class="docs-main"><article>
  <h1{h1_cls}>{_esc(heading)}</h1>
{body}
    </article></main>
  </div>
  <script src="{asset}/docs.js"></script>
</body>
</html>
"""


def write(rel: str, html: str) -> None:
    path = DOC / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    print("wrote", path.relative_to(ROOT))


def main() -> None:
    write(
        "index.html",
        """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="refresh" content="0; url=documentation/" />
  <link rel="canonical" href="documentation/" />
  <title>MoM Docs</title>
  <script>location.replace("documentation/");</script>
</head>
<body>
  <p><a href="documentation/">Continue to documentation</a></p>
</body>
</html>
""",
    )

    write(
        "documentation/index.html",
        page(
            "",
            "Getting started",
            "MoM SDK: register models, wire graphs, one run() that feels like a single model.",
            hero=True,
            body=f"""
  <p class="lead"><strong>mom</strong> is a Python SDK for composing models in-process. You implement <code class="chip">run(input, state)</code>, register an id, wire a <code class="chip">Graph</code>, and call <code class="chip">mom.run</code> (or <code class="chip">MoM().chat</code>). Shared state, speculative routing, timing metrics.</p>

  <h2>How the pieces fit</h2>
  <div class="table-wrap mb">
    <table class="plain">
      <thead><tr><th>Name</th><th>What it is</th></tr></thead>
      <tbody>
        <tr><td class="mono">Model</td><td>Protocol: <code class="chip">run(input, state, cancel=None)</code>. Any kind.</td></tr>
        <tr><td class="mono">ModelDirectory</td><td>id → factory. Graphs only see ids.</td></tr>
        <tr><td class="mono">Graph</td><td><code class="chip">add</code> / <code class="chip">link</code> / <code class="chip">speculate</code>.</td></tr>
        <tr><td class="mono">StateStore</td><td>Shared memory for hops and turns.</td></tr>
        <tr><td class="mono">run</td><td>Execute a graph. Returns <code class="chip">RunResult</code>.</td></tr>
        <tr><td class="mono">Session</td><td>Multi-turn over one store.</td></tr>
        <tr><td class="mono">MoM</td><td>App handle: directory + registry + <code class="chip">chat</code>.</td></tr>
      </tbody>
    </table>
  </div>

  <h2>Minimal SDK loop</h2>
  {py_block('''from mom import Graph, ModelDirectory, StateStore, run

directory = ModelDirectory()

class Echo:
    def run(self, input, state, cancel=None):
        return {"text": str(input), "model": "echo"}

directory.register("echo", Echo, tags={"generator"})
result = run(Graph().add("g", "echo"), "hello", directory, state=StateStore())
print(result.output, result.metrics["total_ms"])''')}

  <h2>App handle</h2>
  {py_block('''from mom import MoM, Graph

app = MoM()  # local adapters from env

@app.model("billing.lookup", tags={"tool"})
class BillingLookup:
    def run(self, input, state, cancel=None):
        return {"text": "invoice #9 is unpaid", "model": "billing.lookup"}

app.add_graph(
    "support",
    Graph()
    .add("billing", "billing.lookup")
    .add("router", "prod.router")
    .add("gen", "prod.chat.fast")
    .link("billing", "router")
    .speculate("router", "gen"),
    requires={"billing.lookup", "prod.router", "prod.chat.fast", "prod.chat.strong"},
)
print(app.chat("why was I charged?", graph="support").text)''')}

  <h2>Next</h2>
  <ul class="next-list">
    <li><a href="install/">Install</a> — package + native extension</li>
    <li><a href="cli/">CLI</a> — mom doctor / models / graphs / run / chat / serve</li>
    <li><a href="sdk/">SDK</a> — run, Session, MoM, metrics</li>
    <li><a href="graphs/">Graphs</a> — add, link, speculate, registry</li>
    <li><a href="adapters/">Adapters</a> — the Model contract</li>
    <li><a href="caveats/">Limits</a> — what speculate can hide</li>
  </ul>
""",
        ),
    )

    write(
        "documentation/install/index.html",
        page(
            "install/",
            "Install",
            "Install the mom Python SDK from the repo.",
            body=f"""
  <p class="lead">The SDK is the <code class="chip">mom</code> package. Native graph runner is optional but built by default with maturin. No PyPI release yet.</p>
  <div class="prereq"><span class="prereq-label">Prerequisite</span>Python ≥ 3.10 · Rust (rustup) for <code class="chip">mom._native</code></div>

  <section class="tool" id="venv">
    <h3 class="tool-cmd">venv + maturin</h3>
    <p class="tool-desc">From the repo root. Puts <code class="chip">import mom</code> and the <code class="chip">mom</code> CLI on your environment.</p>
    {shell_block([
        "python3 -m venv .venv && source .venv/bin/activate",
        "pip install -r requirements.txt",
        "maturin develop",
        "mom version",
    ])}
  </section>

  <section class="tool" id="local">
    <h3 class="tool-cmd">Local model extras</h3>
    <p class="tool-desc">Only if you use the bundled HF / torchvision adapters via <code class="chip">MoM()</code> / <code class="chip">build_directory()</code>.</p>
    {shell_block([
        "pip install -r requirements-local.txt",
        "cp -n .env.example .env",
    ])}
  </section>

  <section class="tool" id="cli">
    <h3 class="tool-cmd">mom CLI</h3>
    <p class="tool-desc">Same SDK, no Python file. See <a href="../cli/">CLI</a>. <code class="chip">mom-ping</code> and <code class="chip">mom-serve</code> still work as aliases.</p>
    {shell_block(["mom doctor", "mom serve"])}
  </section>
""",
        ),
    )

    write(
        "documentation/cli/index.html",
        page(
            "cli/",
            "CLI",
            "mom doctor, models, graphs, plan, run, chat, serve.",
            body=f"""
  <p class="lead">After <code class="chip">maturin develop</code>, the <code class="chip">mom</code> command is the SDK in a terminal. It uses the same directory, registry, and <code class="chip">MoM()</code> handle as Python.</p>

  <section class="tool" id="inspect">
    <h3 class="tool-cmd">Inspect</h3>
    {shell_block([
        "mom version",
        "mom doctor",
        "mom models",
        "mom graphs",
        "mom plan speculate_chat",
    ])}
    <p class="tool-desc"><code class="chip">doctor</code> exits 1 if the process is not ready. Add <code class="chip">--json</code> on any command for machine-readable output. <code class="chip">mom-ping</code> is <code class="chip">mom version</code>.</p>
  </section>

  <section class="tool" id="run">
    <h3 class="tool-cmd">Run and chat</h3>
    {shell_block([
        'mom run "hello" --graph speculate_chat',
        "mom chat --graph speculate_chat",
        "mom run hello --graph-json graph.json --json",
    ])}
    <p class="tool-desc">Text goes to stdout; a metrics line (model, total_ms, spec) goes to stderr. <code class="chip">chat</code> without a message is a REPL (<code class="chip">/quit</code> to leave).</p>
  </section>

  <section class="tool" id="serve">
    <h3 class="tool-cmd">Serve</h3>
    {shell_block(["mom serve", "mom serve --host 127.0.0.1 --port 8080"])}
    <p class="tool-desc"><code class="chip">/v1/run</code>, <code class="chip">/v1/chat</code>, <code class="chip">/health</code>, <code class="chip">/ready</code>. Alias: <code class="chip">mom-serve</code>.</p>
  </section>
""",
        ),
    )

    write(
        "documentation/sdk/index.html",
        page(
            "sdk/",
            "SDK",
            "Python API: Graph, ModelDirectory, run, Session, MoM, RunResult.",
            body=f"""
  <p class="lead">Import from <code class="chip">mom</code>. Stable names are also listed on <code class="chip">mom.api.STABLE_API</code>.</p>

  <section class="tool" id="directory">
    <h3 class="tool-cmd">ModelDirectory</h3>
    <p class="tool-desc">Register a factory under a string id. Tags and modality are metadata; the hot path only calls <code class="chip">run</code>.</p>
    {py_block('''from mom import ModelDirectory

directory = ModelDirectory()
directory.register("echo", Echo, tags={"generator"}, modality="text")''')}
  </section>

  <section class="tool" id="run">
    <h3 class="tool-cmd">run / RunResult</h3>
    <p class="tool-desc"><code class="chip">run(graph, input, directory, state=...)</code> returns <code class="chip">output</code>, <code class="chip">metrics</code>, and <code class="chip">state</code>.</p>
    {py_block('''from mom import Graph, StateStore, run

result = run(Graph().add("g", "echo"), "hello", directory, state=StateStore())
result.output
result.metrics["total_ms"]
result.metrics["orchestration_overhead_ms"]
result.metrics.get("spec")  # hit / miss when the graph speculates''')}
  </section>

  <section class="tool" id="session">
    <h3 class="tool-cmd">Session</h3>
    <p class="tool-desc">Multi-turn. History is stored on the <code class="chip">StateStore</code>, not passed as hop messages.</p>
    {py_block('''from mom import Session
s = Session(directory, graph)
s.say("hi")
s.say("what did I just say?")''')}
  </section>

  <section class="tool" id="mom">
    <h3 class="tool-cmd">MoM</h3>
    <p class="tool-desc">Product handle: loads a directory + graph registry, keeps a default session.</p>
    {py_block('''from mom import MoM

app = MoM()
reply = app.chat("hello")
print(reply.text, reply.model, reply.total_ms)

app.register("my.tool", MyTool, tags={"tool"})
app.add_graph("named", graph, requires={"my.tool"})
app.run("…", graph="named")''')}
  </section>

  <section class="tool" id="cancel-limits">
    <h3 class="tool-cmd">CancelToken · Limiter</h3>
    <p class="tool-desc">Speculative losers get a cancel token. <code class="chip">ConcurrencyLimits</code> cap in-flight runs and model workers.</p>
  </section>
""",
        ),
    )

    write(
        "documentation/graphs/index.html",
        page(
            "graphs/",
            "Graphs",
            "Graph.add, link, speculate. Registry of named graphs.",
            body=f"""
  <p class="lead">A graph is data: nodes name directory ids, edges are <code class="chip">depend</code> or <code class="chip">speculate</code>. The scheduler plans and runs it.</p>

  <section class="tool" id="build">
    <h3 class="tool-cmd">Graph.add · link · speculate</h3>
    <p class="tool-desc"><code class="chip">link(a, b)</code> means b waits on a. <code class="chip">speculate(router, prior)</code> starts <code class="chip">prior</code> at the same time as the router. On a route hit, wall ≈ max(router, prior). On a miss, the prior is cancelled and the routed model runs.</p>
    {py_block('''from mom import Graph

g = (
    Graph()
    .add("router", "prod.router")
    .add("gen", "prod.chat.fast")
    .speculate("router", "gen")
)

pipe = (
    Graph()
    .add("vision", "prod.vision.caption")
    .add("router", "prod.router")
    .add("gen", "prod.chat.fast")
    .link("vision", "router")
    .speculate("router", "gen")
)''')}
  </section>

  <section class="tool" id="registry">
    <h3 class="tool-cmd">GraphRegistry</h3>
    <p class="tool-desc">Name a graph, declare required ids, run it with <code class="chip">run_named</code>. <code class="chip">build_registry()</code> ships a few production names over <code class="chip">prod.*</code> ids if those adapters are loaded.</p>
    {py_block('''from mom import run_named
from mom.runtime import build_directory, build_registry

d = build_directory()
reg = build_registry(d)
run_named("speculate_chat", "hello", d, reg)''')}
  </section>

  <section class="tool" id="select">
    <h3 class="tool-cmd">select_graph</h3>
    <p class="tool-desc">Optional helper: pick a registered graph from the prompt and what the directory actually has. It does not invent new topology.</p>
  </section>
""",
        ),
    )

    write(
        "documentation/adapters/index.html",
        page(
            "adapters/",
            "Adapters",
            "The Model contract: run(input, state). Register by id.",
            body=f"""
  <p class="lead">The SDK does not care what the model is. Chat, vision, embeddings, tools — same method.</p>

  <section class="tool" id="contract">
    <h3 class="tool-cmd">Model.run</h3>
    {py_block('''from mom import ModelDirectory, CancelToken, StateStore

class MyModel:
    def run(self, input, state, cancel=None):
        if cancel is not None:
            cancel.check()
        state.set("my.key", "ok")
        return {"text": "…", "model": "vendor.mine"}

directory = ModelDirectory()
directory.register(
    "vendor.mine",
    lambda: MyModel(),
    tags={"generator"},
    modality="text",
)''')}
    <p class="tool-desc">Common chat/tool shape is a dict with <code class="chip">text</code> and <code class="chip">model</code>. Anything JSON-friendly is allowed. Honor <code class="chip">cancel</code> if you can stop mid-flight.</p>
  </section>

  <section class="tool" id="bundled">
    <h3 class="tool-cmd">Bundled adapters</h3>
    <p class="tool-desc"><code class="chip">build_directory()</code> registers local HF chat/embed/router and optional vision. You do not have to use them — register your own ids instead.</p>
    <div class="table-wrap mb">
      <table class="plain">
        <thead><tr><th>Id</th><th>Adapter</th></tr></thead>
        <tbody>
          <tr><td class="mono">prod.chat.fast / strong</td><td>Local causal LM</td></tr>
          <tr><td class="mono">prod.router</td><td>Heuristic router</td></tr>
          <tr><td class="mono">prod.embed</td><td>Local embeddings</td></tr>
          <tr><td class="mono">prod.vision.caption</td><td>BLIP caption</td></tr>
          <tr><td class="mono">prod.vision.torch</td><td>torchvision classifier</td></tr>
        </tbody>
      </table>
    </div>
  </section>
""",
        ),
    )

    write(
        "documentation/caveats/index.html",
        page(
            "caveats/",
            "Limits",
            "SDK non-guarantees: speculate miss, serial graphs, colocated v1.",
            body="""
  <p class="lead">The SDK will run any graph you give it. Latency hiding is a property of the shape, not a flag you can set on serial work.</p>

  <h2>Speculate</h2>
  <div class="table-wrap mb">
    <table class="plain">
      <thead><tr><th>Outcome</th><th>SDK behavior</th></tr></thead>
      <tbody>
        <tr><td>hit</td><td>Router and prior overlap. Wall ≈ max of the two. Metrics <code class="chip">spec=hit</code>.</td></tr>
        <tr><td>miss</td><td>Prior cancelled (best-effort). Routed model runs. Visible extra wall. <code class="chip">spec=miss</code>.</td></tr>
      </tbody>
    </table>
  </div>

  <h2>Not hidden</h2>
  <ul class="lead-list">
    <li><code class="chip">link</code> pipelines — each hop adds wall.</li>
    <li>Fan-out then reconcile — siblings overlap; the join does not.</li>
    <li>Cross-host shared state — v1 is colocated.</li>
    <li>Bit-identical outputs across model versions.</li>
  </ul>
""",
        ),
    )

    write(
        "README.md",
        """# MoM docs

SDK documentation (same chrome as other Aquin Labs docs).

```
docs/
  documentation/   # Getting started, Install, CLI, SDK, Graphs, Adapters, Limits
  assets/
  index.html       # → documentation/
```

Regenerate HTML: `python docs/_gen.py`
""",
    )


if __name__ == "__main__":
    main()
