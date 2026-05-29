-- Access rules for the current PyQt desktop app integration.
-- This app uses its own username/password tables and the Supabase publishable anon key.
-- For a production POS, replace this with Supabase Auth + tighter RLS policies or Edge Functions.

grant usage on schema public to anon;

grant select, insert, update, delete on all tables in schema public to anon;
grant usage, select on all sequences in schema public to anon;

alter default privileges in schema public grant select, insert, update, delete on tables to anon;
alter default privileges in schema public grant usage, select on sequences to anon;

alter table if exists public.roles disable row level security;
alter table if exists public.users disable row level security;
alter table if exists public.registers disable row level security;
alter table if exists public.cash_shifts disable row level security;
alter table if exists public.cash_movements disable row level security;
alter table if exists public.products disable row level security;
alter table if exists public.product_barcodes disable row level security;
alter table if exists public.sales disable row level security;
alter table if exists public.sale_items disable row level security;
alter table if exists public.sale_payments disable row level security;
alter table if exists public.audit_logs disable row level security;
alter table if exists public.settings disable row level security;
alter table if exists public.sync_queue disable row level security;
alter table if exists public.app_meta disable row level security;
