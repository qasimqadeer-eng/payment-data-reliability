with refunds as (
    select payment_id, sum(amount_minor) as refund_minor
    from {{ source('pipeline', 'clean_refunds') }}
    where status = 'completed' group by payment_id
), settlements as (
    select payment_id, count(*) as settlement_count, sum(amount_minor) as settled_minor,
           min(currency) as min_currency, max(currency) as max_currency,
           min(occurred_at) as first_settlement_at
    from {{ source('pipeline', 'clean_settlements') }} group by payment_id
), keys as (
    select payment_id from {{ source('pipeline', 'clean_payments') }}
    union select payment_id from {{ source('pipeline', 'clean_settlements') }}
), amounts as (
    select k.payment_id, p.currency, p.status as payment_status,
           p.occurred_at as payment_at, p.matured, b.payment_id as blocked_id,
           coalesce(p.amount_minor, 0) as gross_minor,
           coalesce(p.fee_minor, 0) as fee_minor,
           coalesce(r.refund_minor, 0) as refund_minor,
           case when p.status = 'completed'
                then p.amount_minor - p.fee_minor - coalesce(r.refund_minor, 0)
                else 0 end as expected_net_minor,
           coalesce(s.settled_minor, 0) as settled_minor,
           coalesce(s.settlement_count, 0) as settlement_count,
           s.min_currency, s.max_currency, s.first_settlement_at
    from keys k
    left join {{ source('pipeline', 'clean_payments') }} p on k.payment_id = p.payment_id
    left join refunds r on k.payment_id = r.payment_id
    left join settlements s on k.payment_id = s.payment_id
    left join {{ source('pipeline', 'blocked_payments') }} b on k.payment_id = b.payment_id
)
select *, settled_minor - expected_net_minor as variance_minor,
    case
        when payment_status is null then 'orphan_settlement'
        when blocked_id is not null then 'data_quality_blocked'
        when settlement_count > 0 and (min_currency <> currency or max_currency <> currency)
            then 'currency_mismatch'
        when first_settlement_at < payment_at then 'settlement_before_payment'
        when payment_status = 'failed' and settlement_count > 0 then 'unexpected_settlement'
        when payment_status = 'failed' then 'not_applicable'
        when refund_minor > gross_minor then 'excess_refund'
        when matured = 0 then 'pending'
        when settlement_count = 0 then 'missing_settlement'
        when settled_minor <> expected_net_minor then 'amount_mismatch'
        else 'matched'
    end as reconciliation_status
from amounts
