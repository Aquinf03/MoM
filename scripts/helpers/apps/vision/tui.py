"""
Watch torchvision + BLIP, then MoM chat vs always-big.

  PYTHONPATH=src:scripts/helpers python -m apps.vision

n next image   q quit
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

os.environ["MOM_LOG_LEVEL"] = "ERROR"
os.environ["TQDM_DISABLE"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [
    str(ROOT / "src"),
    str(ROOT),
    str(ROOT / "scripts" / "helpers"),
    str(ROOT / "scripts" / "helpers" / "bench"),
]

from mom import StateStore, run  # noqa: E402
from mom.logging_config import setup_logging  # noqa: E402
from mom.runtime import build_directory, build_registry  # noqa: E402

IM = ROOT / "weights" / "eval_images"
ITEMS = [
    (IM / "solid_red.png", "What color is this? One word."),
    (IM / "solid_blue.png", "What color is this? One word."),
    (IM / "solid_green.png", "What color is this? One word."),
    (IM / "circle_gray.png", "Is there a circle? yes or no."),
    (
        IM / "split_red_blue.png",
        "Reason carefully. Name the two colors. Two words only.",
    ),
]


def _text(out) -> str:
    if isinstance(out, dict):
        for k in ("text", "caption", "top"):
            if isinstance(out.get(k), str):
                return out[k]
        return str(out)
    return str(out)


class VisionShow:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.status = "loading…"
        self.error = ""
        self.ready = False
        self.busy = True
        self.idx = 0
        self.torch_text = ""
        self.caption = ""
        self.mom_text = ""
        self.big_text = ""
        self.mom_ms = 0.0
        self.big_ms = 0.0
        self.mom_spec = ""
        self.directory = None
        self.g_torch = None
        self.g_cap = None
        self.g_mom = None
        self.g_big = None

    def boot(self) -> None:
        try:
            self.directory = build_directory()
            reg = build_registry(self.directory)
            self.g_torch = reg.get("direct_torch").graph
            self.g_cap = reg.get("direct_caption").graph
            self.g_mom = reg.get("caption_chat").graph
            self.g_big = reg.get("caption_strong").graph
            img, q = ITEMS[0]
            payload = {"image": str(img), "text": q}
            run(self.g_torch, payload, self.directory, state=StateStore())
            run(self.g_mom, payload, self.directory, state=StateStore())
            with self.lock:
                self.ready = True
                self.busy = False
                self.status = "n next image · q quit"
        except Exception as e:  # noqa: BLE001
            with self.lock:
                self.error = str(e)
                self.status = "load failed"
                self.busy = False

    def kick(self) -> None:
        if self.busy or not self.ready:
            return
        with self.lock:
            self.busy = True
            self.status = "running…"
            self.torch_text = self.caption = self.mom_text = self.big_text = ""
        threading.Thread(target=self._run, daemon=True).start()

    def next_item(self) -> None:
        if self.busy or not self.ready:
            return
        with self.lock:
            self.idx = (self.idx + 1) % len(ITEMS)
        self.kick()

    def _run(self) -> None:
        try:
            with self.lock:
                idx = self.idx
            img, q = ITEMS[idx]
            payload = {"image": str(img), "text": q}
            st = StateStore()
            t = run(self.g_torch, payload, self.directory, state=st)
            with self.lock:
                self.torch_text = str(st.get("vision_top") or _text(t.output))
                self.status = "caption…"
            st2 = StateStore()
            c = run(self.g_cap, payload, self.directory, state=st2)
            with self.lock:
                self.caption = str(st2.get("caption") or _text(c.output))
                self.status = "MoM…"
            t0 = time.perf_counter()
            m = run(self.g_mom, payload, self.directory, state=StateStore())
            mom_ms = (time.perf_counter() - t0) * 1000.0
            spec = m.metrics.get("spec") or {}
            outcome = next(iter(spec.values()), "") if isinstance(spec, dict) else ""
            with self.lock:
                self.mom_text = _text(m.output)
                self.mom_ms = mom_ms
                self.mom_spec = str(outcome)
                self.status = "big…"
            t1 = time.perf_counter()
            b = run(self.g_big, payload, self.directory, state=StateStore())
            big_ms = (time.perf_counter() - t1) * 1000.0
            with self.lock:
                self.big_text = _text(b.output)
                self.big_ms = big_ms
                self.status = f"{img.name} · n next · q quit"
        except Exception as e:  # noqa: BLE001
            with self.lock:
                self.error = str(e)
                self.status = "error"
        finally:
            with self.lock:
                self.busy = False


def _mute() -> None:
    setup_logging(level="ERROR", json_logs=False)
    logging.disable(logging.WARNING)
    warnings.filterwarnings("ignore")
    try:
        from transformers.utils import logging as tf_logging

        tf_logging.set_verbosity_error()
        tf_logging.disable_progress_bar()
    except Exception:
        pass


@contextmanager
def _quiet_stdio():
    with open(os.devnull, "w") as sink:
        with redirect_stdout(sink), redirect_stderr(sink):
            yield


def _row(stdscr, y, w, text, attr):
    try:
        stdscr.addnstr(y, 1, text, max(1, w - 2), attr)
    except curses.error:
        pass


def loop(stdscr, show: VisionShow) -> None:
    curses.curs_set(0)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_WHITE, -1)
    curses.init_pair(5, curses.COLOR_RED, -1)
    stdscr.nodelay(True)
    show.kick()
    while True:
        h, w = stdscr.getmaxyx()
        with show.lock:
            status, err = show.status, show.error
            idx = show.idx
            torch_t, cap = show.torch_text, show.caption
            mom, big = show.mom_text, show.big_text
            mom_ms, big_ms, spec = show.mom_ms, show.big_ms, show.mom_spec
            busy = show.busy
        img, q = ITEMS[idx]
        stdscr.erase()
        _row(stdscr, 0, w, "vision graphs (torchvision + BLIP + MoM)", curses.color_pair(1) | curses.A_BOLD)
        _row(stdscr, 1, w, status, curses.color_pair(5) if err else curses.color_pair(1))
        if err:
            _row(stdscr, 2, w, err, curses.color_pair(5))
        _row(stdscr, 3, w, f"image: {img.name}", curses.color_pair(4))
        _row(stdscr, 4, w, f"Q: {q}", curses.color_pair(4))
        _row(stdscr, 6, w, f"torchvision top: {torch_t or '…'}", curses.color_pair(3))
        _row(stdscr, 7, w, f"BLIP caption:    {cap or '…'}", curses.color_pair(3))
        _row(stdscr, 9, w, f"MoM {spec} {mom_ms:.0f}ms", curses.color_pair(2) | curses.A_BOLD)
        _row(stdscr, 10, w, (mom or "…")[: max(1, w - 2)], curses.color_pair(2))
        _row(stdscr, 12, w, f"always-big {big_ms:.0f}ms", curses.color_pair(3) | curses.A_BOLD)
        _row(stdscr, 13, w, (big or "…")[: max(1, w - 2)], curses.color_pair(3))
        _row(stdscr, h - 1, w, "n next image   q quit", curses.color_pair(4))
        stdscr.refresh()
        try:
            ch = stdscr.get_wch()
        except curses.error:
            time.sleep(0.05)
            continue
        if ch in ("q", "Q"):
            return
        if ch in ("n", "N") and not busy:
            show.next_item()


def main() -> None:
    _mute()
    print("loading vision models…", flush=True)
    show = VisionShow()
    with _quiet_stdio():
        show.boot()
    if not show.ready:
        print(show.error or "load failed", file=sys.stderr)
        raise SystemExit(1)
    try:
        curses.wrapper(loop, show)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
