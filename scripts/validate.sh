#!/usr/bin/env bash
# בודק את הסקיל: frontmatter, שם, אורך, ושכל מספר ב-SKILL.md וב-references מופיע ב-evidence.json.
# הרצה: ./scripts/validate.sh
# יציאה 0 אם הכול תקין, 1 אם יש שגיאות.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

python3 - <<'PY'
import json
import re
import sys
from pathlib import Path

errors = []
skill = Path("SKILL.md").read_text(encoding="utf-8")

# 1. frontmatter
if not skill.startswith("---\n"):
    sys.exit("SKILL.md: חסר frontmatter")
_, frontmatter, body = skill.split("---\n", 2)
fields = dict(re.findall(r"^([a-z-]+): (.*)$", frontmatter, re.M))

# 2. שם
if fields.get("name") != "shekel":
    errors.append(f"name חייב להיות shekel, התקבל {fields.get('name')}")
if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields.get("name", "")):
    errors.append("name חייב להיות בקבב")
if fields.get("license") != "MIT":
    errors.append("license חייב להיות MIT")

# 3. תיאור
description = fields.get("description", "")
if not description:
    errors.append("חסר description")
if len(description) > 1024:
    errors.append(f"description ארוך מדי: {len(description)}")
if re.search(r"[<>]", description):
    errors.append("description מכיל סוגריים משולשים")
if "Not tax advice" not in description[:30]:
    errors.append('description חייב להתחיל ב-"Not tax advice"')
if not re.search(r"use when", description, re.I):
    errors.append('description חייב לכלול "Use when"')
triggers = ["עוסק פטור", "עוסק מורשה", "לפתוח עוסק", "עצמאי", "קבלה", "חשבונית", "הכנסה", "הוצאה מוכרת", "תקרה",
            "עסק זעיר", "ביטוח לאומי", "מקדמות", "דוח שנתי", "1301", "הצהרת עוסק פטור", "רואה חשבון"]
for word in triggers:
    if word not in description:
        errors.append(f"description: חסרה מילת הפעלה {word}")

# 4. אורך
words = len(body.split())
if words > 4000:
    errors.append(f"גוף SKILL.md {words} מילים, התקרה 4,000")

# 5. שורת הסיום וההבהרה
closing = "זו המחשה שעוזרת לכם להתארגן, לא ייעוץ מס. החישוב המחייב הוא של רשות המסים, ובמקרה מורכב דברו עם רואה חשבון או יועץ מס."
if closing not in body:
    errors.append("SKILL.md: חסרה שורת הסיום הקבועה")
if body.find("## הבהרה משפטית") > 200:
    errors.append("SKILL.md: ההבהרה המשפטית חייבת להיות בראש הקובץ")

# 6. קבצים חובה
required = ["README.md", "LICENSE", "metadata.json", "evidence.json", "CHANGELOG.md",
            "references/figures.md", "references/opening.md", "references/income.md", "references/expenses.md",
            "references/calendar.md", "references/sources.md",
            "templates/opening_checklist.md", "templates/receipt.md", "templates/deal_invoice.md",
            "templates/income_log.csv", "templates/expense_log.csv", "templates/year_summary.md",
            "templates/reclassification_letter.md",
            "scripts/threshold.py", "scripts/zair_compare.py", "scripts/deadlines.py", "scripts/expense_rule.py"]
for name in required:
    if not Path(name).is_file():
        errors.append(f"חסר קובץ: {name}")

scenarios = sorted(Path("tests/scenarios").glob("*.md"))
if len(scenarios) < 8:
    errors.append(f"נמצאו {len(scenarios)} תרחישים, צריך 8")

metadata = json.loads(Path("metadata.json").read_text(encoding="utf-8"))
if metadata.get("version") != "1.0.0":
    errors.append("metadata: הגרסה צריכה להיות 1.0.0")

