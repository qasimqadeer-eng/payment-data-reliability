"""Transactional snapshot loader and shared SQL transformations."""
import csv
from decimal import Decimal
import hashlib
import json
import os
import re
import sqlite3
from collections import Counter
from pathlib import Path
from .quality import timestamp, validate

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = {
    "clean_payments": "payment_id TEXT PRIMARY KEY, amount_minor BIGINT, currency TEXT, status TEXT, occurred_at TEXT, fee_minor BIGINT, matured INTEGER",
    "clean_refunds": "refund_id TEXT PRIMARY KEY, payment_id TEXT, amount_minor BIGINT, currency TEXT, status TEXT, occurred_at TEXT",
    "clean_settlements": "settlement_id TEXT PRIMARY KEY, payment_id TEXT, amount_minor BIGINT, currency TEXT, occurred_at TEXT",
    "quality_issues": "source TEXT, row_number INTEGER, record_id TEXT, rule TEXT, disposition TEXT, raw_json TEXT",
    "raw_records": "source TEXT, row_number INTEGER, payload TEXT",
    "blocked_payments": "payment_id TEXT PRIMARY KEY",
}
MODEL_NAMES = ["payment_reconciliation", "daily_metrics"]


def render_sql(path: Path) -> str:
    sql = path.read_text()
    sql = re.sub(r"\{\{\s*source\('pipeline', '([a-z_]+)'\)\s*\}\}", r"\1", sql)
    sql = re.sub(r"\{\{\s*ref\('([a-z_]+)'\)\s*\}\}", r"\1", sql)
    if "{{" in sql:
        raise ValueError("Unsupported template in local SQL renderer")
    return sql


def connect(backend, output):
    if backend == "sqlite":
        return sqlite3.connect(output / "warehouse.sqlite")
    if backend != "postgres":
        raise ValueError("Unsupported backend")
    import psycopg
    return psycopg.connect(host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"), dbname=os.environ.get("PGDATABASE", "payments"),
        user=os.environ.get("PGUSER", "payments"), password=os.environ["PGPASSWORD"])


def read_rows(cursor, table):
    # Only callers' constant, allowlisted table names are accepted.
    if table not in SCHEMAS and table not in MODEL_NAMES:
        raise ValueError("Unknown table")
    cursor.execute(f"SELECT * FROM {table}")
    fields = [col[0] for col in cursor.description]
    return fields, [dict(zip(fields, (int(value) if isinstance(value, Decimal) and value == value.to_integral_value() else value for value in row))) for row in cursor.fetchall()]


def run(directory: Path, output: Path, as_of: str, backend="sqlite", grace_days=2):
    clean, issues, raw = validate(directory, timestamp(as_of), grace_days)
    output.mkdir(parents=True, exist_ok=True)
    conn = connect(backend, output)
    data = {f"clean_{k}": v for k,v in clean.items()}
    data["quality_issues"] = issues
    blocked = set()
    for issue in issues:
        if issue["disposition"] == "quarantined":
            pid = json.loads(issue["raw_json"]).get("payment_id")
            if pid:
                blocked.add(pid)
    data["blocked_payments"] = [{"payment_id": pid} for pid in sorted(blocked)]
    data["raw_records"] = [dict(source=k, row_number=i, payload=json.dumps(r))
                           for k,rows in raw.items() for i,r in enumerate(rows, 2)]
    try:
        cur = conn.cursor()
        if backend == "postgres":
            # Isolate this application from other public-schema objects.
            cur.execute("CREATE SCHEMA IF NOT EXISTS reliability")
            cur.execute("SET search_path TO reliability")
        for name, schema in SCHEMAS.items():
            cur.execute(f"CREATE TABLE IF NOT EXISTS {name} ({schema})")
            cur.execute(f"DELETE FROM {name}")
            fields = [part.strip().split()[0] for part in schema.split(",")]
            placeholder = "%s" if backend == "postgres" else "?"
            values = ",".join([placeholder]*len(fields))
            if data[name]:
                cur.executemany(f"INSERT INTO {name} ({','.join(fields)}) VALUES ({values})",
                    [tuple(row[f] for f in fields) for row in data[name]])
        for name in reversed(MODEL_NAMES):
            cur.execute(f"DROP VIEW IF EXISTS {name}")
        for name in MODEL_NAMES:
            cur.execute(f"CREATE VIEW {name} AS " + render_sql(ROOT / "dbt/models" / f"{name}.sql"))
        conn.commit()
        exports = {}
        for name in ["quality_issues", *MODEL_NAMES]:
            fields, rows = read_rows(cur, name)
            rows.sort(key=lambda r: json.dumps(r, sort_keys=True))
            exports[name] = rows
            with (output / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader(); writer.writerows(rows)
    finally:
        conn.close()
    summary = {"synthetic": True, "as_of": timestamp(as_of).isoformat(), "backend": backend,
        "grace_days": grace_days, "fee_policy": "2.9% rounded half up + 30 minor units; nonrefundable",
        "raw_rows": {k: len(v) for k,v in raw.items()}, "clean_rows": {k: len(v) for k,v in clean.items()},
        "quality_counts": dict(Counter(i["rule"] for i in issues)),
        "status_counts": dict(Counter(r["reconciliation_status"] for r in exports["payment_reconciliation"])),
        "input_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.glob("*.csv"))}}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n")
    from .report import write_report
    write_report(output, summary, exports)
    return summary
