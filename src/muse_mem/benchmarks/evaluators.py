"""Dataset evaluation primitives."""
from __future__ import annotations

import re

def option_label(text: str) -> str | None:
    match = re.search(r"(?i)(?<![a-z])\(?([a-d])\)?(?![a-z])", text)
    return match.group(1).lower() if match else None

def personamem_exact_match(response: str, gold: str) -> int:
    predicted, expected = option_label(response), option_label(gold)
    return int(predicted is not None and predicted == expected)

def accuracy(rows: list[dict], score_field: str = "score") -> float:
    if not rows:
        return 0.0
    return sum(float(row[score_field]) for row in rows) / len(rows)
