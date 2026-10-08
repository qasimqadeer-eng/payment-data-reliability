select * from {{ ref('payment_reconciliation') }}
where reconciliation_status = 'matched'
  and (variance_minor <> 0 or settlement_count = 0 or matured <> 1)
