grant usage on schema public to anon, authenticated;
grant select, insert, update, delete on all tables in schema public to anon, authenticated;
grant usage, select on all sequences in schema public to anon, authenticated;

insert into public.products (id, label, default_price, sort_order)
values
  ('5kg', '5kg gas cylinder', 0, 1),
  ('9kg', '9kg gas cylinder', 0, 2),
  ('14kg', '14kg gas cylinder', 0, 3),
  ('19kg', '19kg gas cylinder', 0, 4),
  ('48kg', '48kg gas cylinder', 0, 5)
on conflict (id) do nothing;

alter table public.clients enable row level security;
alter table public.products enable row level security;
alter table public.stock_movements enable row level security;
alter table public.invoices enable row level security;
alter table public.invoice_items enable row level security;
alter table public.payments enable row level security;
alter table public.credit_notes enable row level security;
alter table public.credit_note_items enable row level security;

drop policy if exists "gas_at_call_anon_all" on public.clients;
drop policy if exists "gas_at_call_public_all" on public.clients;
create policy "gas_at_call_public_all" on public.clients for all to anon, authenticated using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.products;
drop policy if exists "gas_at_call_public_all" on public.products;
create policy "gas_at_call_public_all" on public.products for all to anon, authenticated using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.stock_movements;
drop policy if exists "gas_at_call_public_all" on public.stock_movements;
create policy "gas_at_call_public_all" on public.stock_movements for all to anon, authenticated using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.invoices;
drop policy if exists "gas_at_call_public_all" on public.invoices;
create policy "gas_at_call_public_all" on public.invoices for all to anon, authenticated using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.invoice_items;
drop policy if exists "gas_at_call_public_all" on public.invoice_items;
create policy "gas_at_call_public_all" on public.invoice_items for all to anon, authenticated using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.payments;
drop policy if exists "gas_at_call_public_all" on public.payments;
create policy "gas_at_call_public_all" on public.payments for all to anon, authenticated using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.credit_notes;
drop policy if exists "gas_at_call_public_all" on public.credit_notes;
create policy "gas_at_call_public_all" on public.credit_notes for all to anon, authenticated using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.credit_note_items;
drop policy if exists "gas_at_call_public_all" on public.credit_note_items;
create policy "gas_at_call_public_all" on public.credit_note_items for all to anon, authenticated using (true) with check (true);
