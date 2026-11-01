#!/usr/bin/env python3
"""תחזית מול תקרת עוסק פטור. התחזית קובעת, לא האחוז.

לכל חודש שנשאר: הגבוה מבין החוזה של אותו חודש לבין הקצב הרץ. חד-פעמי נוסף מתווסף מעל.
"""
from __future__ import annotations

import argparse
import json
import sys

from _figures import get, number, shekels


def parse_contract(text: str) -> tuple[int, float]:
    try:
        month, amount = text.split(":")
        return int(month), float(amount)
    except ValueError:
        raise argparse.ArgumentTypeError(f"חוזה בפורמט חודש:סכום, למשל 9:20000. התקבל: {text}")


def project(ytd, month, open_month=1, rate=None, past_one_offs=0.0, contracts=(), one_offs=(), no_more_work=False):
    if not 1 <= month <= 12 or not 1 <= open_month <= month:
        raise ValueError("חודש לא תקין: חודש הפתיחה חייב להיות בין 1 לחודש הנוכחי")
    if past_one_offs > ytd:
        raise ValueError("הפרויקטים החד-פעמיים לא יכולים לעבור את ההכנסה עד היום")

    by_month: dict[int, float] = {}
    for m, amount in contracts:
        if m < month or m > 12:
            raise ValueError(f"חוזה לחודש {m} לא בטווח שנשאר (מחודש {month} עד 12)")
        by_month[m] = by_month.get(m, 0.0) + amount

    months_active = month - open_month + 1
    if no_more_work:
        run_rate = 0.0
    elif rate is not None:
        run_rate = rate
    else:
        run_rate = (ytd - past_one_offs) / months_active

    # חוזה לחודש הנוכחי הוא כסף שעוד לא נכנס, ולכן מתווסף להכנסה עד היום
    total = ytd + by_month.get(month, 0.0) + sum(one_offs)
    path = [(month, total)]
    for m in range(month + 1, 13):
        total += max(by_month.get(m, 0.0), run_rate)
        path.append((m, total))
    return {"run_rate": run_rate, "projection": total, "path": path}


def evaluate(year, ytd, month, **kwargs):
    raw = get("patur_ceiling", year)
    if raw is None:
        raise LookupError(f"אין תקרה לשנת {year} ב-references/figures.md. בדקו באתר רשות המסים.")
    ceiling = number(raw)
    result = project(ytd, month, **kwargs)
    projection = result["projection"]
    crossing = next((m for m, value in result["path"] if value > ceiling), None)
    return {
        "year": year,
        "ceiling": ceiling,
        "ytd": ytd,
        "ytd_pct": round(ytd / ceiling * 100, 1),
        "run_rate": round(result["run_rate"], 2),
        "projection": round(projection, 2),
        "projection_pct": round(projection / ceiling * 100, 1),
        "crossing_month": crossing,
        "duty_live": projection > ceiling,
        "partial_year": kwargs.get("open_month", 1) > 1,
    }


def band(pct: float) -> str:
    if pct >= 95:
        return "95% ומעלה"
    if pct >= 85:
        return "85% ומעלה"
    if pct >= 70:
        return "70% ומעלה"
    return "מתחת ל-70%"


def render(r: dict) -> str:
    lines = [
        f"{shekels(r['ytd'])} מתוך התקרה של {shekels(r['ceiling'])} (נכון לשנת {r['year']}), שהם {r['ytd_pct']}%.",
        f"קצב חודשי בחישוב: {shekels(r['run_rate'])}.",
        f"תחזית לסוף השנה: {shekels(r['projection'])}, שהם {r['projection_pct']}% מהתקרה.",
    ]
    if r["duty_live"]:
        lines.append("חובת ההודעה כבר חלה: התחזית עוברת את התקרה, גם אם הכסף עוד לא הגיע.")
        lines.append(f"בקצב הזה התקרה נחצית בחודש {r['crossing_month']}. שינוי הסיווג צריך להיעשות לפני התשלום שחוצה.")
    else:
        margin = r["ceiling"] - r["projection"]
        lines.append(f"אין צורך בפעולה כרגע, רק מעקב. נשארו {shekels(margin)} עד התקרה לפי התחזית.")
    lines.append(f"להקשר בלבד, האחוז עד היום: {band(r['ytd_pct'])}. התחזית היא שקובעת.")
    if r["partial_year"]:
        lines.append("העסק נפתח באמצע השנה: לא בדקנו אם התקרה יחסית. שאלו רואה חשבון.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--ytd", type=float, required=True, help="הכנסות מתחילת השנה")
    parser.add_argument("--month", type=int, required=True, help="החודש הנוכחי, 1 עד 12")
    parser.add_argument("--open-month", type=int, default=1, help="חודש הפתיחה, אם נפתח השנה")
    parser.add_argument("--rate", type=float, help="קצב חודשי שהמשתמש אמר")
    parser.add_argument("--past-one-offs", type=float, default=0.0, help="חד-פעמיים שכבר בתוך ההכנסה עד היום")
    parser.add_argument("--contract", type=parse_contract, action="append", default=[], help="חודש:סכום")
    parser.add_argument("--one-off", type=float, action="append", default=[], help="פרויקט נוסף מעל הזרם הרגיל")
    parser.add_argument("--no-more-work", action="store_true", help="המשתמש אמר שאין עוד עבודה")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = evaluate(
            args.year, args.ytd, args.month, open_month=args.open_month, rate=args.rate,
            past_one_offs=args.past_one_offs, contracts=args.contract, one_offs=args.one_off,
            no_more_work=args.no_more_work,
        )
    except (LookupError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
