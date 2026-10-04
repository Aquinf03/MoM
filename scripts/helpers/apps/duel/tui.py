"""
Split-screen terminal: watch MoM answer, then the big model.

  PYTHONPATH=src:scripts/helpers python -m apps.duel

Type a question and hit enter.
  e  easy example     h  hard example     q  quit
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
from pathlib import Path

# Kill library noise before mom / transformers import.
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

from eval_set import prompts  # noqa: E402
from mom import StateStore  # noqa: E402
from mom.logging_config import setup_logging  # noqa: E402
from mom.runtime import ID_CHAT_FAST, ID_CHAT_STRONG, build_directory  # noqa: E402

EASY = prompts("easy")
HARD = prompts("hard")


class Duel:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.prompt = ""
        self.draft = ""
        self.status = "loading models…"
        self.busy = True
        self.ready = False
        self.error = ""
        self.mom_text = ""
        self.big_text = ""
        self.mom_ms = 0.0
        self.big_ms = 0.0
        self.mom_tag = ""
        self.mom_live = False
        self.big_live = False
        self._ex = 0
        self._hx = 0
        self.directory = None
        self._router = None
        self._fast = None
        self._strong = None

    def boot(self) -> None:
        try:
            self.directory = build_directory()
            self._router = self.directory.create("prod.router")
            self._fast = self.directory.create(ID_CHAT_FAST)
            self._strong = self.directory.create(ID_CHAT_STRONG)
            # force weights in
            st = StateStore()
            self._fast.run("Say ok.", st)
            self._strong.run("Say ok.", StateStore())
            with self.lock:
                self.busy = False
                self.ready = True
                self.status = "type a question · e easy · h hard · enter go · q quit"
        except Exception as e:  # noqa: BLE001
            with self.lock:
                self.busy = False
                self.error = str(e)
                self.status = "load failed"

    def start(self, prompt: str) -> None:
        prompt = prompt.strip()
        if not prompt or self.busy or not self.ready:
            return
        with self.lock:
            self.busy = True
            self.prompt = prompt
            self.draft = ""
            self.mom_text = ""
            self.big_text = ""
            self.mom_ms = 0.0
            self.big_ms = 0.0
            self.mom_tag = ""
            self.mom_live = False
            self.big_live = False
            self.status = "MoM going…"
            self.error = ""
        threading.Thread(target=self._run, args=(prompt,), daemon=True).start()

    def _run(self, prompt: str) -> None:
        try:
            with _quiet_stdio():
                route_out = self._router.run(prompt, StateStore())
                route = route_out.get("route") if isinstance(route_out, dict) else None
                if route not in (ID_CHAT_FAST, ID_CHAT_STRONG):
                    route = ID_CHAT_FAST
                hit = route == ID_CHAT_FAST
                tag = "HIT → small" if hit else "MISS → big"
                mom_model = self._fast if hit else self._strong
                with self.lock:
                    self.mom_tag = tag
                    self.mom_live = True
                t0 = time.perf_counter()
                acc = []
                for piece in mom_model.stream(prompt, StateStore()):
                    acc.append(piece)
                    with self.lock:
                        self.mom_text = "".join(acc)
                        self.mom_ms = (time.perf_counter() - t0) * 1000.0
                with self.lock:
                    self.mom_live = False
                    self.mom_ms = (time.perf_counter() - t0) * 1000.0
                    self.status = "big model going…"
                    self.big_live = True
                t1 = time.perf_counter()
                acc = []
                for piece in self._strong.stream(prompt, StateStore()):
                    acc.append(piece)
                    with self.lock:
                        self.big_text = "".join(acc)
                        self.big_ms = (time.perf_counter() - t1) * 1000.0
                with self.lock:
                    self.big_live = False
                    self.big_ms = (time.perf_counter() - t1) * 1000.0
                    faster = "MoM faster" if self.mom_ms < self.big_ms else "big faster"
                    self.status = f"done · {faster} · e/h for another · type to ask"
        except Exception as e:  # noqa: BLE001
            with self.lock:
                self.error = str(e)
                self.status = "error"
                self.mom_live = False
                self.big_live = False
        finally:
            with self.lock:
                self.busy = False

    def example(self, hard: bool) -> None:
        if hard:
            q = HARD[self._hx % len(HARD)]
            self._hx += 1
        else:
            q = EASY[self._ex % len(EASY)]
            self._ex += 1
        self.start(q)


def _wrap(text: str, width: int, height: int) -> list[str]:
    if width < 8 or height < 1:
        return []
    lines: list[str] = []
    for raw in (text or "").splitlines() or [""]:
        s = raw
        if not s:
            lines.append("")
            continue
        while s:
            lines.append(s[:width])
            s = s[width:]
    if not lines:
        lines = [""]
    if len(lines) > height:
        return lines[-height:]
    return lines


def _mute_libraries() -> None:
    setup_logging(level="ERROR", json_logs=False)
    logging.disable(logging.WARNING)
    for name in (
        "mom",
        "mom.runtime",
        "mom.engines",
        "transformers",
        "huggingface_hub",
        "torch",
        "accelerate",
        "httpx",
    ):
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


def loop(stdscr: curses.window, duel: Duel) -> None:
    curses.curs_set(1)
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
        if h < 12 or w < 40:
            stdscr.erase()
            stdscr.addstr(0, 0, "window too small")
            stdscr.refresh()
            time.sleep(0.05)
            continue

        with duel.lock:
            prompt = duel.prompt
            draft = duel.draft
            status = duel.status
            err = duel.error
            mom_text = duel.mom_text
            big_text = duel.big_text
            mom_ms = duel.mom_ms
            big_ms = duel.big_ms
            tag = duel.mom_tag
            mom_live = duel.mom_live
            big_live = duel.big_live
            busy = duel.busy

        stdscr.erase()
        title = "MoM vs big"
        try:
            stdscr.addnstr(0, 1, title, w - 2, curses.color_pair(1) | curses.A_BOLD)
            qline = f"Q: {prompt}" if prompt else "Q: (none yet)"
            stdscr.addnstr(1, 1, qline, w - 2, curses.color_pair(4))
            stdscr.addnstr(2, 1, status, w - 2, curses.color_pair(5) if err else curses.color_pair(1))
            if err:
                stdscr.addnstr(3, 1, err[: w - 2], w - 2, curses.color_pair(5))
        except curses.error:
            pass

        split = max(18, w // 2)
        pane_top = 4 if not err else 5
        pane_h = max(5, h - pane_top - 3)
        left_w = split - 1
        right_w = w - split
        mom_head = f" MoM {tag}  {mom_ms:.0f}ms" + (" …" if mom_live else "")
        big_head = f" big  {big_ms:.0f}ms" + (" …" if big_live else "")
        try:
            stdscr.attron(curses.color_pair(2))
            stdscr.hline(pane_top, 0, curses.ACS_HLINE, left_w)
            stdscr.addnstr(pane_top, 1, mom_head[: left_w - 2], left_w - 2, curses.color_pair(2) | curses.A_BOLD)
            stdscr.vline(pane_top, left_w, curses.ACS_VLINE, pane_h)
            stdscr.attron(curses.color_pair(3))
            stdscr.hline(pane_top, split, curses.ACS_HLINE, max(1, right_w - 1))
            stdscr.addnstr(pane_top, split + 1, big_head[: max(1, right_w - 3)], max(1, right_w - 3), curses.color_pair(3) | curses.A_BOLD)
            stdscr.attroff(curses.color_pair(3))
        except curses.error:
            pass

        inner_h = pane_h - 2
        mom_lines = _wrap(mom_text or ("…" if mom_live else ""), max(1, left_w - 2), inner_h)
        big_lines = _wrap(big_text or ("…" if big_live else ""), max(1, right_w - 2), inner_h)
        for i, line in enumerate(mom_lines):
            try:
                stdscr.addnstr(pane_top + 1 + i, 1, line, max(1, left_w - 2), curses.color_pair(2))
            except curses.error:
                pass
        for i, line in enumerate(big_lines):
            try:
                stdscr.addnstr(pane_top + 1 + i, split + 1, line, max(1, right_w - 2), curses.color_pair(3))
            except curses.error:
                pass

        hint = "e easy  h hard  enter send  q quit"
        bar = f"> {draft}"
        try:
            stdscr.addnstr(h - 2, 1, hint, w - 2, curses.color_pair(4))
            stdscr.addnstr(h - 1, 1, bar, w - 2, curses.color_pair(4) | curses.A_BOLD)
        except curses.error:
            pass
        stdscr.move(h - 1, min(w - 2, 3 + len(draft)))
        stdscr.refresh()

        try:
            ch = stdscr.get_wch()
        except curses.error:
            time.sleep(0.03)
            continue
        if ch == curses.KEY_RESIZE:
            continue
        if busy:
            time.sleep(0.03)
            continue
        if ch in ("q", "Q") and not draft:
            return
        if ch in ("e", "E") and not draft:
            duel.example(hard=False)
            continue
        if ch in ("h", "H") and not draft:
            duel.example(hard=True)
            continue
        if ch in ("\n", "\r", curses.KEY_ENTER):
            duel.start(draft)
            continue
        if ch in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            with duel.lock:
                duel.draft = duel.draft[:-1]
            continue
        if isinstance(ch, str) and ch.isprintable():
            with duel.lock:
                if len(duel.draft) < 500:
                    duel.draft += ch


def main() -> None:
    _mute_libraries()
    print("loading models…", flush=True)
    duel = Duel()
    with _quiet_stdio():
        duel.boot()
    if not duel.ready:
        print(duel.error or "load failed", file=sys.stderr)
        raise SystemExit(1)
    try:
        curses.wrapper(loop, duel)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
