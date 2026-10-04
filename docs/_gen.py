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
    ("SDK", "sdk/"),
    ("Graphs", "graphs/"),
    ("Adapters", "adapters/"),
    ("Benches", "benches/"),
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
            "MoM is a composition runtime: plug in any models, wire graphs, one call surface.",
            hero=True,
            body=f"""
  <p class="lead"><strong>MoM</strong> is a colocated composition runtime. You register models (chat, vision, tools, embeddings), wire them as graphs, and call one <code class="chip">run</code> / <code class="chip">chat</code> that feels like a single model — shared state, speculative routing, measured overhead.</p>
  <p class="lead">It is not a chatbot toy. Stubs exist only for latency fixtures. Production default is local Hugging Face / path weights.</p>

  <h2>How the pieces fit</h2>
  <div class="table-wrap mb">
    <table class="plain">
      <thead><tr><th>Name</th><th>What it is</th></tr></thead>
      <tbody>
        <tr><td class="mono">Model</td><td><code class="chip">run(input, state) → output</code>. Any kind. No modality hierarchy.</td></tr>
        <tr><td class="mono">ModelDirectory</td><td>id → factory + tags. Graphs only see ids.</td></tr>
        <tr><td class="mono">Graph</td><td>Nodes are directory ids. Edges are depend or speculate.</td></tr>
        <tr><td class="mono">StateStore</td><td>Shared in-process memory across hops and turns.</td></tr>
        <tr><td class="mono">speculate</td><td>Start the likely model with the router. Hit hides router cost. Miss is correct, not hidden.</td></tr>
        <tr><td class="mono">MoM()</td><td>Product handle: env → local adapters, registry, <code class="chip">chat</code> / HTTP.</td></tr>
      </tbody>
    </table>
  </div>

  <h2>SDK (few lines)</h2>
  {shell_block(["pip install -r requirements-local.txt", "cp -n .env.example .env", "maturin develop"])}
  {py_block('''from mom import MoM, Graph

app = MoM()

print(app.chat("What is 2+2? Reply with only the number.").text)''')}
  <p class="lead">That uses <code class="chip">speculate_chat</code>: heuristic router in parallel with the small chat model; hard prompts fall through to the bigger one.</p>

  <h2>Product graph</h2>
  {py_block('''from mom import MoM, Graph

app = MoM()

@app.model("billing.lookup", tags={"tool"})
class BillingLookup:
    def run(self, input, state, cancel=None):
        return {"text": "invoice #9 is unpaid ($42)", "model": "billing.lookup"}

app.add_graph(
    "support",
    Graph()
    .add("billing", "billing.lookup")
    .add("router", "prod.router")
    .add("gen", "prod.chat.fast")
    .link("billing", "router")
    .speculate("router", "gen"),
    requires={"billing.lookup", "prod.router", "prod.chat.fast", "prod.chat.strong"},
    latency_hideable=True,
)
print(app.chat("why was I charged?", graph="support").text)''')}

  <h2>Next</h2>
  <ul class="next-list">
    <li><a href="install/">Install</a> — venv, Rust, local weights</li>
    <li><a href="sdk/">SDK</a> — run, Session, MoM()</li>
    <li><a href="graphs/">Graphs</a> — chat, vision, speculate</li>
    <li><a href="benches/">Benches</a> — proof, cost, vision, TUIs</li>
    <li><a href="caveats/">Limits</a> — what MoM does and does not hide</li>
  </ul>
""",
        ),
    )

    write(
        "documentation/install/index.html",
        page(
            "install/",
            "Install",
            "Install MoM from the repo: Python, Rust, maturin, local HF weights.",
            body=f"""
  <p class="lead">Install from this repo. No PyPI package yet. Local models need torch + transformers.</p>
  <div class="prereq"><span class="prereq-label">Prerequisite</span>Python ≥ 3.10 · Rust via rustup · Hugging Face weights or Hub access</div>

  <section class="tool" id="venv">
    <h3 class="tool-cmd">venv + build</h3>
    <p class="tool-desc">From the repo root. <code class="chip">maturin develop</code> builds the Rust hot path into <code class="chip">mom._native</code>.</p>
    {shell_block([
        "git clone https://github.com/aquinlabs/mom.git && cd mom",
        "python3 -m venv .venv && source .venv/bin/activate",
        "pip install -r requirements.txt -r requirements-dev.txt -r requirements-local.txt",
        "maturin develop",
        "mom-ping",
        "cp -n .env.example .env",
    ])}
  </section>

  <section class="tool" id="env">
    <h3 class="tool-cmd">Weights</h3>
    <p class="tool-desc">Hub ids download under <code class="chip">MOM_WEIGHTS_DIR/hub/…</code>. Paths work too. Default chat pair is SmolLM2 135M / 360M.</p>
    {shell_block([
        "export MOM_BACKEND=local",
        "export MOM_CHAT_FAST=HuggingFaceTB/SmolLM2-135M-Instruct",
        "export MOM_CHAT_STRONG=HuggingFaceTB/SmolLM2-360M-Instruct",
        "export MOM_VISION_CAPTION=Salesforce/blip-image-captioning-base",
        "export MOM_VISION_TORCH=resnet18",
    ], label="env")}
  </section>

  <section class="tool" id="check">
    <h3 class="tool-cmd">Check</h3>
    {shell_block([
        "pytest -q",
        "python scripts/helpers/examples/hello_mom.py",
    ])}
  </section>
""",
        ),
    )

    write(
        "documentation/sdk/index.html",
        page(
            "sdk/",
            "SDK",
            "Python surface: Graph, ModelDirectory, run, Session, MoM().",
            body=f"""
  <p class="lead">Prefer <code class="chip">from mom import Graph, ModelDirectory, Session, run</code> and <code class="chip">MoM()</code> for products.</p>

  <section class="tool" id="run">
    <h3 class="tool-cmd">mom.run</h3>
    <p class="tool-desc">Execute one graph against a directory. Returns output + timing metrics + the same StateStore.</p>
    {py_block('''from mom import Graph, ModelDirectory, StateStore, run

directory = ModelDirectory()

class Echo:
    def run(self, input, state, cancel=None):
        return {"text": str(input), "model": "echo"}

directory.register("echo", Echo, tags={"generator"})
result = run(Graph().add("g", "echo"), "hello", directory, state=StateStore())
print(result.output, result.metrics["total_ms"])''')}
  </section>

  <section class="tool" id="mom">
    <h3 class="tool-cmd">MoM()</h3>
    <p class="tool-desc">Loads production adapters from env (<code class="chip">build_directory</code>), registers builtin graphs, exposes <code class="chip">chat</code> / <code class="chip">run</code> / HTTP helpers.</p>
    {py_block('''from mom import MoM
app = MoM()
reply = app.chat("Say hi in one word.")
print(reply.text, reply.model, reply.total_ms)''')}
  </section>

  <section class="tool" id="session">
    <h3 class="tool-cmd">Session</h3>
    <p class="tool-desc">Multi-turn over one store. History lives in state, not serialized hop messages.</p>
  </section>

  <section class="tool" id="metrics">
    <h3 class="tool-cmd">Metrics on every run</h3>
    <p class="tool-desc"><code class="chip">total_ms</code>, <code class="chip">orchestration_overhead_ms</code>, per-node ms, <code class="chip">spec</code> hit/miss. Overhead should stay tiny next to model time.</p>
  </section>
""",
        ),
    )

    write(
        "documentation/graphs/index.html",
        page(
            "graphs/",
            "Graphs",
            "Production graph names: speculate chat, vision caption, torchvision.",
            body=f"""
  <p class="lead">Graphs are data. Nodes are directory ids. <code class="chip">link</code> is serial. <code class="chip">speculate</code> overlaps router with the likely generator.</p>

  <div class="table-wrap mb">
    <table class="plain">
      <thead><tr><th>Name</th><th>Shape</th></tr></thead>
      <tbody>
        <tr><td class="mono">speculate_chat</td><td>router ∥ small chat; miss → strong</td></tr>
        <tr><td class="mono">direct_fast / direct_strong</td><td>one chat model</td></tr>
        <tr><td class="mono">caption_chat</td><td>BLIP caption → speculate chat</td></tr>
        <tr><td class="mono">caption_strong</td><td>BLIP → always strong (baseline)</td></tr>
        <tr><td class="mono">torch_chat</td><td>torchvision ResNet → speculate chat</td></tr>
        <tr><td class="mono">vision_stack</td><td>ResNet → BLIP → speculate chat</td></tr>
        <tr><td class="mono">direct_caption / direct_torch</td><td>vision hop only</td></tr>
      </tbody>
    </table>
  </div>

  <section class="tool" id="vision-in">
    <h3 class="tool-cmd">Vision input</h3>
    <p class="tool-desc">Real image files. Pass a dict; hops stash <code class="chip">image_path</code> / <code class="chip">caption</code> on the store.</p>
    {py_block('''from mom import run, StateStore
from mom.runtime import build_directory, build_registry

d = build_directory()
g = build_registry(d).get("caption_chat").graph
out = run(g, {
    "image": "weights/eval_images/solid_red.png",
    "text": "What color is this? One word.",
}, d, state=StateStore())
print(out.output)''')}
  </section>

  <section class="tool" id="wire">
    <h3 class="tool-cmd">Wire your own</h3>
    {py_block('''from mom import Graph
Graph().add("caption", "prod.vision.caption").add("router", "prod.router").add("gen", "prod.chat.fast").link("caption", "router").speculate("router", "gen")''')}
  </section>
""",
        ),
    )

    write(
        "documentation/adapters/index.html",
        page(
            "adapters/",
            "Adapters",
            "One run() contract. Register by id. Local HF, torchvision, optional HTTP.",
            body=f"""
  <p class="lead">No subclass required. Implement <code class="chip">run</code>, register an id, point a graph at it.</p>
  {py_block('''class MyModel:
    def run(self, input, state, cancel=None):
        if cancel is not None:
            cancel.check()
        state.set("my.key", "ok")
        return {"text": "...", "model": "vendor.mine"}

directory.register("vendor.mine", lambda: MyModel(), tags={"generator"}, modality="text")''')}

  <h2>Shipped local adapters</h2>
  <div class="table-wrap mb">
    <table class="plain">
      <thead><tr><th>Id</th><th>What</th></tr></thead>
      <tbody>
        <tr><td class="mono">prod.chat.fast / strong</td><td>Causal LM from Hub or path</td></tr>
        <tr><td class="mono">prod.router</td><td>Heuristic (optional tiny LM)</td></tr>
        <tr><td class="mono">prod.embed</td><td>Local sentence embeddings</td></tr>
        <tr><td class="mono">prod.vision.caption</td><td>BLIP captioner</td></tr>
        <tr><td class="mono">prod.vision.torch</td><td>torchvision ResNet18</td></tr>
      </tbody>
    </table>
  </div>
  <p class="lead"><code class="chip">src/models/stub_*</code> is fixtures. Speech/ASR in that tree is fake. Real speech = you register Whisper (or similar) the same way.</p>

  <section class="tool" id="rules">
    <h3 class="tool-cmd">Rules</h3>
    <p class="tool-desc">New capability = new adapter + register + graph id. Shared state by key. Honor cancel on speculative losers. Common chat shape is <code class="chip">{{text, model}}</code>.</p>
  </section>
""",
        ),
    )

    write(
        "documentation/benches/index.html",
        page(
            "benches/",
            "Benches",
            "Proof, cost, vision, live TUIs. Real weights only.",
            body=f"""
  <p class="lead">These are the numbers that matter. Do not use the old VLM ImageNet bakeoff as a grade.</p>

  <section class="tool" id="proof">
    <h3 class="tool-cmd">Text proof</h3>
    <p class="tool-desc">MoM vs always-small vs always-big on labeled easy/hard prompts. Must beat big on easy speed and mix wall, beat small on hard accuracy.</p>
    {shell_block(["python scripts/helpers/bench/mom_proof.py --rounds 2 --json results/mom_proof.json"])}
  </section>

  <section class="tool" id="cost">
    <h3 class="tool-cmd">Cost</h3>
    <p class="tool-desc">Work = tokens × model size (135M vs 360M). Not dollars. MoM should come in under always-big on an easy-heavy mix.</p>
    {shell_block(["python scripts/helpers/bench/mom_cost.py --rounds 2 --json results/mom_cost.json"])}
  </section>

  <section class="tool" id="vision">
    <h3 class="tool-cmd">Vision</h3>
    <p class="tool-desc">Real PNGs in <code class="chip">weights/eval_images</code>. Caption+MoM vs caption+big vs torchvision graphs.</p>
    {shell_block(["python scripts/helpers/bench/vision_proof.py --json results/vision_proof.json"])}
  </section>

  <section class="tool" id="tui">
    <h3 class="tool-cmd">Live terminals</h3>
    {shell_block([
        "PYTHONPATH=src:scripts/helpers python -m apps.duel",
        "PYTHONPATH=src:scripts/helpers python -m apps.livebench",
        "PYTHONPATH=src:scripts/helpers python -m apps.vision",
    ])}
    <p class="tool-desc">duel: MoM then big, streaming. livebench: full eval scoreboard. vision: ResNet + BLIP + MoM vs big.</p>
  </section>
""",
        ),
    )

    write(
        "documentation/caveats/index.html",
        page(
            "caveats/",
            "Limits",
            "What speculative routing can hide, and what it cannot.",
            body="""
  <p class="lead">The thesis is composition that <em>feels</em> like one model. That only holds when extra work fits under overlapped wall time. Other graphs are valid — they just show seams.</p>

  <h2>Can hide (or already one hop)</h2>
  <div class="table-wrap mb">
    <table class="plain">
      <thead><tr><th>Shape</th><th>Why</th></tr></thead>
      <tbody>
        <tr><td>speculate hit</td><td>Router ∥ likely winner. Wall ≈ max(router, prior). Orchestration should stay tiny.</td></tr>
        <tr><td>single model</td><td>Nothing to hide.</td></tr>
      </tbody>
    </table>
  </div>

  <h2>Cannot hide</h2>
  <div class="table-wrap mb">
    <table class="plain">
      <thead><tr><th>Shape</th><th>Why</th></tr></thead>
      <tbody>
        <tr><td>speculate miss</td><td>Correct route, visible penalty. Cancel the loser; you still pay the true model.</td></tr>
        <tr><td>serial route</td><td>Router then generator, summed.</td></tr>
        <tr><td>pipeline</td><td>Each depend hop adds wall. Caption then chat is a pipeline plus speculate on the chat hop only.</td></tr>
        <tr><td>heavy reconcile</td><td>Fan-out can overlap; the join does not.</td></tr>
      </tbody>
    </table>
  </div>

  <h2>Also true</h2>
  <ul class="lead-list">
    <li>v1 is colocated. No cross-host shared state.</li>
    <li>Small models ramble if you do not cap tokens. Fast hop is capped on purpose.</li>
    <li>ImageNet ResNet on solid color PNGs is a bad specialist. Use BLIP caption for those questions.</li>
    <li>The TUI that runs MoM then the big model is two jobs. Do not judge speed from that screen.</li>
  </ul>
""",
        ),
    )

    write(
        "README.md",
        """# MoM docs (GitHub Pages)

Same chrome as other Aquin Labs docs.

```
docs/
  documentation/   # product docs
  assets/          # CSS, logo, favicon
  index.html       # redirects → documentation/
```

**Edit HTML under `documentation/`.** Markdown notes (`concepts.md`, `adapter_guide.md`, …) remain as repo text.

GitHub: https://github.com/aquinlabs/mom
""",
    )


if __name__ == "__main__":
    main()
