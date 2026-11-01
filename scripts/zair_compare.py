#!/usr/bin/env python3
"""משווה ניכוי נורמטיבי של עסק זעיר מול הוצאות מוכרות בפועל."""
from __future__ import annotations

import argparse
import json
import sys

from _figures import get, number, shekels


def compare(year: int, turnover: float, expenses: float) -> dict:
    ceiling = get("patur_ceiling", year)
    pct = get("zair_normative_pct", year)
    if ceiling is None or pct is None:
        raise LookupError(f"אין נתוני עסק זעיר לשנת {year} ב-references/figures.md.")
    if turnover < 0 or expenses < 0:
        raise ValueError("סכומים לא יכולים להיות שליליים")
    normative = turnover * number(pct) / 100
    return {
        "year": year,
        "turnover": turnover,
        "actual_expenses": expenses,
        "normative_pct": number(pct),
        "normative": round(normative, 2),
        "difference": round(abs(normative - expenses), 2),
        "better": "zair" if normative > expenses else "regular" if expenses > normative else "equal",
        "over_ceiling": turnover > number(ceiling),
        "ceiling": number(ceiling),
    }


def render(r: dict) -> str:
    pct = f"{r['normative_pct']:g}%"
    lines = [f"{pct} מהמחזור של {shekels(r['turnover'])} הם {shekels(r['normative'])} (נכון לשנת {r['year']})."]
    lines.append(f"הוצאות מוכרות בפועל: {shekels(r['actual_expenses'])}.")
    if r["over_ceiling"]:
        lines.append(f"המחזור מעל התקרה של {shekels(r['ceiling'])}, ולכן עסק זעיר לא זמין בכלל.")
    elif r["better"] == "zair":
        lines.append(f"המסלול של {pct} מוריד {shekels(r['difference'])} יותר מההכנסה החייבת.")
    elif r["better"] == "regular":
        lines.append(f"ההוצאות בפועל מורידות {shekels(r['difference'])} יותר מההכנסה החייבת, ולכן המסלול הרגיל עדיף במספרים האלה.")
    else:
        lines.append("שני המסלולים יוצאים זהים. עסק זעיר פשוט יותר בדיווח.")
    lines.append("זה הפרש בהכנסה החייבת, לא הפרש במס. לפני שמחליטים, בדקו את התנאים עם רואה חשבון.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--turnover", type=float, required=True, help="מחזור שנתי")
    parser.add_argument("--expenses", type=float, required=True, help="הוצאות מוכרות בפועל")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = compare(args.year, args.turnover, args.expenses)
    except (LookupError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
