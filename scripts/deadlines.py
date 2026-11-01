#!/usr/bin/env python3
"""שנה נותנת לוח מועדים בתאריכים לועזיים: שבת עוברת לראשון, ושנה בלי מועד רשמי מקבלת "טרם פורסם"."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from _figures import get

DAYS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]


def parse(text: str) -> dt.date:
    day, month, year = (int(part) for part in text.split("."))
    return dt.date(year, month, day)


def shift(date: dt.date) -> dt.date:
    return date + dt.timedelta(days=1) if date.weekday() == 5 else date


def entry(date, title, who, prepare, where, note="", movable=True) -> dict:
    final = shift(date) if movable else date
    if final != date:
        note = f"{date.day}.{date.month}.{date.year} נופל בשבת, עובר לראשון. {note}".strip()
    if not movable and date.weekday() == 5:
        note = f"נופל בשבת ולא נדחה: מפקידים לפני כן. {note}".strip()
    return {
        "date": final.isoformat(),
        "display": f"{final.day}.{final.month}.{final.year}",
        "day": DAYS[final.weekday()],
        "title": title,
        "who": who,
        "prepare": prepare,
        "where": where,
        "note": note,
        "published": True,
    }


def unpublished(title, who, prepare, where, note="") -> dict:
    return {
        "date": None, "display": "טרם פורסם", "day": "", "title": title, "who": who,
        "prepare": prepare, "where": where, "note": note, "published": False,
    }


def build(year: int, status: str = "patur", mkdamot: str = "none", zair: bool = True) -> list[dict]:
    previous = year - 1
    rows = []

    if status == "patur":
        title = f"הצהרת עוסק פטור על מחזור {previous}"
        override = get("declaration_override", previous)
        where = "למע\"מ, באתר רשות המסים"
        if override:
            rows.append(entry(parse(override), title, "עוסק פטור", "סך המחזור מהיומן", where,
                              f"דחייה חד-פעמית לשנה הזו. הכלל הרגיל הוא 31.1."))
        else:
            rows.append(entry(dt.date(year, 1, 31), title, "עוסק פטור", "סך המחזור מהיומן", where))

    title = f"דוח שנתי 1301 על שנת המס {previous}"
    prep = "נתונים מדף הסיכום השנתי"
    where = "אתר רשות המסים, או רואה חשבון"
    paper, online = get("annual_report_paper", previous), get("annual_report_online", previous)
    if paper and online:
        rows.append(entry(parse(paper), title + ", לא מקוון", "מי שחייב בדוח", prep, where, "מיוצגים לפי הסדר הארכות."))
        rows.append(entry(parse(online), title + ", מקוון", "מי שחייב בדוח", prep, where, "מיוצגים לפי הסדר הארכות."))
    else:
        rows.append(unpublished(title, "מי שחייב בדוח", prep, where, "רשות המסים עוד לא פרסמה מועד. לא מניחים תאריך."))

    if zair:
        title = f"דוח מקוצר של עסק זעיר על {previous}"
        override = get("zair_report_override", previous)
        date = parse(override) if override else dt.date(year, 3, 31)
        rows.append(entry(date, title, "עסק זעיר", "מחזור, ניכוי במקור, הפקדות לפנסיה", "מערכת הדיווח המקוונת",
                          "מי שלא מגיש עובר להיות עסק רגיל."))

    for month in range(1, 13):
        paid_for = month - 1 or 12
        rows.append(entry(dt.date(year, month, 22), f"ביטוח לאומי, הוראת קבע בנק, עבור חודש {paid_for}", "עצמאי",
                          "כסף בחשבון", "חיוב אוטומטי", "בלי הוראת קבע: לפי דף התשלומים."))

    if status == "murshe":
        for month in (1, 3, 5, 7, 9, 11):
            rows.append(entry(dt.date(year, month, 15), "דוח מע\"מ דו-חודשי", "עוסק מורשה", "חשבוניות מכירה וקנייה",
                              "אתר רשות המסים", "גם דוח אפס. 19 לחודש בדיווח ותשלום מקוון."))
    if mkdamot != "none":
        months = range(1, 13) if mkdamot == "monthly" else (1, 3, 5, 7, 9, 11)
        for month in months:
            rows.append(entry(dt.date(year, month, 15), "מקדמות למס הכנסה", "מי שיש לו פנקס מקדמות", "פנקס המקדמות",
                              "אתר רשות המסים", "19 לחודש בתשלום מקוון."))

    rows.append(entry(dt.date(year, 12, 15), "תזכורת להפקדות, עם ההכנסה עד היום", "עצמאי", "הכנסה עד היום",
                      "לא מועד רשמי", "לא נוקבים בסכום להפקיד.", movable=False))
    if zair:
        rows.append(entry(dt.date(year, 12, 25), f"תיאום מס מקוון לעסק זעיר ל-{year}", "עסק זעיר", "מחזור צפוי",
                          "מערכת תיאומי המס"))
    rows.append(entry(dt.date(year, 12, 31), "הפקדות לפנסיה ולקרן השתלמות", "עצמאי", "בדיקה מול הקרן או רואה חשבון",
                      "הקרן", "הפקדה אחרי המועד נספרת לשנה הבאה.", movable=False))

    # מה שמוגש בשנה הבאה על השנה הזו, כדי שלא ייפול בין הלוחות
    if status == "patur":
        rows.append(entry(dt.date(year + 1, 1, 31), f"הצהרת עוסק פטור על מחזור {year}", "עוסק פטור",
                          "סך המחזור מהיומן", "למע\"מ, באתר רשות המסים"))
    paper, online = get("annual_report_paper", year), get("annual_report_online", year)
    if paper and online:
        rows.append(entry(parse(paper), f"דוח שנתי 1301 על שנת המס {year}, לא מקוון", "מי שחייב בדוח", prep, where))
        rows.append(entry(parse(online), f"דוח שנתי 1301 על שנת המס {year}, מקוון", "מי שחייב בדוח", prep, where))
    else:
        rows.append(unpublished(f"דוח שנתי 1301 על שנת המס {year}", "מי שחייב בדוח", prep, where,
                                "רשות המסים עוד לא פרסמה מועד. לא מניחים תאריך."))
    if zair:
        override = get("zair_report_override", year)
        date = parse(override) if override else dt.date(year + 1, 3, 31)
        rows.append(entry(date, f"דוח מקוצר של עסק זעיר על {year}", "עסק זעיר", "מחזור, ניכוי במקור, הפקדות לפנסיה",
                          "מערכת הדיווח המקוונת", "מי שלא מגיש עובר להיות עסק רגיל."))

    rows.sort(key=lambda row: (row["date"] is None, row["date"] or ""))
    return rows


def ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def to_ics(rows: list[dict], alarm_days: int = 3) -> str:
    """קובץ יומן שאפשר לייבא לכל יומן. ההתראות נשלחות מהיומן עצמו."""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//shekel//deadlines//HE", "CALSCALE:GREGORIAN"]
    for index, row in enumerate(rows):
        if not row["published"]:
            continue
        start = dt.date.fromisoformat(row["date"])
        details = f"מכינים: {row['prepare']}. איפה: {row['where']}. {row['note']}".strip()
        lines += [
            "BEGIN:VEVENT",
            f"UID:shekel-{row['date']}-{index}@shekel",
            f"DTSTAMP:{start:%Y%m%d}T000000Z",
            f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
            f"DTEND;VALUE=DATE:{start + dt.timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{ics_escape(row['title'])}",
            f"DESCRIPTION:{ics_escape(details)}",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{ics_escape(row['title'])}",
            f"TRIGGER:-P{alarm_days}D",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def render(year: int, rows: list[dict]) -> str:
    lines = [f"לוח מועדים לשנת {year}"]
    for row in rows:
        day = f" (יום {row['day']})" if row["day"] else ""
        lines.append(f"{row['display']}{day}: {row['title']}. למי: {row['who']}. מכינים: {row['prepare']}. איפה: {row['where']}.")
        if row["note"]:
            lines.append(f"    {row['note']}")
    lines.append("הסקריפט לא מכיר חגים ודחיות אד-הוק. בדקו באתר רשות המסים לפני כל מועד.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--status", choices=["patur", "murshe"], default="patur")
    parser.add_argument("--mkdamot", choices=["none", "monthly", "bimonthly"], default="none")
    parser.add_argument("--no-zair", action="store_true", help="לא עסק זעיר")
    parser.add_argument("--ics", help="כותב קובץ יומן עם התראות לנתיב הזה")
    parser.add_argument("--alarm-days", type=int, default=3, help="כמה ימים לפני המועד להתריע")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = build(args.year, args.status, args.mkdamot, not args.no_zair)
    if args.ics:
        Path(args.ics).write_text(to_ics(rows, args.alarm_days), encoding="utf-8", newline="")
        print(f"נכתב קובץ יומן: {args.ics}")
        return 0
    print(json.dumps(rows, ensure_ascii=False, indent=2) if args.json else render(args.year, rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
