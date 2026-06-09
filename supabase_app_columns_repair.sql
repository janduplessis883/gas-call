-- Safe to run more than once in the Supabase SQL editor.
-- It catches the live database up to the app's current VAT/pricing columns.

alter table public.products
  add column if not exists gas_purchase_cost_ex_vat numeric(12, 2) not null default 0,
  add column if not exists container_purchase_cost_ex_vat numeric(12, 2) not null default 0,
  add column if not exists gas_sale_price_ex_vat numeric(12, 2) not null default 0,
  add column if not exists container_sale_price_ex_vat numeric(12, 2) not null default 0;

alter table public.stock_movements
  add column if not exists gas_amount_ex_vat numeric(12, 2) not null default 0,
  add column if not exists container_amount_ex_vat numeric(12, 2) not null default 0,
  add column if not exists gas_total_ex_vat numeric(12, 2) not null default 0,
  add column if not exists container_total_ex_vat numeric(12, 2) not null default 0,
  add column if not exists vat_amount numeric(12, 2) not null default 0,
  add column if not exists line_total numeric(12, 2) not null default 0;

alter table public.invoices
  add column if not exists gas_total_ex_vat numeric(12, 2) not null default 0,
  add column if not exists container_total_ex_vat numeric(12, 2) not null default 0,
  add column if not exists vat_amount numeric(12, 2) not null default 0;

alter table public.invoice_items
  add column if not exists gas_amount_ex_vat numeric(12, 2) not null default 0,
  add column if not exists container_amount_ex_vat numeric(12, 2) not null default 0,
  add column if not exists gas_total_ex_vat numeric(12, 2) not null default 0,
  add column if not exists container_total_ex_vat numeric(12, 2) not null default 0,
  add column if not exists vat_amount numeric(12, 2) not null default 0;

alter table public.credit_notes
  add column if not exists gas_total_ex_vat numeric(12, 2) not null default 0,
  add column if not exists container_total_ex_vat numeric(12, 2) not null default 0,
  add column if not exists vat_amount numeric(12, 2) not null default 0;

alter table public.credit_note_items
  add column if not exists gas_amount_ex_vat numeric(12, 2) not null default 0,
  add column if not exists container_amount_ex_vat numeric(12, 2) not null default 0,
  add column if not exists gas_total_ex_vat numeric(12, 2) not null default 0,
  add column if not exists container_total_ex_vat numeric(12, 2) not null default 0,
  add column if not exists vat_amount numeric(12, 2) not null default 0;

update public.products
set gas_sale_price_ex_vat = round(default_price / 1.15, 2)
where gas_sale_price_ex_vat = 0
  and container_sale_price_ex_vat = 0
  and default_price > 0;

grant select, insert, update, delete on all tables in schema public to anon, authenticated;
grant usage, select on all sequences in schema public to anon, authenticated;

notify pgrst, 'reload schema';

select
  table_name,
  column_name
from information_schema.columns
where table_schema = 'public'
  and table_name in (
    'products',
    'stock_movements',
    'invoices',
    'invoice_items',
    'credit_notes',
    'credit_note_items'
  )
  and column_name in (
    'gas_purchase_cost_ex_vat',
    'container_purchase_cost_ex_vat',
    'gas_sale_price_ex_vat',
    'container_sale_price_ex_vat',
    'gas_amount_ex_vat',
    'container_amount_ex_vat',
    'gas_total_ex_vat',
    'container_total_ex_vat',
    'vat_amount',
    'line_total'
  )
order by table_name, column_name;
