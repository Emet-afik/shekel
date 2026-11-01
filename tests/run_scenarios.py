#!/usr/bin/env python3
"""מריץ את התרחישים דרך claude -p, עם הסקיל טעון בתיקייה זמנית, ובודק את התשובות.

הרצה: python3 tests/run_scenarios.py [--only 04] [--out DIR] [--jobs 4]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOSING = "זו המחשה שעוזרת לכם להתארגן, לא ייעוץ מס."
TOOLS = "Read Glob Grep Write Edit Bash(python3:*) Bash(cp:*) Bash(ls:*) Bash(cat:*) Bash(pwd) Bash(mkdir:*)"


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    prompt = text.split("## קלט", 1)[1].split("## מצופה", 1)[0].strip()
    must = re.findall(r"^must: (.+)$", text, re.M)
    must_not = re.findall(r"^must_not: (.+)$", text, re.M)
    files = re.findall(r"^must_file: (.+)$", text, re.M)
    return {"name": path.stem, "prompt": prompt, "must": must, "must_not": must_not, "files": files}


def run(case: dict, out: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="shekel-") as tmp:
        skills = Path(tmp) / ".claude" / "skills"
        skills.mkdir(parents=True)
        # העתקה ולא קישור, כמו התקנה אמיתית
        skill = skills / "shekel"
        shutil.copytree(ROOT, skill, ignore=shutil.ignore_patterns(".git", "_sources", ".results", "__pycache__"))
        # בלי משתני הסשן שמריץ את הבדיקה, כדי שהתיקייה הזמנית תהיה באמת תיקיית העבודה
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "VSCODE")) and k not in ("PWD", "OLDPWD")}
        env.update({"PWD": tmp, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
        done = subprocess.run(
            ["claude", "-p", case["prompt"].replace("{ROOT}", str(skill)), "--allowedTools", *TOOLS.split(" ")],
            cwd=tmp, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=540,
        )
        missing = [name for name in case["files"] if not (Path(tmp) / name).is_file()]
        leaked = [name for name in ("income_log.csv", "expense_log.csv") if (ROOT / name).exists()]
        written = {name: (Path(tmp) / name).read_text(encoding="utf-8") for name in case["files"] if name not in missing}
    answer = done.stdout.strip()
    (out / f"{case['name']}.txt").write_text(answer + ("\n\nSTDERR:\n" + done.stderr if done.stderr else ""), encoding="utf-8")
    failures = [f"חסר: {p}" for p in case["must"] if not re.search(p, answer)]
    failures += [f"אסור: {p}" for p in case["must_not"] if re.search(p, answer)]
    failures += [f"לא נוצר קובץ: {name}" for name in missing]
    failures += [f"נכתב לתיקיית הסקיל: {name}" for name in leaked]
    for name, content in written.items():
        (out / f"{case['name']}.{name}").write_text(content, encoding="utf-8")
    if CLOSING not in answer:
        failures.append("חסרה שורת ההסתייגות")
    return {"name": case["name"], "passed": not failures, "failures": failures, "chars": len(answer)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="רק תרחישים ששמם מתחיל בזה, מופרד בפסיקים")
    parser.add_argument("--out", default=str(ROOT / "tests" / ".results"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cases = [parse(p) for p in sorted((ROOT / "tests" / "scenarios").glob("*.md"))]
    if args.only:
        wanted = tuple(args.only.split(","))
        cases = [c for c in cases if c["name"].startswith(wanted)]
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda c: run(c, out), cases))
    for r in results:
        print(("PASS" if r["passed"] else "FAIL"), r["name"], r["chars"], "; ".join(r["failures"]))
    (out / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
