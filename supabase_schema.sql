create extension if not exists pgcrypto;

create table if not exists public.clients (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text not null default '',
  contact_number text not null default '',
  email text not null default '',
  notes text not null default '',
  created_at timestamptz not null default now()
);

create table if not exists public.products (
  id text primary key,
  label text not null,
  default_price numeric(12, 2) not null default 0,
  gas_purchase_cost_ex_vat numeric(12, 2) not null default 0,
  container_purchase_cost_ex_vat numeric(12, 2) not null default 0,
  gas_sale_price_ex_vat numeric(12, 2) not null default 0,
  container_sale_price_ex_vat numeric(12, 2) not null default 0,
  sort_order integer not null
);

insert into public.products (id, label, default_price, sort_order)
values
  ('5kg', '5kg gas cylinder', 0, 1),
  ('9kg', '9kg gas cylinder', 0, 2),
  ('14kg', '14kg gas cylinder', 0, 3),
  ('19kg', '19kg gas cylinder', 0, 4),
  ('48kg', '48kg gas cylinder', 0, 5)
on conflict (id) do nothing;

create table if not exists public.stock_movements (
  id uuid primary key default gen_random_uuid(),
  product_id text not null references public.products(id),
  movement_type text not null check (movement_type in ('purchase', 'sale', 'credit_note', 'adjustment')),
  quantity integer not null,
  unit_price numeric(12, 2) not null default 0,
  gas_amount_ex_vat numeric(12, 2) not null default 0,
  container_amount_ex_vat numeric(12, 2) not null default 0,
  gas_total_ex_vat numeric(12, 2) not null default 0,
  container_total_ex_vat numeric(12, 2) not null default 0,
  vat_amount numeric(12, 2) not null default 0,
  line_total numeric(12, 2) not null default 0,
  movement_date date not null default current_date,
  client_id uuid references public.clients(id),
  invoice_id uuid,
  credit_note_id uuid,
  notes text not null default '',
  created_at timestamptz not null default now()
);

create table if not exists public.invoices (
  id uuid primary key default gen_random_uuid(),
  invoice_number text not null unique,
  client_id uuid not null references public.clients(id),
  invoice_date date not null default current_date,
  gas_total_ex_vat numeric(12, 2) not null default 0,
  container_total_ex_vat numeric(12, 2) not null default 0,
  vat_amount numeric(12, 2) not null default 0,
  subtotal numeric(12, 2) not null default 0,
  total numeric(12, 2) not null default 0,
  status text not null default 'unpaid' check (status in ('unpaid', 'partial', 'paid', 'void')),
  pdf_filename text not null default '',
  created_at timestamptz not null default now()
);

create table if not exists public.invoice_items (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references public.invoices(id) on delete cascade,
  product_id text not null references public.products(id),
  quantity integer not null check (quantity > 0),
  unit_price numeric(12, 2) not null,
  gas_amount_ex_vat numeric(12, 2) not null default 0,
  container_amount_ex_vat numeric(12, 2) not null default 0,
  gas_total_ex_vat numeric(12, 2) not null default 0,
  container_total_ex_vat numeric(12, 2) not null default 0,
  vat_amount numeric(12, 2) not null default 0,
  line_total numeric(12, 2) not null
);

create table if not exists public.payments (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references public.invoices(id) on delete cascade,
  client_id uuid not null references public.clients(id),
  payment_date date not null default current_date,
  amount numeric(12, 2) not null check (amount > 0),
  method text not null default '',
  reference text not null default '',
  notes text not null default '',
  created_at timestamptz not null default now()
);

create table if not exists public.credit_notes (
  id uuid primary key default gen_random_uuid(),
  credit_number text not null unique,
  client_id uuid not null references public.clients(id),
  credit_date date not null default current_date,
  gas_total_ex_vat numeric(12, 2) not null default 0,
  container_total_ex_vat numeric(12, 2) not null default 0,
  vat_amount numeric(12, 2) not null default 0,
  amount numeric(12, 2) not null default 0,
  reason text not null default '',
  pdf_filename text not null default '',
  created_at timestamptz not null default now()
);

create table if not exists public.credit_note_items (
  id uuid primary key default gen_random_uuid(),
  credit_note_id uuid not null references public.credit_notes(id) on delete cascade,
  product_id text not null references public.products(id),
  quantity integer not null check (quantity > 0),
  unit_price numeric(12, 2) not null,
  gas_amount_ex_vat numeric(12, 2) not null default 0,
  container_amount_ex_vat numeric(12, 2) not null default 0,
  gas_total_ex_vat numeric(12, 2) not null default 0,
  container_total_ex_vat numeric(12, 2) not null default 0,
  vat_amount numeric(12, 2) not null default 0,
  line_total numeric(12, 2) not null
);

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

create index if not exists idx_clients_name on public.clients (name);
create index if not exists idx_stock_movements_product on public.stock_movements (product_id);
create index if not exists idx_stock_movements_client on public.stock_movements (client_id);
create index if not exists idx_invoices_client on public.invoices (client_id);
create index if not exists idx_payments_invoice on public.payments (invoice_id);

grant usage on schema public to anon, authenticated;
grant select, insert, update, delete on all tables in schema public to anon, authenticated;
grant usage, select on all sequences in schema public to anon, authenticated;

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
create policy "gas_at_call_public_all" on public.clients for all to public using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.products;
drop policy if exists "gas_at_call_public_all" on public.products;
create policy "gas_at_call_public_all" on public.products for all to public using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.stock_movements;
drop policy if exists "gas_at_call_public_all" on public.stock_movements;
create policy "gas_at_call_public_all" on public.stock_movements for all to public using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.invoices;
drop policy if exists "gas_at_call_public_all" on public.invoices;
create policy "gas_at_call_public_all" on public.invoices for all to public using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.invoice_items;
drop policy if exists "gas_at_call_public_all" on public.invoice_items;
create policy "gas_at_call_public_all" on public.invoice_items for all to public using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.payments;
drop policy if exists "gas_at_call_public_all" on public.payments;
create policy "gas_at_call_public_all" on public.payments for all to public using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.credit_notes;
drop policy if exists "gas_at_call_public_all" on public.credit_notes;
create policy "gas_at_call_public_all" on public.credit_notes for all to public using (true) with check (true);

drop policy if exists "gas_at_call_anon_all" on public.credit_note_items;
drop policy if exists "gas_at_call_public_all" on public.credit_note_items;
create policy "gas_at_call_public_all" on public.credit_note_items for all to public using (true) with check (true);
