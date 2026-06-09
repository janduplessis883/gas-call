-- Safe to run more than once in the Supabase SQL editor.
-- It adds the product pricing columns used by Prices & settings.

alter table public.products
  add column if not exists gas_purchase_cost_ex_vat numeric(12, 2) not null default 0,
  add column if not exists container_purchase_cost_ex_vat numeric(12, 2) not null default 0,
  add column if not exists gas_sale_price_ex_vat numeric(12, 2) not null default 0,
  add column if not exists container_sale_price_ex_vat numeric(12, 2) not null default 0;

update public.products
set gas_sale_price_ex_vat = round(default_price / 1.15, 2)
where gas_sale_price_ex_vat = 0
  and container_sale_price_ex_vat = 0
  and default_price > 0;

grant select, insert, update, delete on public.products to anon, authenticated;

drop policy if exists "gas_at_call_public_all" on public.products;
create policy "gas_at_call_public_all"
on public.products
for all
to anon, authenticated
using (true)
with check (true);

notify pgrst, 'reload schema';

select
  column_name,
  data_type,
  numeric_precision,
  numeric_scale,
  column_default
from information_schema.columns
where table_schema = 'public'
  and table_name = 'products'
  and column_name in (
    'gas_purchase_cost_ex_vat',
    'container_purchase_cost_ex_vat',
    'gas_sale_price_ex_vat',
    'container_sale_price_ex_vat'
  )
order by column_name;
