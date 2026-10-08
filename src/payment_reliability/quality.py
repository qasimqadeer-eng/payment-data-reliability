"""Validate before loading; preserve rejected rows and deterministic decisions."""
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from .generate import FIELDS, fee


def timestamp(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def validate(directory: Path, as_of: datetime, grace_days: int = 2):
    if as_of.tzinfo is None or grace_days < 0:
        raise ValueError("timezone-aware as_of and nonnegative grace_days required")
    clean, issues, raw = {}, [], {}

    def issue(name, row_number, row, rule, disposition="quarantined"):
        issues.append(dict(source=name, row_number=row_number, record_id=row.get(FIELDS[name][0], ""),
            rule=rule, disposition=disposition, raw_json=json.dumps(row)))

    for name, fields in FIELDS.items():
        with (directory / f"{name}.csv").open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != fields:
                raise ValueError(f"{name}: CSV columns must equal {fields}")
            raw[name] = list(reader)
        grouped = defaultdict(list)
        for n, row in enumerate(raw[name], 2):
            grouped[row.get(fields[0], "")].append((n, row))
        accepted = []
        for identity, group in grouped.items():
            # Never silently select a winner among conflicting versions.
            if len({json.dumps(r) for _,r in group}) > 1 and identity:
                for n, row in group:
                    issue(name, n, row, "conflicting_duplicate")
                continue
            n, row = group[0]
            errors = []
            if any(row.get(f) in (None, "") for f in fields) or None in row:
                errors.append("missing_or_extra_field")
            try:
                amount = int(row["amount_minor"])
                lower = -(10**12) if name == "settlements" else 1
                if not lower <= amount <= 10**12:
                    raise ValueError()
            except (ValueError, TypeError):
                errors.append("invalid_amount")
            if row.get("currency") not in {"USD", "CAD"}:
                errors.append("unsupported_currency")
            if name != "settlements" and row.get("status") not in {"completed", "failed"}:
                errors.append("invalid_status")
            try:
                occurred = timestamp(row["occurred_at"])
                if occurred > as_of:
                    errors.append("future_timestamp")
            except (ValueError, TypeError, AttributeError):
                errors.append("invalid_timestamp")
            if errors:
                for rn, rr in group:
                    issue(name, rn, rr, ";".join(errors))
                continue
            for rn, rr in group[1:]:
                issue(name, rn, rr, "exact_duplicate", "deduplicated")
            item = dict(row, amount_minor=amount, occurred_at=occurred.isoformat())
            if name == "payments":
                item["fee_minor"] = fee(amount) if row["status"] == "completed" else 0
                item["matured"] = int((as_of-occurred).total_seconds() >= grace_days*86400)
            accepted.append((n, item))
        clean[name] = accepted
    parents = {p["payment_id"]: p for _,p in clean["payments"]}
    refunds = []
    for n, row in clean["refunds"]:
        parent = parents.get(row["payment_id"])
        rule = None
        if not parent:
            rule = "orphan_refund"
        elif row["currency"] != parent["currency"]:
            rule = "refund_currency_mismatch"
        elif timestamp(row["occurred_at"]) < timestamp(parent["occurred_at"]):
            rule = "refund_before_payment"
        elif row["status"] == "completed" and parent["status"] != "completed":
            rule = "refund_on_failed_payment"
        if rule:
            issue("refunds", n, raw["refunds"][n-2], rule)
        else:
            refunds.append((n, row))
    clean["refunds"] = refunds
    # Settlement orphans and currency mismatches remain visible in reconciliation.
    return {k: [r for _,r in v] for k,v in clean.items()}, issues, raw
