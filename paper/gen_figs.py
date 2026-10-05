#!/usr/bin/env python3
"""Generate torchvision + vision-proof figures into paper/figs/."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
import torchvision.models as models  # noqa: E402
import torchvision.transforms as T  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIGS = Path(__file__).resolve().parent / "figs"
IM = ROOT / "weights" / "eval_images"
RESULTS = ROOT / "results"

EVAL_NAMES = [
    "solid_red.png",
    "solid_blue.png",
    "solid_green.png",
    "circle_gray.png",
    "split_red_blue.png",
]


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "figure.dpi": 160,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def fig_eval_montage() -> None:
    paths = [IM / n for n in EVAL_NAMES if (IM / n).is_file()]
    fig, axes = plt.subplots(1, len(paths), figsize=(2.1 * len(paths), 2.2))
    if len(paths) == 1:
        axes = [axes]
    for ax, p in zip(axes, paths):
        ax.imshow(Image.open(p).convert("RGB"))
        ax.set_title(p.stem.replace("_", " "), fontsize=9)
        ax.axis("off")
    fig.suptitle("Vision eval set (synthetic pixels)", y=1.02)
    fig.savefig(FIGS / "eval_montage.png")
    plt.close(fig)


def _resnet18():
    weights = models.ResNet18_Weights.DEFAULT
    model = models.resnet18(weights=weights).eval()
    return model, weights


def fig_torch_topk() -> None:
    model, weights = _resnet18()
    tfm = weights.transforms()
    cats = weights.meta["categories"]
    paths = [IM / n for n in EVAL_NAMES if (IM / n).is_file()]

    fig, axes = plt.subplots(len(paths), 2, figsize=(7.2, 1.55 * len(paths)))
    for i, p in enumerate(paths):
        img = Image.open(p).convert("RGB")
        with torch.inference_mode():
            logits = model(tfm(img).unsqueeze(0))[0]
            prob = torch.softmax(logits, dim=0)
            top = torch.topk(prob, 5)

        axes[i, 0].imshow(img)
        axes[i, 0].set_ylabel(p.stem.replace("_", "\n"), rotation=0, ha="right", va="center")
        axes[i, 0].set_xticks([])
        axes[i, 0].set_yticks([])

        labels = [cats[j] for j in top.indices.tolist()]
        vals = top.values.tolist()
        y = np.arange(len(labels))[::-1]
        axes[i, 1].barh(y, vals, color="#2f6fed")
        axes[i, 1].set_yticks(y)
        axes[i, 1].set_yticklabels(labels, fontsize=8)
        axes[i, 1].set_xlim(0, 1)
        axes[i, 1].set_xlabel("softmax" if i == len(paths) - 1 else "")
    fig.suptitle("torchvision ResNet18 top-5 on MoM eval images", y=0.995)
    fig.tight_layout()
    fig.savefig(FIGS / "torch_topk.png")
    plt.close(fig)


def fig_torch_activations() -> None:
    model, weights = _resnet18()
    tfm = weights.transforms()
    feats: dict[str, torch.Tensor] = {}

    def hook(_m, _i, o):
        feats["x"] = o.detach()

    handle = model.layer1.register_forward_hook(hook)
    paths = [IM / n for n in ("solid_red.png", "circle_gray.png", "split_red_blue.png") if (IM / n).is_file()]
    fig, axes = plt.subplots(len(paths), 5, figsize=(8.5, 1.7 * len(paths)))
    for r, p in enumerate(paths):
        img = Image.open(p).convert("RGB")
        with torch.inference_mode():
            _ = model(tfm(img).unsqueeze(0))
        fmap = feats["x"][0]  # C,H,W
        axes[r, 0].imshow(img)
        axes[r, 0].set_title(p.stem if r == 0 else "")
        axes[r, 0].set_ylabel(p.stem.replace("_", "\n"), rotation=0, ha="right", va="center")
        axes[r, 0].axis("off")
        for c in range(4):
            ax = axes[r, c + 1]
            ax.imshow(fmap[c].numpy(), cmap="magma")
            ax.set_title(f"ch {c}" if r == 0 else "")
            ax.axis("off")
    handle.remove()
    fig.suptitle("ResNet18 layer1 activations (torchvision)", y=1.01)
    fig.tight_layout()
    fig.savefig(FIGS / "torch_activations.png")
    plt.close(fig)


def fig_vision_scoreboard() -> None:
    data = json.loads((RESULTS / "vision_proof.json").read_text())
    tallies = data["tallies"]
    names = ["caption_chat", "caption_strong", "torch_chat", "torch_strong"]
    labels = ["caption+MoM", "caption+strong", "torch+MoM", "torch+strong"]
    acc = [tallies[n]["ok"] / tallies[n]["n"] for n in names]
    mean_ms = [tallies[n]["ms"] / tallies[n]["n"] for n in names]
    colors = ["#1f7a4c", "#6b7280", "#2f6fed", "#9ca3af"]

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(8.2, 3.2))
    ax0.bar(labels, acc, color=colors)
    ax0.set_ylim(0, 1.05)
    ax0.set_ylabel("accuracy")
    ax0.set_title("Vision graph accuracy")
    ax0.tick_params(axis="x", rotation=20)
    for i, v in enumerate(acc):
        ax0.text(i, v + 0.03, f"{v:.0%}", ha="center", fontsize=9)

    ax1.bar(labels, mean_ms, color=colors)
    ax1.set_ylabel("mean latency (ms)")
    ax1.set_title("Vision graph latency")
    ax1.tick_params(axis="x", rotation=20)
    for i, v in enumerate(mean_ms):
        ax1.text(i, v + 4, f"{v:.0f}", ha="center", fontsize=9)

    fig.suptitle("Vision proof: BLIP caption vs torchvision ResNet → chat", y=1.02)
    fig.tight_layout()
    fig.savefig(FIGS / "vision_scoreboard.png")
    plt.close(fig)


def fig_vision_per_item() -> None:
    data = json.loads((RESULTS / "vision_proof.json").read_text())
    rows = data["rows"]
    ids = []
    for r in rows:
        if r["id"] not in ids:
            ids.append(r["id"])
    arms = ["caption_chat", "torch_chat", "caption_strong", "torch_strong"]
    mat = np.zeros((len(arms), len(ids)))
    for r in rows:
        mat[arms.index(r["arm"]), ids.index(r["id"])] = 1.0 if r["ok"] else 0.0

    fig, ax = plt.subplots(figsize=(6.2, 2.8))
    im = ax.imshow(mat, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(ids)))
    ax.set_xticklabels(ids)
    ax.set_yticks(range(len(arms)))
    ax.set_yticklabels(arms)
    ax.set_title("Per-item correctness (green=OK)")
    for i in range(len(arms)):
        for j in range(len(ids)):
            ax.text(j, i, "OK" if mat[i, j] else "NO", ha="center", va="center", fontsize=8, color="black")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(FIGS / "vision_per_item.png")
    plt.close(fig)


def fig_text_mom() -> None:
    proof = json.loads((RESULTS / "mom_proof.json").read_text())["arms"]
    cost = json.loads((RESULTS / "mom_cost.json").read_text())
    arms = ["always_fast", "mom", "always_strong"]
    labels = ["always-fast", "MoM", "always-strong"]
    easy_p50 = [proof[a]["easy_p50"] for a in arms]
    hard_acc = [proof[a]["hard_acc"] for a in arms]
    work = [cost["arms"][a]["work"] for a in arms]
    colors = ["#9ca3af", "#2f6fed", "#6b7280"]

    fig, axes = plt.subplots(1, 3, figsize=(9.2, 3.0))
    axes[0].bar(labels, easy_p50, color=colors)
    axes[0].set_ylabel("easy p50 (ms)")
    axes[0].set_title("Easy latency")
    axes[1].bar(labels, hard_acc, color=colors)
    axes[1].set_ylabel("hard accuracy")
    axes[1].set_ylim(0, 1.05)
    axes[1].set_title("Hard accuracy")
    axes[2].bar(labels, work, color=colors)
    axes[2].set_ylabel("token×params work")
    axes[2].set_title("Compute proxy")
    for ax in axes:
        ax.tick_params(axis="x", rotation=15)
    fig.suptitle("Text speculate_chat vs always-fast / always-strong", y=1.02)
    fig.tight_layout()
    fig.savefig(FIGS / "text_scoreboard.png")
    plt.close(fig)


def fig_architecture() -> None:
    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")

    def box(x, y, w, h, text, color):
        r = plt.Rectangle((x, y), w, h, facecolor=color, edgecolor="#111", linewidth=1.2)
        ax.add_patch(r)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9)

    box(0.3, 1.5, 1.8, 1.0, "vision hop\n(caption / torch)", "#dbeafe")
    box(2.8, 2.4, 1.8, 1.0, "router", "#fef3c7")
    box(2.8, 0.6, 1.8, 1.0, "prior (fast)", "#dcfce7")
    box(5.6, 1.5, 1.8, 1.0, "strong\n(on miss)", "#fee2e2")
    box(8.0, 1.5, 1.6, 1.0, "output", "#e5e7eb")
    ax.annotate("", xy=(2.8, 2.9), xytext=(2.1, 2.2), arrowprops=dict(arrowstyle="->", lw=1.4))
    ax.annotate("", xy=(2.8, 1.1), xytext=(2.1, 1.8), arrowprops=dict(arrowstyle="->", lw=1.4))
    ax.annotate("", xy=(5.6, 2.0), xytext=(4.6, 2.9), arrowprops=dict(arrowstyle="->", lw=1.2, linestyle="--"))
    ax.annotate("", xy=(5.6, 2.0), xytext=(4.6, 1.1), arrowprops=dict(arrowstyle="->", lw=1.2))
    ax.annotate("", xy=(8.0, 2.0), xytext=(7.4, 2.0), arrowprops=dict(arrowstyle="->", lw=1.4))
    ax.text(3.7, 3.6, "speculate (overlap)", ha="center", fontsize=9, style="italic")
    ax.set_title("MoM vision → speculate chat graph")
    fig.savefig(FIGS / "architecture.png")
    plt.close(fig)


def main() -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    _style()
    fig_architecture()
    fig_eval_montage()
    fig_torch_topk()
    fig_torch_activations()
    fig_vision_scoreboard()
    fig_vision_per_item()
    fig_text_mom()
    print("wrote figures to", FIGS)


if __name__ == "__main__":
    main()
