import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from payment_reliability.generate import generate, fee, FIELDS
from payment_reliability.pipeline import run
from payment_reliability.quality import validate, timestamp

AS_OF = "2026-09-10T00:00:00+00:00"


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.out = self.root / "out"
        generate(self.data, 100)

    def rows(self, name):
        with (self.data / f"{name}.csv").open(newline="") as f:
            return list(csv.DictReader(f))

    def save(self, name, rows):
        with (self.data / f"{name}.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS[name])
            writer.writeheader(); writer.writerows(rows)

    def result(self):
        summary = run(self.data, self.out, AS_OF)
        with (self.out / "payment_reconciliation.csv").open(newline="") as f:
            records = {r["payment_id"]:r for r in csv.DictReader(f)}
        return summary, records

    def test_known_anomalies(self):
        summary, records = self.result()
        expected = {"P000002":"orphan_settlement", "P000003":"missing_settlement",
            "P000004":"amount_mismatch", "P000005":"currency_mismatch",
            "P000006":"excess_refund", "P_PENDING":"pending", "P000001":"matched"}
        for pid, status in expected.items():
            self.assertEqual(records[pid]["reconciliation_status"], status)
        self.assertEqual(int(records["P000004"]["variance_minor"]), 125)
        self.assertEqual(summary["quality_counts"]["conflicting_duplicate"], 2)
        self.assertNotIn("BAD_AMOUNT", records)

    def test_exact_duplicate_does_not_double_money(self):
        _, records = self.result()
        p = self.rows("payments")[1]
        self.assertEqual(int(records[p["payment_id"]]["gross_minor"]), int(p["amount_minor"]))

    def test_replay_is_idempotent(self):
        first = self.result()
        summary_bytes = (self.out / "summary.json").read_bytes()
        self.assertEqual(first, self.result())
        self.assertEqual(summary_bytes, (self.out / "summary.json").read_bytes())

    def test_generator_is_reproducible(self):
        other = self.root / "other"
        generate(other, 100)
        for p in self.data.glob("*.csv"):
            self.assertEqual(p.read_bytes(), (other / p.name).read_bytes())

    def test_conflicting_duplicates_quarantine_all(self):
        clean, issues, _ = validate(self.data, timestamp(AS_OF))
        self.assertNotIn("P000002", {r["payment_id"] for r in clean["payments"]})
        self.assertEqual(sum(i["rule"] == "conflicting_duplicate" for i in issues), 2)

    def test_refund_relationship_and_currency(self):
        rows = self.rows("refunds")
        rows[0]["currency"] = "CAD" if rows[0]["currency"] == "USD" else "USD"
        self.save("refunds", rows)
        _, issues, _ = validate(self.data, timestamp(AS_OF))
        rules = {i["rule"] for i in issues}
        self.assertIn("orphan_refund", rules)
        self.assertIn("refund_currency_mismatch", rules)

    def test_partial_refund_is_net_of_nonrefundable_fee(self):
        _, records = self.result()
        r = records["P000007"]
        expected = int(r["gross_minor"]) - int(r["refund_minor"]) - fee(int(r["gross_minor"]))
        self.assertEqual(int(r["settled_minor"]), expected)
        self.assertEqual(r["reconciliation_status"], "matched")

    def test_bad_refund_blocks_false_match(self):
        rows = self.rows("refunds")
        p = self.rows("payments")[1]
        rows.append(dict(refund_id="BAD_REFUND", payment_id=p["payment_id"],
            amount_minor="-100", currency=p["currency"], status="completed",
            occurred_at="2026-09-02T12:00:00+00:00"))
        self.save("refunds", rows)
        self.assertEqual(self.result()[1][p["payment_id"]]["reconciliation_status"], "data_quality_blocked")

    def test_full_refund_supports_negative_net_settlement(self):
        p = self.rows("payments")[1]
        rows = self.rows("refunds")
        rows.append(dict(refund_id="FULL", payment_id=p["payment_id"], amount_minor=p["amount_minor"],
            currency=p["currency"], status="completed", occurred_at="2026-09-02T12:00:00+00:00"))
        self.save("refunds", rows)
        settlements = self.rows("settlements")
        next(r for r in settlements if r["payment_id"] == p["payment_id"])["amount_minor"] = str(-fee(int(p["amount_minor"])))
        self.save("settlements", settlements)
        self.assertEqual(self.result()[1][p["payment_id"]]["reconciliation_status"], "matched")

    def test_multiple_settlements_sum_before_join(self):
        rows = self.rows("settlements")
        r = next(r for r in rows if r["payment_id"] == "P000001")
        amount = int(r["amount_minor"])
        r["amount_minor"] = str(amount//2)
        rows.append(dict(r, settlement_id="S_SPLIT", amount_minor=str(amount-amount//2)))
        self.save("settlements", rows)
        _, records = self.result()
        self.assertEqual(records["P000001"]["reconciliation_status"], "matched")
        self.assertEqual(int(records["P000001"]["settlement_count"]), 2)

    def test_naive_and_future_times_quarantined(self):
        rows = self.rows("payments")
        rows[8]["occurred_at"] = "2026-09-01T12:00:00"
        rows[9]["occurred_at"] = "2027-01-01T00:00:00+00:00"
        self.save("payments", rows)
        _, issues, _ = validate(self.data, timestamp(AS_OF))
        self.assertIn("invalid_timestamp", {i["rule"] for i in issues})
        self.assertIn("future_timestamp", {i["rule"] for i in issues})

    def test_failed_payment_with_settlement(self):
        payments = self.rows("payments")
        p = payments[0]
        rows = self.rows("settlements")
        rows.append(dict(settlement_id="FAILED_SETTLED",payment_id=p["payment_id"],
            amount_minor="100",currency=p["currency"],occurred_at="2026-09-03T12:00:00+00:00"))
        self.save("settlements", rows)
        self.assertEqual(self.result()[1][p["payment_id"]]["reconciliation_status"], "unexpected_settlement")

    def test_grace_boundary(self):
        summary = run(self.data,self.out,"2026-09-11T12:00:00+00:00")
        self.assertEqual(summary["status_counts"].get("pending",0), 0)

    def test_money_rounding(self):
        self.assertEqual(fee(10000),320)
        self.assertEqual(fee(1500),74)  # 43.5 rounds UP, not bankers' rounding

    def test_wrong_columns_fail_before_loading(self):
        (self.data/"payments.csv").write_text("id,amount\na,1\n")
        with self.assertRaisesRegex(ValueError,"CSV columns"):
            self.result()

    def test_extra_csv_cells_are_quarantined(self):
        path = self.data / 'refunds.csv'
        with path.open('a') as f:
            f.write('EXTRA,P000001,100,USD,completed,2026-09-02T00:00:00+00:00,unwanted\n')
        summary, records = self.result()
        self.assertIn('missing_or_extra_field', summary['quality_counts'])
        self.assertEqual(records['P000001']['reconciliation_status'], 'data_quality_blocked')

    def test_currency_aggregates_remain_separate(self):
        self.result()
        with (self.out/"daily_metrics.csv").open(newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual({r["currency"] for r in rows}, {"USD","CAD"})
        self.assertNotIn("currency_mismatch", {r["reconciliation_status"] for r in rows})

    def test_html_escapes_source_values(self):
        rows = self.rows("payments")
        rows[-1]["payment_id"] = "<script>alert(1)</script>"
        rows[-1]["amount_minor"] = "-1"
        self.save("payments", rows)
        self.result()
        page = (self.out/"dashboard.html").read_text()
        self.assertNotIn("<script>alert(1)</script>",page)
        self.assertIn("&lt;script&gt;",page)

    @unittest.skipUnless(os.environ.get("TEST_POSTGRES") == "1", "Postgres integration requires a service")
    def test_postgres_sqlite_parity(self):
        local = run(self.data,self.out,AS_OF)
        pgout = self.root/"postgres"
        pg = run(self.data,pgout,AS_OF,backend="postgres")
        self.assertEqual(local["status_counts"],pg["status_counts"])
        for name in ["payment_reconciliation.csv","daily_metrics.csv","quality_issues.csv"]:
            self.assertEqual((self.out/name).read_bytes(),(pgout/name).read_bytes())


if __name__ == "__main__":
    unittest.main()
