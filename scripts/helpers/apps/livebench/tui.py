"""
Live eval: MoM vs always-small vs always-big.

  PYTHONPATH=src:scripts/helpers python -m apps.livebench

space pause/resume   q quit
"""

from __future__ import annotations

import curses
import logging
import os
import sys
import threading
import time
import warnings
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

os.environ["MOM_LOG_LEVEL"] = "ERROR"
os.environ["TQDM_DISABLE"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [
    str(ROOT / "src"),
    str(ROOT),
    str(ROOT / "scripts" / "helpers"),
    str(ROOT / "scripts" / "helpers" / "bench"),
]

from eval_set import EVAL, gold_ok  # noqa: E402
from mom import StateStore, run  # noqa: E402
from mom.adapters.local_chat import reset_token_meter, token_meter_snapshot  # noqa: E402
from mom.logging_config import setup_logging  # noqa: E402
from mom.runtime import ID_CHAT_FAST, ID_CHAT_STRONG, build_directory, build_registry  # noqa: E402

FAST_M = 135
STRONG_M = 360


def _text(out: Any) -> str:
    if isinstance(out, dict):
        for k in ("text", "answer", "output"):
            if isinstance(out.get(k), str):
                return out[k]
        return str(out)
    return str(out)


def _spec(metrics: dict[str, Any]) -> str:
    spec = metrics.get("spec") or {}
    if isinstance(spec, dict) and spec:
        return str(next(iter(spec.values())))
    return "-"


@dataclass
class Totals:
    n: int = 0
    ok: int = 0
    wall_ms: float = 0.0
    tok_fast: int = 0
    tok_strong: int = 0
    easy_n: int = 0
    easy_ok: int = 0
    hard_n: int = 0
    hard_ok: int = 0

    @property
    def work(self) -> float:
        return self.tok_fast * FAST_M + self.tok_strong * STRONG_M

    def add(self, *, ok: bool, ms: float, tf: int, ts: int, diff: str) -> None:
        self.n += 1
        if ok:
            self.ok += 1
        self.wall_ms += ms
        self.tok_fast += tf
        self.tok_strong += ts
        if diff == "easy":
            self.easy_n += 1
            if ok:
                self.easy_ok += 1
        else:
            self.hard_n += 1
            if ok:
                self.hard_ok += 1


@dataclass
class Bench:
    lock: threading.Lock = field(default_factory=threading.Lock)
    status: str = "loading models…"
    error: str = ""
    ready: bool = False
    busy: bool = True
    paused: bool = False
    done: bool = False
    idx: int = 0
    arm_name: str = ""
    prompt: str = ""
    gold: str = ""
    last_pred: str = ""
    last_ok: bool | None = None
    last_ms: float = 0.0
    log: list[str] = field(default_factory=list)
    mom: Totals = field(default_factory=Totals)
    fast: Totals = field(default_factory=Totals)
    strong: Totals = field(default_factory=Totals)
    directory: Any = None
    g_mom: Any = None
    g_fast: Any = None
    g_strong: Any = None

    def boot(self) -> None:
        try:
            self.directory = build_directory()
            reg = build_registry(self.directory)
            self.g_mom = reg.get("speculate_chat").graph
            self.g_fast = reg.get("direct_fast").graph
            self.g_strong = reg.get("direct_strong").graph
            run(self.g_mom, "Say ok.", self.directory, state=StateStore())
            run(self.g_fast, "Say ok.", self.directory, state=StateStore())
            run(self.g_strong, "Say ok.", self.directory, state=StateStore())
            with self.lock:
                self.ready = True
                self.busy = False
                self.status = "running evals…"
        except Exception as e:  # noqa: BLE001
            with self.lock:
                self.error = str(e)
                self.status = "load failed"
                self.busy = False

    def toggle_pause(self) -> None:
        with self.lock:
            if self.done or not self.ready:
                return
            self.paused = not self.paused
            self.status = "paused" if self.paused else "running evals…"

    def _one(self, graph, prompt: str) -> tuple[str, float, str, int, int]:
        reset_token_meter()
        state = StateStore()
        t0 = time.perf_counter()
        result = run(graph, prompt, self.directory, state=state)
        ms = (time.perf_counter() - t0) * 1000.0
        snap = token_meter_snapshot()
        tf = int(snap.get(ID_CHAT_FAST) or 0)
        ts = int(snap.get(ID_CHAT_STRONG) or 0)
        return _text(result.output), ms, _spec(dict(result.metrics)), tf, ts

    def run_all(self) -> None:
        try:
            for i, item in enumerate(EVAL):
                while True:
                    with self.lock:
                        if self.paused:
                            pass
                        else:
                            break
                    time.sleep(0.05)
                prompt = item["prompt"]
                gold = str(item.get("gold") or "")
                diff = item["diff"]
                for name, graph, bucket in (
                    ("mom", self.g_mom, self.mom),
                    ("small", self.g_fast, self.fast),
                    ("big", self.g_strong, self.strong),
                ):
                    with self.lock:
                        self.idx = i
                        self.arm_name = name
                        self.prompt = prompt
                        self.gold = gold
                        self.status = f"{item['id']} {diff} · {name}…"
                    with _quiet_stdio():
                        pred, ms, spec, tf, ts = self._one(graph, prompt)
                    ok = gold_ok(pred, item)
                    bucket.add(ok=ok, ms=ms, tf=tf, ts=ts, diff=diff)
                    line = (
                        f"{item['id']:4} {diff:4} {name:5} "
                        f"{'OK' if ok else 'NO':2} {ms:6.0f}ms {spec:4} "
                        f"{(pred or '').replace(chr(10), ' ')[:40]}"
                    )
                    with self.lock:
                        self.last_pred = pred
                        self.last_ok = ok
                        self.last_ms = ms
                        self.log.append(line)
                        if len(self.log) > 24:
                            self.log = self.log[-24:]
            with self.lock:
                self.done = True
                self.arm_name = ""
                cheaper = self.mom.work < self.strong.work
                faster = self.mom.wall_ms < self.strong.wall_ms
                better_hard = (
                    (self.mom.hard_ok / self.mom.hard_n if self.mom.hard_n else 0)
                    > (self.fast.hard_ok / self.fast.hard_n if self.fast.hard_n else 0)
                )
                bits = [
                    "CHEAPER than big" if cheaper else "NOT cheaper than big",
                    "FASTER than big" if faster else "NOT faster than big",
                    "beats small on hard" if better_hard else "does not beat small on hard",
                ]
                self.status = "done · " + " · ".join(bits)
        except Exception as e:  # noqa: BLE001
            with self.lock:
                self.error = str(e)
                self.status = "error"
                self.done = True


def _mute() -> None:
    setup_logging(level="ERROR", json_logs=False)
    logging.disable(logging.WARNING)
    for name in ("mom", "mom.runtime", "mom.engines", "transformers", "huggingface_hub"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
        logging.getLogger(name).propagate = False
    warnings.filterwarnings("ignore")
    try:
        from huggingface_hub.utils import disable_progress_bars

        disable_progress_bars()
    except Exception:
        pass
    try:
        from transformers.utils import logging as tf_logging

        tf_logging.set_verbosity_error()
        tf_logging.disable_progress_bar()
    except Exception:
        pass
    try:
        from tqdm import tqdm

        tqdm.disable = True
    except Exception:
        pass


@contextmanager
def _quiet_stdio():
    with open(os.devnull, "w") as sink:
        with redirect_stdout(sink), redirect_stderr(sink):
            yield


def _row(stdscr, y: int, w: int, text: str, attr: int) -> None:
    try:
        stdscr.addnstr(y, 1, text, max(1, w - 2), attr)
    except curses.error:
        pass


def loop(stdscr: curses.window, bench: Bench) -> None:
    curses.curs_set(0)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_WHITE, -1)
    curses.init_pair(5, curses.COLOR_RED, -1)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    while True:
        h, w = stdscr.getmaxyx()
        with bench.lock:
            status = bench.status
            err = bench.error
            idx = bench.idx
            arm = bench.arm_name
            prompt = bench.prompt
            gold = bench.gold
            pred = bench.last_pred
            last_ok = bench.last_ok
            log = list(bench.log)
            mom, fast, strong = bench.mom, bench.fast, bench.strong
            done = bench.done
            paused = bench.paused
            n_eval = len(EVAL)

        stdscr.erase()
        title = f"live bench  {min(idx + 1, n_eval)}/{n_eval}"
        if paused:
            title += "  PAUSED"
        _row(stdscr, 0, w, title, curses.color_pair(1) | curses.A_BOLD)
        _row(stdscr, 1, w, status, curses.color_pair(5) if err else curses.color_pair(1))
        if err:
            _row(stdscr, 2, w, err, curses.color_pair(5))
            yq = 3
        else:
            yq = 2
        q = f"Q [{arm or '-'}]: {prompt}" if prompt else "Q: (starting)"
        _row(stdscr, yq, w, q, curses.color_pair(4))
        _row(stdscr, yq + 1, w, f"gold={gold}", curses.color_pair(4))
        if last_ok is not None:
            mark = "OK" if last_ok else "NO"
            col = curses.color_pair(2) if last_ok else curses.color_pair(5)
            _row(stdscr, yq + 2, w, f"last {mark}: {(pred or '')[: max(1, w - 12)]}", col)

        y = yq + 4
        _row(
            stdscr,
            y,
            w,
            f"{'arm':6} {'acc':>7} {'easy':>7} {'hard':>7} {'work':>10} {'wall':>8}",
            curses.color_pair(4) | curses.A_BOLD,
        )
        for name, t, pair in (
            ("mom", mom, 2),
            ("small", fast, 4),
            ("big", strong, 3),
        ):
            acc = f"{t.ok}/{t.n}" if t.n else "-"
            easy = f"{t.easy_ok}/{t.easy_n}" if t.easy_n else "-"
            hard = f"{t.hard_ok}/{t.hard_n}" if t.hard_n else "-"
            line = (
                f"{name:6} {acc:>7} {easy:>7} {hard:>7} "
                f"{t.work:10.0f} {t.wall_ms:7.0f}ms"
            )
            _row(stdscr, y + 1, w, line, curses.color_pair(pair))
            y += 1

        y += 2
        _row(stdscr, y, w, "recent", curses.color_pair(4) | curses.A_BOLD)
        y += 1
        room = max(3, h - y - 2)
        for line in log[-room:]:
            bits = line.split()
            if "NO" in bits:
                col = curses.color_pair(5)
            elif "OK" in bits:
                col = curses.color_pair(2)
            else:
                col = curses.color_pair(4)
            _row(stdscr, y, w, line, col)
            y += 1
            if y >= h - 2:
                break

        hint = "space pause/resume   q quit"
        if done:
            hint = "done   q quit"
        _row(stdscr, h - 1, w, hint, curses.color_pair(4))
        stdscr.refresh()

        try:
            ch = stdscr.get_wch()
        except curses.error:
            time.sleep(0.05)
            continue
        if ch in ("q", "Q"):
            return
        if ch in (" ",) and not done:
            bench.toggle_pause()


def main() -> None:
    _mute()
    print("loading models…", flush=True)
    bench = Bench()
    with _quiet_stdio():
        bench.boot()
    if not bench.ready:
        print(bench.error or "load failed", file=sys.stderr)
        raise SystemExit(1)
    threading.Thread(target=bench.run_all, daemon=True).start()
    try:
        curses.wrapper(loop, bench)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