# 7. כל מספר מופיע ב-evidence.json
evidence = json.loads(Path("evidence.json").read_text(encoding="utf-8"))
known = set()
for claim in evidence["claims"]:
    for key in ("claim_id", "claim", "source_url", "quote", "verified_at", "effective_year", "appears_in", "values"):
        if key not in claim:
            errors.append(f"evidence: בטענה {claim.get('claim_id')} חסר {key}")
    known.update(str(value) for value in claim.get("values", []))

PATTERNS = [
    re.compile(r"(?<![\d.])\d{1,2}\.\d{1,2}\.\d{4}(?![\d])"),              # תאריך מלא
    re.compile(r"(?<![\d.])\d{1,2}\.\d{1,2}(?![\d.%])"),                   # תאריך קצר
    re.compile(r"(?<![\d.,])\d+(?:\.\d+)?%"),                              # אחוז
    re.compile(r"(?<![\d.,])\d{1,3}(?:,\d{3})+(?![\d])"),                  # סכום עם פסיק
    re.compile(r"(?<![\d.,/-])\d{3,7}(?![\d,.%])"),                        # סכום או מספר טופס
    re.compile(r"(?<![\d.,])\d{1,2}(?=\s+(?:לחודש|בחודש|שעות|שנים|ימי|ימים|תלמידים))"),  # מספר עם יחידה
    re.compile(r"(?<=גיל )\d{1,3}"),
    re.compile(r"(?<=\*)\d{4}"),                                           # מוקד טלפוני
]
YEAR = re.compile(r"^20[2-3]\d$")


def tokens(text):
    text = re.sub(r"https?://\S+", " ", text)
    found = set()
    for pattern in PATTERNS:
        for match in pattern.findall(text):
            token = match.replace(",", "")
            if not YEAR.match(token):
                found.add(token)
    return found


checked = 0
files = [Path("SKILL.md")] + sorted(Path("references").glob("*.md"))
for path in files:
    text = body if path.name == "SKILL.md" else path.read_text(encoding="utf-8")
    for token in sorted(tokens(text)):
        checked += 1
        if token not in known:
            errors.append(f"{path}: {token} לא מופיע ב-evidence.json")

# 8. בגוף SKILL.md אין סכומים, חוץ מהתקרה לדוגמה
amounts = set(re.findall(r"\d{1,3}(?:,\d{3})+\s*₪", body))
extra = {a for a in amounts if not a.startswith("122,833")}
if extra:
    errors.append(f"SKILL.md: סכומים שצריכים לגור ב-figures.md: {sorted(extra)}")

# 9. כל קישור ב-sources.md מתועד
urls = set(re.findall(r"https?://[^\s|]+", Path("references/sources.md").read_text(encoding="utf-8")))
logged = {link["url"] for link in evidence.get("links", [])}
for url in sorted(urls - logged):
    errors.append(f"sources.md: {url} לא מתועד ב-evidence.json")

# 10. appears_in נכון
for claim in evidence["claims"]:
    for name in claim.get("appears_in", []):
        if not Path(name).exists():
            errors.append(f"evidence: {claim['claim_id']} מצביע על קובץ שלא קיים: {name}")

# 11. אין שאריות של השם הישן, ואין מילים אסורות
banned = {"jewish-accountant": "השם הישן", "Jewish Accountant": "השם הישן"}
for path in Path(".").rglob("*"):
    if not path.is_file() or path.parts[0] in {".git", "_sources"} or path.name in {"PLAN.md", "CHANGELOG.md", "validate.sh"}:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for word, why in banned.items():
        if word in text:
            errors.append(f"{path}: {why}: {word}")

print(f"גוף SKILL.md: {words} מילים")
print(f"נבדקו {checked} מספרים מול {len(evidence['claims'])} רשומות ב-evidence.json")
if errors:
    print("\nשגיאות:")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)
print("הכול תקין.")
PY

python3 -m unittest discover -s tests/unit 2>&1 | tail -1
