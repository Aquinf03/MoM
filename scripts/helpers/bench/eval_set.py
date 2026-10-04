"""Shared labeled evals for proof / cost / live TUI.

Easy: short facts the small model usually gets.
Hard: starts with "Reason carefully" so the production router sends them to strong.
"""

from __future__ import annotations

from typing import Any

EVAL: list[dict[str, Any]] = [
    {"id": "e1", "diff": "easy", "prompt": "What is 2+2? Reply with only the number.", "gold": "4"},
    {"id": "e2", "diff": "easy", "prompt": "Spell cat. One word.", "gold": "cat"},
    {"id": "e3", "diff": "easy", "prompt": "How many days in a week? Number only.", "gold": "7"},
    {"id": "e4", "diff": "easy", "prompt": "Is ice cold? yes or no.", "gold": "yes"},
    {"id": "e5", "diff": "easy", "prompt": "First letter of apple. One letter.", "gold": "a"},
    {"id": "e6", "diff": "easy", "prompt": "Sun rises in the east? yes or no.", "gold": "yes"},
    {"id": "e7", "diff": "easy", "prompt": "Color of a clear daytime sky? One word.", "gold": "blue"},
    {"id": "e8", "diff": "easy", "prompt": "Spell dog. One word.", "gold": "dog"},
    {"id": "e9", "diff": "easy", "prompt": "Is fire hot? yes or no.", "gold": "yes"},
    {"id": "e10", "diff": "easy", "prompt": "Is 2 even? yes or no.", "gold": "yes"},
    {"id": "e11", "diff": "easy", "prompt": "Spell hat. One word.", "gold": "hat"},
    {"id": "e12", "diff": "easy", "prompt": "Is snow white? yes or no.", "gold": "yes"},
    {"id": "e13", "diff": "easy", "prompt": "First letter of banana. One letter.", "gold": "b"},
    {"id": "e14", "diff": "easy", "prompt": "Is grass green? yes or no.", "gold": "yes"},
    {"id": "e15", "diff": "easy", "prompt": "Spell sun. One word.", "gold": "sun"},
    {"id": "e16", "diff": "easy", "prompt": "Is water wet? yes or no.", "gold": "yes"},
    {"id": "e17", "diff": "easy", "prompt": "Spell pig. One word.", "gold": "pig"},
    {"id": "e18", "diff": "easy", "prompt": "Is milk white? yes or no.", "gold": "yes"},
    {"id": "e19", "diff": "easy", "prompt": "First letter of dog. One letter.", "gold": "d"},
    {"id": "e20", "diff": "easy", "prompt": "Spell red. One word.", "gold": "red"},
    {"id": "e21", "diff": "easy", "prompt": "Is sugar sweet? yes or no.", "gold": "yes"},
    {"id": "e22", "diff": "easy", "prompt": "First letter of zoo. One letter.", "gold": "z"},
    {"id": "e23", "diff": "easy", "prompt": "Spell map. One word.", "gold": "map"},
    {"id": "e24", "diff": "easy", "prompt": "Is night dark? yes or no.", "gold": "yes"},
    {
        "id": "h1",
        "diff": "hard",
        "prompt": "Reason carefully. Compute (12+8)*3-10. Reply with only the final number.",
        "gold": "50",
    },
    {
        "id": "h2",
        "diff": "hard",
        "prompt": (
            "Reason carefully. John has 4 more apples than Mary. Mary has 3 apples. "
            "How many apples do they have together? Reply with only the number."
        ),
        "gold": "10",
    },
    {
        "id": "h3",
        "diff": "hard",
        "prompt": (
            "Reason carefully. Tom is 3 years older than Ana. Ana is 10. "
            "How old is Tom? Reply with only the number."
        ),
        "gold": "13",
    },
    {
        "id": "h4",
        "diff": "hard",
        "prompt": "Reason carefully. Compute 25+17. Reply with only the final number.",
        "gold": "42",
    },
    {
        "id": "h5",
        "diff": "hard",
        "prompt": "Reason carefully. Compute 30-11. Reply with only the final number.",
        "gold": "19",
    },
    {
        "id": "h6",
        "diff": "hard",
        "prompt": (
            "Reason carefully. Lea has 6 stickers. Sam has 2 more than Lea. "
            "How many stickers does Sam have? Reply with only the number."
        ),
        "gold": "8",
    },
    {
        "id": "h7",
        "diff": "hard",
        "prompt": "Reason carefully. Compute 14+19. Reply with only the final number.",
        "gold": "33",
    },
    {
        "id": "h8",
        "diff": "hard",
        "prompt": (
            "Reason carefully. Mia has 7 cards. She gives 2 away. "
            "How many cards does she have left? Reply with only the number."
        ),
        "gold": "5",
    },
]


def gold_ok(text: str, item: dict[str, Any]) -> bool:
    t = (text or "").lower()
    any_golds = item.get("gold_any")
    if isinstance(any_golds, list) and any_golds:
        return any(str(g).lower() in t for g in any_golds)
    gold = str(item.get("gold") or "").lower()
    if not gold:
        return False
    if gold in t.split() or t.strip() == gold or t.strip().endswith(gold):
        return True
    return gold in t


def prompts(diff: str) -> list[str]:
    return [x["prompt"] for x in EVAL if x["diff"] == diff]
