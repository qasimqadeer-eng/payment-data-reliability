"""Self-contained, offline dashboard; data is escaped before HTML embedding."""
import html
from pathlib import Path


def write_report(output: Path, summary: dict, exports: dict):
    statuses = summary["status_counts"]
    total = sum(statuses.values())
    excluded = {"matched", "pending", "not_applicable"}
    exceptions = [r for r in exports["payment_reconciliation"] if r["reconciliation_status"] not in excluded]
    def esc(value):
        return html.escape(str(value if value is not None else "Unknown"))
    def table(headers, rows):
        return "<div class='scroll'><table><thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in headers) + "</tr></thead><tbody>" + "".join("<tr>"+"".join(f"<td>{esc(c)}</td>" for c in row)+"</tr>" for row in rows)+"</tbody></table></div>"
    bars = "".join(f"<div class='barrow'><span>{esc(k.replace('_',' '))}</span><div class='track'><div class='fill' style='width:{100*v/max(total,1):.2f}%'></div></div><b>{v:,}</b></div>" for k,v in sorted(statuses.items(), key=lambda kv:-kv[1]))
    exception_table = table(["Payment", "Status", "Currency", "Expected cents", "Settled cents", "Variance cents"],
        [[r["payment_id"],r["reconciliation_status"],r["currency"],r["expected_net_minor"],r["settled_minor"],r["variance_minor"]] for r in exceptions])
    quality_table = table(["Source", "CSV row", "Record", "Rule", "Disposition"],
        [[r[k] for k in ["source","row_number","record_id","rule","disposition"]] for r in exports["quality_issues"]])
    cards = "".join(f"<article><p>{label}</p><strong>{value:,}</strong><small>{desc}</small></article>" for label,value,desc in [
        ("Payment keys",total,"Union of valid payments and settlement keys"),
        ("Reconciliation exceptions",len(exceptions),"Requires investigation; not a loss estimate"),
        ("Quality dispositions",len(exports["quality_issues"]),"Quarantined or deduplicated source rows"),
        ("Matched",statuses.get("matched",0),"Matured, valid, reconciled payments")])
    page = """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Payment Reliability | Synthetic Demo</title><style>
    :root{color-scheme:light;font-family:system-ui,sans-serif;color:#182a40;background:#f2f5f9}*{box-sizing:border-box}body{margin:0}main{max-width:1160px;margin:auto;padding:40px 24px}header{background:#102b40;color:white;padding:36px;border-radius:16px}h1{font-size:clamp(26px,4vw,38px);margin:12px 0}h2{font-size:21px;margin-top:0}.eyebrow{text-transform:uppercase;letter-spacing:2px;font-size:12px;color:#88dfcf}.sub{color:#c9d8e6;line-height:1.6}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}article,section{background:white;border:1px solid #dce4ed;border-radius:12px;padding:24px}article p{font-size:13px;margin:0 0 14px}strong{font-size:34px;display:block}small{display:block;color:#65768b;line-height:1.5;margin-top:10px}section{margin-top:20px}.barrow{display:grid;grid-template-columns:210px 1fr 55px;gap:12px;align-items:center;margin:12px 0;font-size:13px}.track{background:#edf2f7;border-radius:5px;overflow:hidden}.fill{background:#168a7d;height:14px;min-width:2px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:12px;border-bottom:1px solid #e7edf2;white-space:nowrap}th{color:#496279;background:#f5f8fc}.note{font-size:13px;line-height:1.7;color:#52647a}button{cursor:pointer;background:#102b40;color:white;border:0;padding:10px 16px;border-radius:7px;margin-bottom:14px}footer{padding:24px 0;color:#65768b;font-size:12px}@media(max-width:760px){.cards{grid-template-columns:1fr 1fr}.barrow{grid-template-columns:145px 1fr 35px}main{padding:20px 12px}header,section,article{padding:18px}}@media(max-width:420px){.cards{grid-template-columns:1fr}}
    </style></head><body><main><header><div class='eyebrow'>Engineering portfolio / synthetic data only</div><h1>Payment Data Reliability</h1><div class='sub'>From payment events to an auditable settlement exception queue.<br>ASOF</div></header><div class='cards'>CARDS</div><section><h2>Reconciliation outcomes</h2>BARS<p class='note'>Pending payments are inside the configured settlement grace period. Failed payments without settlement are not applicable. Each key receives one status, using documented precedence.</p></section><section><h2>Exception queue</h2><button onclick="document.getElementById('exceptions').hidden=!document.getElementById('exceptions').hidden">Show / hide exceptions</button><div id='exceptions'>EXCEPTIONS</div><p class='note'>Currency-mismatch and orphan rows have non-comparable monetary values; never aggregate them as financial loss. Amounts are integer minor units. USD and CAD are never combined.</p></section><section><h2>Data-quality audit</h2>QUALITY</section><section><h2>Reading this report</h2><p class='note'>These anomalies were intentionally injected into generated data. This demonstrates validation and reconciliation logic; it reports no customer adoption, employer results, recovered revenue, or production performance. Downloadable CSVs and input hashes accompany the report. Fee assumption: 2.9% plus 30 cents, nonrefundable. Settlement grace: GRACE days. Full refresh: one writer, one snapshot.</p></section><footer>Python · SQL · PostgreSQL / SQLite · dbt · Docker · GitHub Actions</footer></main></body></html>"""
    for key,value in {"ASOF":esc(summary["as_of"]),"CARDS":cards,"BARS":bars,"EXCEPTIONS":exception_table,"QUALITY":quality_table,"GRACE":str(summary["grace_days"])}.items():
        page = page.replace(key,value)
    (output / "dashboard.html").write_text(page, encoding="utf-8")
