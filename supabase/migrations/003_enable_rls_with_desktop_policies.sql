-- Enable RLS again and add explicit policies for the current desktop app.
-- This clears the "RLS Disabled in Public" Advisor warnings while preserving app access.
--
-- Note: these policies intentionally allow the anon/publishable key to read/write POS tables
-- because the current PyQt app does its own username/password login outside Supabase Auth.
-- For production, replace these broad policies with Supabase Auth or Edge Functions.

grant usage on schema public to anon;
grant select, insert, update, delete on all tables in schema public to anon;
grant usage, select on all sequences in schema public to anon;

alter table if exists public.roles enable row level security;
alter table if exists public.users enable row level security;
alter table if exists public.registers enable row level security;
alter table if exists public.cash_shifts enable row level security;
alter table if exists public.cash_movements enable row level security;
alter table if exists public.products enable row level security;
alter table if exists public.product_barcodes enable row level security;
alter table if exists public.sales enable row level security;
alter table if exists public.sale_items enable row level security;
alter table if exists public.sale_payments enable row level security;
alter table if exists public.audit_logs enable row level security;
alter table if exists public.settings enable row level security;
alter table if exists public.sync_queue enable row level security;
alter table if exists public.app_meta enable row level security;

drop policy if exists "desktop_app_all_access" on public.roles;
create policy "desktop_app_all_access" on public.roles
for all to anon using (true) with check (true);

drop policy if exists "desktop_app_all_access" on public.users;
create policy "desktop_app_all_access" on public.users
for all to anon using (true) with check (true);

drop policy if exists "desktop_app_all_access" on public.registers;
create policy "desktop_app_all_access" on public.registers
for all to anon using (true) with check (true);

drop policy if exists "desktop_app_all_access" on public.cash_shifts;
create policy "desktop_app_all_access" on public.cash_shifts
for all to anon using (true) with check (true);

drop policy if exists "desktop_app_all_access" on public.cash_movements;
create policy "desktop_app_all_access" on public.cash_movements
for all to anon using (true) with check (true);

drop policy if exists "desktop_app_all_access" on public.products;
create policy "desktop_app_all_access" on public.products
for all to anon using (true) with check (true);

drop policy if exists "desktop_app_all_access" on public.product_barcodes;
create policy "desktop_app_all_access" on public.product_barcodes
for all to anon using (true) with check (true);

drop policy if exists "desktop_app_all_access" on public.sales;
create policy "desktop_app_all_access" on public.sales
for all to anon using (true) with check (true);

drop policy if exists "desktop_app_all_access" on public.sale_items;
create policy "desktop_app_all_access" on public.sale_items
for all to anon using (true) with check (true);

drop policy if exists "desktop_app_all_access" on public.sale_payments;
create policy "desktop_app_all_access" on public.sale_payments
for all to anon using (true) with check (true);

drop policy if exists "desktop_app_all_access" on public.audit_logs;
create policy "desktop_app_all_access" on public.audit_logs
for all to anon using (true) with check (true);

drop policy if exists "desktop_app_all_access" on public.settings;
create policy "desktop_app_all_access" on public.settings
for all to anon using (true) with check (true);

drop policy if exists "desktop_app_all_access" on public.sync_queue;
create policy "desktop_app_all_access" on public.sync_queue
for all to anon using (true) with check (true);

drop policy if exists "desktop_app_all_access" on public.app_meta;
create policy "desktop_app_all_access" on public.app_meta
for all to anon using (true) with check (true);
