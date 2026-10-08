"""Deterministic fixtures. No personal, customer, or employer data."""
import csv
import json
import random
from pathlib import Path

FIELDS = {
    "payments": ["payment_id", "amount_minor", "currency", "status", "occurred_at"],
    "refunds": ["refund_id", "payment_id", "amount_minor", "currency", "status", "occurred_at"],
    "settlements": ["settlement_id", "payment_id", "amount_minor", "currency", "occurred_at"],
}


def fee(amount: int) -> int:
    """Demo fee: 2.9% rounded half up in integer cents + 30 cents."""
    return (amount * 290 + 5000) // 10000 + 30


def generate(directory: Path, count: int = 1000, seed: int = 42) -> dict:
    if count < 20:
        raise ValueError("count must be at least 20")
    rng = random.Random(seed)
    data = {k: [] for k in FIELDS}
    for i in range(count):
        pid = f"P{i:06d}"
        amount = rng.randint(1000, 100000)
        currency = rng.choice(["USD", "CAD"])
        status = "failed" if i % 17 == 0 else "completed"
        payment = dict(payment_id=pid, amount_minor=amount, currency=currency,
                       status=status, occurred_at="2026-09-01T12:00:00+00:00")
        data["payments"].append(payment)
        refund = amount // 5 if status == "completed" and i % 7 == 0 else 0
        if refund:
            data["refunds"].append(dict(refund_id=f"R{i:06d}", payment_id=pid,
                amount_minor=refund, currency=currency, status="completed",
                occurred_at="2026-09-02T12:00:00+00:00"))
        if status == "completed":
            data["settlements"].append(dict(settlement_id=f"S{i:06d}", payment_id=pid,
                amount_minor=amount-refund-fee(amount), currency=currency,
                occurred_at="2026-09-03T12:00:00+00:00"))

    # Deliberate, documented control cases. Random data is otherwise clean.
    data["payments"].append(dict(data["payments"][1]))  # safe exact replay
    conflict = dict(data["payments"][2]); conflict["amount_minor"] += 100
    data["payments"].append(conflict)  # BOTH conflicting records quarantined
    data["settlements"] = [s for s in data["settlements"] if s["payment_id"] != "P000003"]
    next(s for s in data["settlements"] if s["payment_id"] == "P000004")["amount_minor"] += 125
    wrong = next(s for s in data["settlements"] if s["payment_id"] == "P000005")
    wrong["currency"] = "CAD" if wrong["currency"] == "USD" else "USD"
    data["payments"].append(dict(payment_id="BAD_AMOUNT", amount_minor=-50,
        currency="USD", status="completed", occurred_at="2026-09-01T12:00:00+00:00"))
    data["refunds"].append(dict(refund_id="ORPHAN_REFUND", payment_id="UNKNOWN",
        amount_minor=100, currency="USD", status="completed", occurred_at="2026-09-02T12:00:00+00:00"))
    p = data["payments"][6]
    data["refunds"].append(dict(refund_id="EXCESS_REFUND", payment_id=p["payment_id"],
        amount_minor=p["amount_minor"]+1, currency=p["currency"], status="completed",
        occurred_at="2026-09-02T12:00:00+00:00"))
    data["payments"].append(dict(payment_id="P_PENDING", amount_minor=10000,
        currency="USD", status="completed", occurred_at="2026-09-09T12:00:00+00:00"))
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in data.items():
        with (directory / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS[name])
            writer.writeheader(); writer.writerows(rows)
    manifest = {"synthetic": True, "seed": seed, "base_payments": count,
        "as_of": "2026-09-10T00:00:00+00:00", "rows": {k: len(v) for k,v in data.items()},
        "controls": {"P000001": "exact duplicate removed", "P000002": "conflicting payments quarantined",
        "P000003": "missing_settlement", "P000004": "amount_mismatch",
        "P000005": "currency_mismatch", "P000006": "excess_refund",
        "P_PENDING": "pending", "BAD_AMOUNT": "invalid amount quarantined",
        "ORPHAN_REFUND": "orphan refund quarantined"}}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    return manifest
