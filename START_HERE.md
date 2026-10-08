# Start here

1. Extract `Payment_Data_Reliability_GitHub_Project.zip`.
2. Open `payment-data-reliability/docs/demo/dashboard.html` for an immediate preview.
3. Open the `payment-data-reliability` folder in VS Code.
4. Follow the README's Python quick start to generate fresh data and run tests.
5. Review `docs/DATA_CONTRACT.md` and the code. Qasim should be able to explain each design decision and accurately describe the AI assistance used.
6. When ready, create an empty GitHub repository named `payment-data-reliability`. Public makes the code viewable to others; choose visibility deliberately.
7. Upload the extracted repository contents, including `.github/workflows/ci.yml`, or use Git below. Upload the files, not just this ZIP.
8. Check the repository's Actions tab. Confirm all jobs pass before claiming the workflow is verified on GitHub.

Suggested repository description:

> Synthetic payment data pipeline with auditable validation, settlement reconciliation, PostgreSQL/dbt models, an offline dashboard, and automated tests.

Suggested topics: `data-engineering`, `python`, `postgresql`, `dbt`, `data-quality`, `reconciliation`, `docker`.

From a terminal inside the extracted folder (replace YOUR-USERNAME):

```bash
git init
git add .
git status
git commit -m "Add synthetic payment data reliability pipeline"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/payment-data-reliability.git
git push -u origin main
```

Before `git commit`, inspect `git status` and confirm no secrets or personal/company data appear. The generated source data is synthetic, but runtime outputs are ignored by default. The curated `docs/demo` report is intentionally included.

Recommended next substantive contribution: implement an ingestion-watermark freshness rule or extend tests for a processor-specific fee contract, using public documentation and synthetic data. Record real changes in Git rather than inventing development history or adoption metrics.
