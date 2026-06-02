-- Enable product/sale realtime notifications and restrict product writes to Admin/Manager.

do $$
begin
    if exists (select 1 from pg_publication where pubname = 'supabase_realtime')
       and not exists (
            select 1
            from pg_publication_tables
            where pubname = 'supabase_realtime'
              and schemaname = 'public'
              and tablename = 'products'
       ) then
        alter publication supabase_realtime add table public.products;
    end if;

    if exists (select 1 from pg_publication where pubname = 'supabase_realtime')
       and not exists (
            select 1
            from pg_publication_tables
            where pubname = 'supabase_realtime'
              and schemaname = 'public'
              and tablename = 'sales'
       ) then
        alter publication supabase_realtime add table public.sales;
    end if;
end $$;

create or replace function public.can_manage_products()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.profiles p
        join public.roles r on r.id = p.role_id
        where p.auth_user_id = auth.uid()
          and p.active = true
          and p.store_id = public.current_store_id()
          and r.name in ('Admin', 'Manager')
    )
$$;

grant execute on function public.can_manage_products() to authenticated;

drop policy if exists products_tenant_write on public.products;
drop policy if exists products_tenant_insert on public.products;
drop policy if exists products_tenant_update on public.products;
drop policy if exists products_tenant_delete on public.products;

create policy products_tenant_insert on public.products
for insert to authenticated
with check (
    store_id = public.current_store_id()
    and public.can_manage_products()
);

create policy products_tenant_update on public.products
for update to authenticated
using (
    store_id = public.current_store_id()
    and public.can_manage_products()
)
with check (
    store_id = public.current_store_id()
    and public.can_manage_products()
);

drop policy if exists product_barcodes_tenant_write on public.product_barcodes;
drop policy if exists product_barcodes_tenant_insert on public.product_barcodes;
drop policy if exists product_barcodes_tenant_update on public.product_barcodes;
drop policy if exists product_barcodes_tenant_delete on public.product_barcodes;

create policy product_barcodes_tenant_insert on public.product_barcodes
for insert to authenticated
with check (
    store_id = public.current_store_id()
    and public.can_manage_products()
);

create policy product_barcodes_tenant_update on public.product_barcodes
for update to authenticated
using (
    store_id = public.current_store_id()
    and public.can_manage_products()
)
with check (
    store_id = public.current_store_id()
    and public.can_manage_products()
);

create policy product_barcodes_tenant_delete on public.product_barcodes
for delete to authenticated
using (
    store_id = public.current_store_id()
    and public.can_manage_products()
);
