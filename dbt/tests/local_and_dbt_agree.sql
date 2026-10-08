-- Both execution routes must classify the exact same keys and amounts.
with differences as (
  (select * from {{ ref('payment_reconciliation') }}
   except select * from reliability.payment_reconciliation)
  union all
  (select * from reliability.payment_reconciliation
   except select * from {{ ref('payment_reconciliation') }})
)
select * from differences
