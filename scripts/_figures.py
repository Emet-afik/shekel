"""Reads the machine table in references/figures.md. Every script gets its numbers from here."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIGURES = ROOT / "references" / "figures.md"
ROW = re.compile(r"^\|\s*([a-z][a-z0-9_]*)\s*\|\s*(\d{4})\s*\|\s*([^|]+?)\s*\|")


def load() -> dict[str, dict[int, str]]:
    table: dict[str, dict[int, str]] = {}
    for line in FIGURES.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match:
            key, year, value = match.groups()
            table.setdefault(key, {})[int(year)] = value
    return table


def get(key: str, year: int) -> str | None:
    """Exact year only. Returns None when that year was not entered."""
    return load().get(key, {}).get(year)


def latest(key: str, year: int) -> tuple[str, int] | None:
    """Most recent row at or before year, with the year it belongs to."""
    rows = load().get(key, {})
    years = [y for y in rows if y <= year]
    if not years:
        return None
    best = max(years)
    return rows[best], best


def number(value: str) -> float:
    return float(value.replace(",", ""))


def shekels(amount: float) -> str:
    return f"{round(amount):,} ₪"
