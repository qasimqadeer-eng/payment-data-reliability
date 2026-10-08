# Verification record

Prepared October 7, 2026. This record describes execution during project creation, not GitHub-hosted CI results or production certification.

## Executed successfully

- Python 3.12 editable installation with PostgreSQL/dbt optional dependencies.
- Standard-library unittest suite: all 19 passed, including PostgreSQL/SQLite CSV parity through the normal psycopg TCP connection. The PostgreSQL engine used here was PGlite (PostgreSQL compiled to WebAssembly), not a native PostgreSQL 16 server.
- Full synthetic generation and SQLite pipeline with default seed 42 and 1,000 base payment records.
- Strict mode correctly returned exit code 2 for intentionally injected anomalies.
- dbt-core 1.12.5 / dbt-postgres 1.9.0: built both view models against PGlite and passed all 13 data tests, including exact agreement with the loader reconciliation view. dbt ran with one thread for the embedded engine.
- Compose, dbt, and GitHub workflow YAML files parsed.
- The normal PostgreSQL pipeline processed the full 1,000-payment synthetic dataset successfully using PGlite.
- Dashboard opened in Chromium: desktop (1440 px) and mobile (390 px) had no document-level horizontal overflow; the exception toggle worked. Both screenshots were visually inspected. Wide tables scroll inside their own containers.

## Demo results

Input: 1,004 payment rows, 136 refund rows, and 940 settlement rows.

Accepted: 1,000 payment rows, 135 refund rows, and 940 settlement rows.

Reconciliation: 936 matched, 59 not applicable, 1 pending, and 5 exceptions (one each: orphan settlement, currency mismatch, excess refund, missing settlement, and amount mismatch). These are intentionally generated scenarios, not business impact metrics.

Quality audit: 5 row dispositions — 1 exact replay removed, 2 conflicting payment versions quarantined, 1 invalid amount quarantined, and 1 orphan refund quarantined.

## Not executed here

- Docker image build and Compose startup; Docker was unavailable.
- Native PostgreSQL 16 service-container execution. PGlite verifies PostgreSQL SQL and client integration but does not replace native-server/container validation. A dedicated GitHub Actions job covers the native server.
- GitHub-hosted CI; the repository has not been published from this environment.
- Docker smoke execution: the new CI job is configured to build the image, run the container pipeline and dbt, and request the dashboard over HTTP. It has not yet run on GitHub.

## Reproduce

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m payment_reliability.cli generate
python -m payment_reliability.cli run
```

For full PostgreSQL/dbt verification, run `docker compose up --build` or follow the README's local PostgreSQL instructions and enable `TEST_POSTGRES=1` for the Python suite. GitHub Actions runs that integration test automatically.

## Embedded-engine verification details

The temporary verification harness used the official `@electric-sql/pglite-socket` TCP server bound to loopback and launched Python/dbt as child processes. It used only synthetic inputs and a disposable in-memory database. It is an extra verification environment, not a new production dependency. See https://pglite.dev/docs/pglite-socket for the server interface.
