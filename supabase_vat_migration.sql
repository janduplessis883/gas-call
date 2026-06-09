alter table public.products add column if not exists gas_sale_price_ex_vat numeric(12, 2) not null default 0;
alter table public.products add column if not exists container_sale_price_ex_vat numeric(12, 2) not null default 0;
alter table public.products add column if not exists gas_purchase_cost_ex_vat numeric(12, 2) not null default 0;
alter table public.products add column if not exists container_purchase_cost_ex_vat numeric(12, 2) not null default 0;

alter table public.stock_movements add column if not exists gas_amount_ex_vat numeric(12, 2) not null default 0;
alter table public.stock_movements add column if not exists container_amount_ex_vat numeric(12, 2) not null default 0;
alter table public.stock_movements add column if not exists gas_total_ex_vat numeric(12, 2) not null default 0;
alter table public.stock_movements add column if not exists container_total_ex_vat numeric(12, 2) not null default 0;
alter table public.stock_movements add column if not exists vat_amount numeric(12, 2) not null default 0;
alter table public.stock_movements add column if not exists line_total numeric(12, 2) not null default 0;

alter table public.invoices add column if not exists gas_total_ex_vat numeric(12, 2) not null default 0;
alter table public.invoices add column if not exists container_total_ex_vat numeric(12, 2) not null default 0;
alter table public.invoices add column if not exists vat_amount numeric(12, 2) not null default 0;

alter table public.invoice_items add column if not exists gas_amount_ex_vat numeric(12, 2) not null default 0;
alter table public.invoice_items add column if not exists container_amount_ex_vat numeric(12, 2) not null default 0;
alter table public.invoice_items add column if not exists gas_total_ex_vat numeric(12, 2) not null default 0;
alter table public.invoice_items add column if not exists container_total_ex_vat numeric(12, 2) not null default 0;
alter table public.invoice_items add column if not exists vat_amount numeric(12, 2) not null default 0;

alter table public.credit_notes add column if not exists gas_total_ex_vat numeric(12, 2) not null default 0;
alter table public.credit_notes add column if not exists container_total_ex_vat numeric(12, 2) not null default 0;
alter table public.credit_notes add column if not exists vat_amount numeric(12, 2) not null default 0;

alter table public.credit_note_items add column if not exists gas_amount_ex_vat numeric(12, 2) not null default 0;
alter table public.credit_note_items add column if not exists container_amount_ex_vat numeric(12, 2) not null default 0;
alter table public.credit_note_items add column if not exists gas_total_ex_vat numeric(12, 2) not null default 0;
alter table public.credit_note_items add column if not exists container_total_ex_vat numeric(12, 2) not null default 0;
alter table public.credit_note_items add column if not exists vat_amount numeric(12, 2) not null default 0;

update public.products
set gas_sale_price_ex_vat = round(default_price / 1.15, 2)
where gas_sale_price_ex_vat = 0
  and container_sale_price_ex_vat = 0
  and default_price > 0;

update public.invoice_items
set
  gas_total_ex_vat = gas_amount_ex_vat * quantity,
  container_total_ex_vat = container_amount_ex_vat * quantity
where gas_total_ex_vat = 0
  and container_total_ex_vat = 0;

update public.credit_note_items
set
  gas_total_ex_vat = gas_amount_ex_vat * quantity,
  container_total_ex_vat = container_amount_ex_vat * quantity
where gas_total_ex_vat = 0
  and container_total_ex_vat = 0;

update public.stock_movements
set
  gas_total_ex_vat = gas_amount_ex_vat * abs(quantity),
  container_total_ex_vat = container_amount_ex_vat * abs(quantity)
where gas_total_ex_vat = 0
  and container_total_ex_vat = 0;

update public.invoices invoice
set
  gas_total_ex_vat = totals.gas_total_ex_vat,
  container_total_ex_vat = totals.container_total_ex_vat,
  vat_amount = totals.vat_amount,
  subtotal = totals.gas_total_ex_vat + totals.container_total_ex_vat
from (
  select
    invoice_id,
    sum(gas_total_ex_vat) as gas_total_ex_vat,
    sum(container_total_ex_vat) as container_total_ex_vat,
    sum(vat_amount) as vat_amount
  from public.invoice_items
  group by invoice_id
) totals
where invoice.id = totals.invoice_id;

update public.credit_notes credit
set
  gas_total_ex_vat = totals.gas_total_ex_vat,
  container_total_ex_vat = totals.container_total_ex_vat,
  vat_amount = totals.vat_amount
from (
  select
    credit_note_id,
    sum(gas_total_ex_vat) as gas_total_ex_vat,
    sum(container_total_ex_vat) as container_total_ex_vat,
    sum(vat_amount) as vat_amount
  from public.credit_note_items
  group by credit_note_id
) totals
where credit.id = totals.credit_note_id;
