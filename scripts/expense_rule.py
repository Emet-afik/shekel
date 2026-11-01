#!/usr/bin/env python3
"""קטגוריה וסכום נותנים את החלק המוכר, לפי הטבלה ב-references/expenses.md. אופציונלי: הסקיל עובד גם בלעדיו."""
from __future__ import annotations

import argparse
import json
import re
import sys

from _figures import ROOT, latest, number, shekels

EXPENSES = ROOT / "references" / "expenses.md"
ROW = re.compile(r"^\|\s*([a-z][a-z0-9_]*)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([a-z]+)\s*\|\s*([^|]*?)\s*\|")


def categories() -> dict[str, dict]:
    table = {}
    for line in EXPENSES.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match:
            key, label, part, method, note = match.groups()
            table[key] = {"label": label, "part": part, "method": method, "note": note}
    return table


def percent(part: str) -> float:
    return float(part)


def deductible(category: str, amount: float, year: int, share=None, annual=False, recipients=1) -> dict:
    table = categories()
    if category not in table:
        raise KeyError(f"קטגוריה לא מוכרת: {category}. אפשרויות: {', '.join(sorted(table))}")
    if amount < 0:
        raise ValueError("סכום לא יכול להיות שלילי")
    row = table[category]
    method = row["method"]
    out = {"category": category, "label": row["label"], "amount": amount, "method": method, "note": row["note"]}

    if method == "pct":
        out["deductible"] = round(amount * percent(row["part"]) / 100, 2)
    elif method == "share":
        if share is None or not 0 <= share <= 1:
            raise ValueError("בית ומשרד ביתי צריכים --share בין 0 ל-1, לפי החלק העסקי שהמשתמש חישב")
        out["share"] = share
        out["deductible"] = round(amount * share, 2)
    elif method == "phone":
        found = latest("phone_floor", year)
        if found is None:
            raise LookupError("אין סכום לטלפון נייד ב-references/figures.md")
        floor, floor_year = number(found[0]), found[1]
        yearly = amount if annual else amount * 12
        allowed = yearly - min(floor, yearly / 2)
        out["deductible"] = round(allowed if annual else allowed / 12, 2)
        out["figure_year"] = floor_year
    elif method == "vehicle":
        out["deductible"] = round(amount * percent(row["part"]) / 100, 2)
        out["minimum_only"] = True
    elif method == "depreciation":
        out["deductible"] = round(amount * percent(row["part"]) / 100, 2)
        out["per_year"] = True
    elif method == "gift":
        found = latest("gift_cap", year)
        if found is None:
            raise LookupError("אין תקרת מתנות ב-references/figures.md")
        out["deductible"] = round(min(amount, number(found[0]) * recipients), 2)
        out["figure_year"] = found[1]
    else:
        raise ValueError(f"שיטה לא מוכרת: {method}")
    return out


def render(r: dict, status: str) -> str:
    text = f"{r['label']}: מתוך {shekels(r['amount'])} מוכר {shekels(r['deductible'])}"
    if r.get("per_year"):
        text += " בשנה, כפחת"
    if r.get("share") is not None:
        text += f", לפי חלק עסקי של {r['share'] * 100:g}%"
    lines = [text + "."]
    if r.get("minimum_only"):
        lines.append("זה רק צד האחוז. בסוף השנה משווים להוצאות פחות שווי שימוש, והגבוה מביניהם קובע.")
    if r.get("figure_year"):
        lines.append(f"הסכום המתואם הוא של שנת המס {r['figure_year']}, בדקו עדכון.")
    if r["note"]:
        lines.append(r["note"] + ".")
    if status == "patur":
        lines.append("עוסק פטור: הסכום כולל מע\"מ, ואין קיזוז מע\"מ תשומות.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", required=True)
    parser.add_argument("--amount", type=float, required=True)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--share", type=float, help="חלק עסקי, בין 0 ל-1")
    parser.add_argument("--annual", action="store_true", help="הסכום שנתי, לטלפון נייד")
    parser.add_argument("--recipients", type=int, default=1, help="מספר מקבלי מתנה")
    parser.add_argument("--status", choices=["patur", "murshe"], default="patur")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = deductible(args.category, args.amount, args.year, args.share, args.annual, args.recipients)
    except (KeyError, LookupError, ValueError) as error:
        print(str(error).strip("'"), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False) if args.json else render(result, args.status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
