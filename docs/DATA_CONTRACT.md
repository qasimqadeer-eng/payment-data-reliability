# Data contract and reconciliation policy

## Files and fields

CSV files use UTF-8, a header row, and the exact column order below. Blank required cells, malformed amounts, extra cells, invalid enums, or invalid timestamps are rejected. Wrong headers abort the run before database mutation.

| Feed | Required columns |
|---|---|
| payments.csv | payment_id, amount_minor, currency, status, occurred_at |
| refunds.csv | refund_id, payment_id, amount_minor, currency, status, occurred_at |
| settlements.csv | settlement_id, payment_id, amount_minor, currency, occurred_at |

- IDs are nonempty strings, unique within each feed after deduplication. Different IDs representing the same economic event cannot be identified automatically by this demo.
- Amounts are integers in cents. Payments/refunds must be positive and at most 10^12. Settlements may be negative (for example a fully refunded payment whose processing fee is retained), zero, or positive within ±10^12.
- Currency is USD or CAD. Both have two decimal minor units. No FX conversion.
- Payment and refund status is `completed` or `failed`. Failed refunds do not reduce expected settlement.
- Times are ISO-8601 with an explicit offset; normalized to UTC. Future times relative to `--as-of` are quarantined.
- Exact duplicates mean byte-equivalent parsed field values under the same ID. Semantically similar but differently formatted duplicates are conservatively conflicts.

## Net amount

`fee_minor = floor((gross_minor × 290 + 5000) / 10000) + 30`

`expected_net_minor = gross_minor − completed_refunds_minor − fee_minor`

`variance_minor = total_settled_minor − expected_net_minor`

The percentage fee rounds half up. It is charged once per completed payment and is not refunded. Failed payments have no expected payout. These are demo assumptions, not Ooredoo, Stripe, or any other provider's pricing.

The model expects a cumulative snapshot: all completed refunds in the input are already reflected in net settlement once a payment is mature. It does not model post-settlement refund timing separately. Split settlements are summed per payment; all currencies must match. No tolerance beyond exact cents is used.

## Status precedence

Each key has one primary status. Earlier rules win:

1. No accepted payment: orphan settlement.
2. A source record linked to the payment was quarantined: data quality blocked.
3. Settlement currency mismatch.
4. Settlement before payment.
5. Failed payment with settlement: unexpected settlement.
6. Failed payment without settlement: not applicable.
7. Refund total exceeds gross payment: excess refund.
8. Payment younger than grace period: pending.
9. Matured payment without settlement: missing settlement.
10. Nonzero variance: amount mismatch.
11. Otherwise matched.

At exactly two elapsed UTC days (default), a payment is mature. Grace uses calendar elapsed seconds, not banking days. Pending classification can mask an interim amount mismatch by design; once mature, it is evaluated.

## Audit and safe aggregation

Raw records are preserved in `raw_records`. One quality disposition is written per rejected/removed row; a rule field can contain multiple validation errors. Conflicting versions are all quarantined. Exact replays have disposition `deduplicated` and are not blocked.

The reconciliation key set is the union of accepted payment IDs and accepted settlement payment IDs. A wholly quarantined payment without accepted settlements appears in the quality audit, not the reconciliation table. Quarantined child rows block any surviving parent so their omission cannot silently create a successful match. A malformed child without a payment ID cannot be linked; strict mode still fails because the row is quarantined.

Daily monetary aggregates exclude orphan and mixed-currency rows. Other exceptional values remain diagnostic. Do not sum exception variances into a loss claim. See both the quality audit and reconciliation queue; neither alone contains all rejected data.

## Example controls

`P000001` exact replay; `P000002` conflicting payment versions; `P000003` missing settlement; `P000004` +125-cent mismatch; `P000005` currency mismatch; `P000006` excess refund; `P_PENDING` inside grace period. The manifest records these intentionally injected scenarios.
