select substr(payment_at, 1, 10) as payment_date, currency,
       reconciliation_status, count(*) as payment_count,
       sum(gross_minor) as gross_minor, sum(refund_minor) as refund_minor,
       sum(expected_net_minor) as expected_net_minor,
       sum(settled_minor) as settled_minor, sum(variance_minor) as variance_minor
from {{ ref('payment_reconciliation') }}
where currency is not null and reconciliation_status <> 'currency_mismatch'
group by substr(payment_at, 1, 10), currency, reconciliation_status
