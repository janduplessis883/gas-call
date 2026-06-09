-- Safe to run more than once in the Supabase SQL editor.
-- It repairs permissions and row-level-security policies used by the credit note flow.

grant usage on schema public to anon, authenticated;
grant select, insert, update, delete on public.credit_notes to anon, authenticated;
grant select, insert, update, delete on public.credit_note_items to anon, authenticated;
grant select, insert, update, delete on public.stock_movements to anon, authenticated;
grant select on public.clients to anon, authenticated;
grant select on public.products to anon, authenticated;

alter table public.credit_notes enable row level security;
alter table public.credit_note_items enable row level security;
alter table public.stock_movements enable row level security;

drop policy if exists "gas_at_call_public_all" on public.credit_notes;
create policy "gas_at_call_public_all"
on public.credit_notes
for all
to anon, authenticated
using (true)
with check (true);

drop policy if exists "gas_at_call_public_all" on public.credit_note_items;
create policy "gas_at_call_public_all"
on public.credit_note_items
for all
to anon, authenticated
using (true)
with check (true);

drop policy if exists "gas_at_call_public_all" on public.stock_movements;
create policy "gas_at_call_public_all"
on public.stock_movements
for all
to anon, authenticated
using (true)
with check (true);

select
  schemaname,
  tablename,
  policyname,
  roles,
  cmd,
  qual,
  with_check
from pg_policies
where schemaname = 'public'
  and tablename in ('credit_notes', 'credit_note_items', 'stock_movements')
order by tablename, policyname;
