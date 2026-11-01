"""בדיקות יחידה לסקריפטים. הרצה: python3 -m unittest discover -s tests/unit"""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from deadlines import build, to_ics  # noqa: E402
from expense_rule import categories, deductible  # noqa: E402
from threshold import evaluate  # noqa: E402
from zair_compare import compare  # noqa: E402


class Threshold(unittest.TestCase):
    def test_july_95000_is_live_though_percent_looks_calm(self):
        r = evaluate(2026, 95000, 7, rate=14000)
        self.assertEqual(r["projection"], 165000)
        self.assertTrue(r["duty_live"])
        self.assertEqual(r["crossing_month"], 9)
        self.assertLess(r["ytd_pct"], 80)

    def test_december_110000_no_pipeline_needs_nothing(self):
        r = evaluate(2026, 110000, 12, no_more_work=True)
        self.assertEqual(r["projection"], 110000)
        self.assertFalse(r["duty_live"])

    def test_small_retainer_does_not_cover_a_month(self):
        r = evaluate(2026, 60000, 6, rate=10000, contracts=[(7, 1000)])
        self.assertEqual(r["projection"], 120000)

    def test_large_contract_is_not_double_counted(self):
        r = evaluate(2026, 60000, 6, rate=10000, contracts=[(7, 30000)])
        self.assertEqual(r["projection"], 140000)

    def test_future_one_off_is_added_on_top(self):
        r = evaluate(2026, 60000, 6, rate=10000, one_offs=[5000])
        self.assertEqual(r["projection"], 125000)

    def test_past_one_off_leaves_the_run_rate(self):
        r = evaluate(2026, 80000, 4, past_one_offs=40000)
        self.assertEqual(r["run_rate"], 10000)
        self.assertEqual(r["projection"], 160000)

    def test_mid_year_opening_uses_active_months(self):
        r = evaluate(2026, 40000, 6, open_month=3)
        self.assertEqual(r["run_rate"], 10000)
        self.assertTrue(r["partial_year"])

    def test_exactly_on_the_ceiling_is_not_over(self):
        r = evaluate(2026, 122833, 12, no_more_work=True)
        self.assertFalse(r["duty_live"])

    def test_one_shekel_over_is_over(self):
        self.assertTrue(evaluate(2026, 122834, 12, no_more_work=True)["duty_live"])

    def test_unknown_year_refuses(self):
        with self.assertRaises(LookupError):
            evaluate(2031, 1000, 3)

    def test_contract_in_a_past_month_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(2026, 50000, 6, contracts=[(3, 1000)])


class Zair(unittest.TestCase):
    def test_brief_case(self):
        r = compare(2026, 90000, 15000)
        self.assertEqual(r["normative"], 27000)
        self.assertEqual(r["difference"], 12000)
        self.assertEqual(r["better"], "zair")

    def test_high_expenses_prefer_regular(self):
        self.assertEqual(compare(2026, 90000, 40000)["better"], "regular")

    def test_over_ceiling_is_flagged(self):
        self.assertTrue(compare(2026, 130000, 1000)["over_ceiling"])


class Expenses(unittest.TestCase):
    def test_table_loads(self):
        self.assertIn("mobile", categories())
        self.assertEqual(len(categories()), 17)

    def test_small_phone_bill_is_half(self):
        self.assertEqual(deductible("mobile", 150, 2026)["deductible"], 75)

    def test_large_phone_bill_hits_the_shekel_floor(self):
        self.assertEqual(deductible("mobile", 300, 2026)["deductible"], 185)

    def test_annual_phone(self):
        self.assertEqual(deductible("mobile", 1800, 2026, annual=True)["deductible"], 900)

    def test_home_needs_a_share(self):
        with self.assertRaises(ValueError):
            deductible("home", 600, 2026)
        self.assertEqual(deductible("home", 600, 2026, share=0.15)["deductible"], 90)

    def test_hosting_is_zero(self):
        self.assertEqual(deductible("hosting", 350, 2026)["deductible"], 0)

    def test_computer_is_depreciated(self):
        r = deductible("computer", 8500, 2026)
        self.assertEqual(r["deductible"], 2805)
        self.assertTrue(r["per_year"])

    def test_gift_is_capped(self):
        self.assertEqual(deductible("gift", 500, 2026)["deductible"], 240)

    def test_unknown_category(self):
        with self.assertRaises(KeyError):
            deductible("nonsense", 1, 2026)


class Calendar(unittest.TestCase):
    def rows(self, year, **kwargs):
        return build(year, **kwargs)

    def find(self, rows, text):
        return [row for row in rows if text in row["title"]]

    def test_2026_declaration_uses_the_one_off_date(self):
        row = self.find(self.rows(2026), "הצהרת עוסק פטור")[0]
        self.assertEqual(row["date"], "2026-04-30")

    def test_2027_declaration_is_31_1(self):
        row = self.find(self.rows(2027), "הצהרת עוסק פטור")[0]
        self.assertEqual(row["date"], "2027-01-31")

    def test_saturday_moves_to_sunday(self):
        rows = self.rows(2026)
        august = self.find(rows, "עבור חודש 7")[0]
        self.assertEqual(august["date"], "2026-08-23")
        self.assertEqual(dt.date.fromisoformat(august["date"]).weekday(), 6)

    def test_december_25_2027_moves(self):
        row = self.find(self.rows(2027), "תיאום מס")[0]
        self.assertEqual(row["date"], "2027-12-26")

    def test_december_31_never_moves_to_january(self):
        for year in range(2026, 2040):
            row = self.find(self.rows(year), "הפקדות לפנסיה")[0]
            self.assertEqual(row["date"], f"{year}-12-31")

    def test_annual_report_2025_dates(self):
        rows = self.find(self.rows(2026), "דוח שנתי 1301 על שנת המס 2025")
        self.assertEqual({row["date"] for row in rows}, {"2026-05-29", "2026-06-30"})

    def test_2026_report_is_unpublished_and_next_declaration_shows(self):
        rows = self.rows(2026)
        self.assertEqual(self.find(rows, "על שנת המס 2026")[0]["display"], "טרם פורסם")
        self.assertEqual(self.find(rows, "הצהרת עוסק פטור על מחזור 2026")[0]["date"], "2027-01-31")

    def test_ics_has_alarms_and_skips_unpublished(self):
        rows = self.rows(2026)
        text = to_ics(rows)
        published = sum(1 for row in rows if row["published"])
        self.assertEqual(text.count("BEGIN:VEVENT"), published)
        self.assertEqual(text.count("TRIGGER:-P3D"), published)
        self.assertLess(published, len(rows))

    def test_unknown_annual_report_is_unpublished(self):
        row = self.find(self.rows(2027), "דוח שנתי")[0]
        self.assertFalse(row["published"])
        self.assertEqual(row["display"], "טרם פורסם")

    def test_zair_report_dates(self):
        self.assertEqual(self.find(self.rows(2026), "דוח מקוצר")[0]["date"], "2026-08-31")
        self.assertEqual(self.find(self.rows(2027), "דוח מקוצר")[0]["date"], "2027-03-31")

    def test_twelve_bituach_rows(self):
        self.assertEqual(len(self.find(self.rows(2026), "ביטוח לאומי")), 12)

    def test_murshe_gets_vat_and_no_declaration(self):
        rows = self.rows(2026, status="murshe")
        self.assertEqual(len(self.find(rows, "מע\"מ")), 6)
        self.assertEqual(self.find(rows, "הצהרת עוסק פטור"), [])


if __name__ == "__main__":
    unittest.main()
