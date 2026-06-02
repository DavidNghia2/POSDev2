create extension if not exists pgcrypto;

create table public.stores (
    id uuid primary key default gen_random_uuid(),
    name text not null check (btrim(name) <> ''),
    owner_user_id uuid unique references auth.users(id) on delete set null,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.roles (
    id bigserial primary key,
    name text not null unique check (btrim(name) <> ''),
    permissions text not null default '',
    created_at timestamptz not null default now()
);

insert into public.roles (name, permissions)
values
    ('Admin', 'all'),
    ('Manager', 'sales,reports,products,registers,shifts,reconciliation'),
    ('Cashier', 'sales,shifts')
on conflict (name) do update set permissions = excluded.permissions;

create table public.profiles (
    auth_user_id uuid primary key references auth.users(id) on delete cascade,
    store_id uuid not null references public.stores(id) on delete cascade,
    email text not null check (btrim(email) <> ''),
    full_name text not null check (btrim(full_name) <> ''),
    role_id bigint not null references public.roles(id),
    active boolean not null default true,
    deleted_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index profiles_store_email_key
on public.profiles (store_id, lower(email));

create table public.registers (
    id bigserial primary key,
    store_id uuid not null references public.stores(id) on delete cascade,
    name text not null check (btrim(name) <> ''),
    location text,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index registers_store_name_key
on public.registers (store_id, lower(name));

create table public.products (
    id bigserial primary key,
    store_id uuid not null references public.stores(id) on delete cascade,
    barcode text,
    sku text,
    name text not null check (btrim(name) <> ''),
    price numeric(12, 2) not null check (price >= 0),
    category text,
    stock_qty numeric(14, 3) not null default 0 check (stock_qty >= 0),
    requires_weight boolean not null default false,
    active boolean not null default true,
    storage_path text,
    image_url text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index products_store_barcode_key
on public.products (store_id, barcode)
where barcode is not null and btrim(barcode) <> '';

create unique index products_store_sku_key
on public.products (store_id, sku)
where sku is not null and btrim(sku) <> '';

create table public.product_barcodes (
    id bigserial primary key,
    store_id uuid not null references public.stores(id) on delete cascade,
    product_id bigint not null references public.products(id) on delete cascade,
    barcode text not null check (btrim(barcode) <> ''),
    is_primary boolean not null default false,
    created_at timestamptz not null default now()
);

create unique index product_barcodes_store_barcode_key
on public.product_barcodes (store_id, barcode);

create table public.sales (
    id bigserial primary key,
    store_id uuid not null references public.stores(id) on delete cascade,
    client_sale_id uuid not null,
    user_id uuid references auth.users(id) on delete set null,
    register_id bigint references public.registers(id) on delete set null,
    total_amount numeric(12, 2) not null check (total_amount >= 0),
    payment_method text not null default 'Unknown',
    tendered_amount numeric(12, 2) not null default 0,
    change_amount numeric(12, 2) not null default 0,
    note text,
    status text not null default 'completed',
    created_at timestamptz not null default now(),
    unique (store_id, client_sale_id)
);

create table public.sale_items (
    id bigserial primary key,
    store_id uuid not null references public.stores(id) on delete cascade,
    sale_id bigint not null references public.sales(id) on delete cascade,
    product_id bigint references public.products(id) on delete set null,
    barcode text,
    name text not null,
    qty numeric(14, 3) not null check (qty > 0),
    price numeric(12, 2) not null check (price >= 0),
    subtotal numeric(12, 2) not null check (subtotal >= 0)
);

create table public.sale_payments (
    id bigserial primary key,
    store_id uuid not null references public.stores(id) on delete cascade,
    sale_id bigint not null references public.sales(id) on delete cascade,
    method text not null,
    amount numeric(12, 2) not null check (amount >= 0),
    created_at timestamptz not null default now()
);

create table public.inventory_movements (
    id bigserial primary key,
    store_id uuid not null references public.stores(id) on delete cascade,
    product_id bigint not null references public.products(id) on delete cascade,
    sale_id bigint references public.sales(id) on delete set null,
    qty_delta numeric(14, 3) not null,
    reason text not null,
    created_at timestamptz not null default now()
);

create table public.cash_shifts (
    id bigserial primary key,
    store_id uuid not null references public.stores(id) on delete cascade,
    register_id bigint not null references public.registers(id) on delete cascade,
    user_id uuid references auth.users(id) on delete set null,
    opened_at timestamptz not null default now(),
    closed_at timestamptz,
    opening_balance numeric(12, 2) not null default 0,
    closing_balance numeric(12, 2),
    expected_balance numeric(12, 2),
    status text not null default 'open',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.cash_movements (
    id bigserial primary key,
    store_id uuid not null references public.stores(id) on delete cascade,
    shift_id bigint not null references public.cash_shifts(id) on delete cascade,
    user_id uuid references auth.users(id) on delete set null,
    type text not null,
    amount numeric(12, 2) not null check (amount >= 0),
    reason text,
    created_at timestamptz not null default now()
);

create table public.audit_logs (
    id bigserial primary key,
    store_id uuid not null references public.stores(id) on delete cascade,
    user_id uuid references auth.users(id) on delete set null,
    action text not null,
    table_name text,
    record_id text,
    old_values jsonb,
    new_values jsonb,
    created_at timestamptz not null default now()
);

create table public.settings (
    id bigserial primary key,
    store_id uuid not null references public.stores(id) on delete cascade,
    key text not null,
    value text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (store_id, key)
);

create index profiles_store_idx on public.profiles (store_id);
create index registers_store_idx on public.registers (store_id);
create index products_store_idx on public.products (store_id);
create index product_barcodes_product_idx on public.product_barcodes (product_id);
create index sales_store_created_idx on public.sales (store_id, created_at desc);
create index sale_items_store_sale_idx on public.sale_items (store_id, sale_id);
create index sale_payments_store_sale_idx on public.sale_payments (store_id, sale_id);
create index inventory_movements_store_product_idx on public.inventory_movements (store_id, product_id);
create index cash_shifts_store_status_idx on public.cash_shifts (store_id, status);
create index cash_movements_store_shift_idx on public.cash_movements (store_id, shift_id);
create index audit_logs_store_created_idx on public.audit_logs (store_id, created_at desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger stores_set_updated_at
before update on public.stores
for each row execute function public.set_updated_at();

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create trigger registers_set_updated_at
before update on public.registers
for each row execute function public.set_updated_at();

create trigger products_set_updated_at
before update on public.products
for each row execute function public.set_updated_at();

create trigger cash_shifts_set_updated_at
before update on public.cash_shifts
for each row execute function public.set_updated_at();

create trigger settings_set_updated_at
before update on public.settings
for each row execute function public.set_updated_at();

create or replace function public.current_store_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
    select p.store_id
    from public.profiles p
    where p.auth_user_id = auth.uid()
      and p.active = true
    limit 1
$$;

create or replace function public.is_store_admin()
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
          and r.name = 'Admin'
    )
$$;

create or replace function public.create_owner_profile_for_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_store_id uuid;
    v_admin_role_id bigint;
    v_store_name text;
    v_full_name text;
begin
    v_store_name := nullif(btrim(coalesce(new.raw_user_meta_data ->> 'store_name', '')), '');
    if v_store_name is null then
        return new;
    end if;

    select id into v_admin_role_id
    from public.roles
    where name = 'Admin';

    if v_admin_role_id is null then
        raise exception 'Admin role is missing';
    end if;

    v_full_name := coalesce(nullif(btrim(new.raw_user_meta_data ->> 'full_name'), ''), new.email);

    insert into public.stores (name, owner_user_id)
    values (v_store_name, new.id)
    on conflict (owner_user_id) do update set
        name = excluded.name,
        active = true
    returning id into v_store_id;

    insert into public.profiles (auth_user_id, store_id, email, full_name, role_id, active)
    values (new.id, v_store_id, new.email, v_full_name, v_admin_role_id, true)
    on conflict (auth_user_id) do update set
        store_id = excluded.store_id,
        email = excluded.email,
        full_name = excluded.full_name,
        role_id = excluded.role_id,
        active = true;

    insert into public.registers (store_id, name, location)
    values (v_store_id, 'Main Register', 'Store Front')
    on conflict do nothing;

    return new;
end;
$$;

create trigger create_owner_profile_after_auth_signup
after insert on auth.users
for each row execute function public.create_owner_profile_for_auth_user();

create or replace function public.ensure_owner_profile()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_auth_user_id uuid;
    v_email text;
    v_metadata jsonb;
    v_store_name text;
    v_full_name text;
begin
    v_auth_user_id := auth.uid();
    if v_auth_user_id is null then
        raise exception 'Not authenticated';
    end if;

    select email, raw_user_meta_data
    into v_email, v_metadata
    from auth.users
    where id = v_auth_user_id;

    v_store_name := nullif(btrim(coalesce(v_metadata ->> 'store_name', '')), '');
    if v_store_name is null then
        return jsonb_build_object('status', 'not_owner_signup');
    end if;

    v_full_name := coalesce(nullif(btrim(v_metadata ->> 'full_name'), ''), v_email);
    return public.ensure_registered_store_owner(v_store_name, v_full_name);
end;
$$;

create or replace function public.ensure_registered_store_owner(
    p_store_name text,
    p_full_name text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_auth_user_id uuid;
    v_email text;
    v_store_id uuid;
    v_profile_store_id uuid;
    v_profile_store_owner uuid;
    v_admin_role_id bigint;
    v_store_name text;
    v_full_name text;
begin
    v_auth_user_id := auth.uid();
    if v_auth_user_id is null then
        raise exception 'Not authenticated';
    end if;

    v_store_name := nullif(btrim(coalesce(p_store_name, '')), '');
    if v_store_name is null then
        raise exception 'Store name is required';
    end if;

    select email into v_email
    from auth.users
    where id = v_auth_user_id;

    v_full_name := coalesce(nullif(btrim(coalesce(p_full_name, '')), ''), v_email);

    select id into v_admin_role_id
    from public.roles
    where name = 'Admin';

    if v_admin_role_id is null then
        raise exception 'Admin role is missing';
    end if;

    update auth.users
    set raw_user_meta_data = coalesce(raw_user_meta_data, '{}'::jsonb)
        || jsonb_build_object(
            'store_name', v_store_name,
            'full_name', v_full_name,
            'pos_owner_signup', true
        )
    where id = v_auth_user_id;

    select p.store_id, s.owner_user_id
    into v_profile_store_id, v_profile_store_owner
    from public.profiles p
    join public.stores s on s.id = p.store_id
    where p.auth_user_id = v_auth_user_id
    limit 1;

    if v_profile_store_id is not null
       and (v_profile_store_owner is null or v_profile_store_owner = v_auth_user_id) then
        v_store_id := v_profile_store_id;
    else
        select id into v_store_id
        from public.stores
        where owner_user_id = v_auth_user_id
        limit 1;
    end if;

    if v_store_id is null then
        insert into public.stores (name, owner_user_id)
        values (v_store_name, v_auth_user_id)
        returning id into v_store_id;
    else
        update public.stores
        set name = v_store_name,
            owner_user_id = v_auth_user_id,
            active = true
        where id = v_store_id;
    end if;

    insert into public.profiles (auth_user_id, store_id, email, full_name, role_id, active)
    values (v_auth_user_id, v_store_id, v_email, v_full_name, v_admin_role_id, true)
    on conflict (auth_user_id) do update set
        store_id = excluded.store_id,
        email = excluded.email,
        full_name = excluded.full_name,
        role_id = excluded.role_id,
        active = true;

    insert into public.registers (store_id, name, location)
    values (v_store_id, 'Main Register', 'Store Front')
    on conflict do nothing;

    return jsonb_build_object(
        'status', 'ok',
        'store_id', v_store_id,
        'role_name', 'Admin'
    );
end;
$$;

create or replace function public.checkout_sale(
    p_client_sale_id uuid,
    p_register_id bigint,
    p_items jsonb,
    p_payments jsonb,
    p_total_amount numeric,
    p_note text default ''
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_store_id uuid;
    v_sale_id bigint;
    v_payment_method text := 'Unknown';
    v_tendered_amount numeric(12, 2) := 0;
    v_change_amount numeric(12, 2) := 0;
    v_product_id bigint;
    v_requested_qty numeric(14, 3);
    v_available_qty numeric(14, 3);
    v_product_name text;
    v_item jsonb;
    v_payment jsonb;
begin
    select store_id into v_store_id
    from public.profiles
    where auth_user_id = auth.uid()
      and active = true
    limit 1;

    if v_store_id is null then
        raise exception 'No active store profile for current user';
    end if;

    if p_client_sale_id is null then
        raise exception 'client_sale_id is required';
    end if;

    if p_total_amount is null or p_total_amount < 0 then
        raise exception 'total_amount must be non-negative';
    end if;

    if p_items is null or jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items) = 0 then
        raise exception 'Sale items are required';
    end if;

    if p_register_id is not null and not exists (
        select 1
        from public.registers
        where id = p_register_id
          and store_id = v_store_id
          and active = true
    ) then
        raise exception 'Register is not in this store';
    end if;

    select id into v_sale_id
    from public.sales
    where store_id = v_store_id
      and client_sale_id = p_client_sale_id;

    if v_sale_id is not null then
        return jsonb_build_object('status', 'ok', 'sale_id', v_sale_id, 'idempotent', true);
    end if;

    for v_item in select * from jsonb_array_elements(p_items)
    loop
        v_product_id := nullif(v_item ->> 'product_id', '')::bigint;
        v_requested_qty := (v_item ->> 'qty')::numeric;

        if v_product_id is null then
            return jsonb_build_object('status', 'insufficient_stock', 'message', 'Product is required');
        end if;

        if v_requested_qty is null or v_requested_qty <= 0 then
            raise exception 'Quantity must be positive';
        end if;

        select stock_qty, name
        into v_available_qty, v_product_name
        from public.products
        where id = v_product_id
          and store_id = v_store_id
          and active = true
        for update;

        if v_available_qty is null then
            return jsonb_build_object(
                'status', 'insufficient_stock',
                'product_id', v_product_id,
                'message', 'Product not found'
            );
        end if;

        if v_requested_qty > v_available_qty then
            return jsonb_build_object(
                'status', 'insufficient_stock',
                'product_id', v_product_id,
                'available_qty', v_available_qty,
                'message', v_product_name || ' has only ' || v_available_qty || ' available'
            );
        end if;
    end loop;

    if p_payments is not null and jsonb_typeof(p_payments) = 'array' then
        for v_payment in select * from jsonb_array_elements(p_payments)
        loop
            if v_payment_method = 'Unknown' then
                v_payment_method := coalesce(nullif(v_payment ->> 'method', ''), 'Unknown');
            end if;
            v_tendered_amount := v_tendered_amount + coalesce((v_payment ->> 'amount')::numeric, 0);
        end loop;
    end if;

    v_change_amount := greatest(v_tendered_amount - p_total_amount, 0);

    insert into public.sales (
        store_id,
        client_sale_id,
        user_id,
        register_id,
        total_amount,
        payment_method,
        tendered_amount,
        change_amount,
        note,
        status
    )
    values (
        v_store_id,
        p_client_sale_id,
        auth.uid(),
        p_register_id,
        p_total_amount,
        v_payment_method,
        v_tendered_amount,
        v_change_amount,
        nullif(btrim(coalesce(p_note, '')), ''),
        'completed'
    )
    returning id into v_sale_id;

    for v_item in select * from jsonb_array_elements(p_items)
    loop
        v_product_id := nullif(v_item ->> 'product_id', '')::bigint;
        v_requested_qty := (v_item ->> 'qty')::numeric;

        insert into public.sale_items (
            store_id,
            sale_id,
            product_id,
            barcode,
            name,
            qty,
            price,
            subtotal
        )
        values (
            v_store_id,
            v_sale_id,
            v_product_id,
            nullif(v_item ->> 'barcode', ''),
            coalesce(nullif(v_item ->> 'name', ''), 'Item'),
            v_requested_qty,
            (v_item ->> 'price')::numeric,
            (v_item ->> 'subtotal')::numeric
        );

        update public.products
        set stock_qty = stock_qty - v_requested_qty
        where id = v_product_id
          and store_id = v_store_id;

        insert into public.inventory_movements (store_id, product_id, sale_id, qty_delta, reason)
        values (v_store_id, v_product_id, v_sale_id, -v_requested_qty, 'sale');
    end loop;

    if p_payments is not null and jsonb_typeof(p_payments) = 'array' then
        for v_payment in select * from jsonb_array_elements(p_payments)
        loop
            insert into public.sale_payments (store_id, sale_id, method, amount)
            values (
                v_store_id,
                v_sale_id,
                coalesce(nullif(v_payment ->> 'method', ''), 'Unknown'),
                coalesce((v_payment ->> 'amount')::numeric, 0)
            );
        end loop;
    end if;

    return jsonb_build_object('status', 'ok', 'sale_id', v_sale_id, 'idempotent', false);
end;
$$;

grant usage on schema public to anon, authenticated, service_role;
grant select on all tables in schema public to authenticated;
grant insert, update, delete on
    public.registers,
    public.products,
    public.product_barcodes,
    public.sales,
    public.sale_items,
    public.sale_payments,
    public.inventory_movements,
    public.cash_shifts,
    public.cash_movements,
    public.settings
to authenticated;
grant update on public.stores, public.profiles to authenticated;
grant insert on public.audit_logs to authenticated;
grant usage, select on all sequences in schema public to authenticated;
grant execute on function public.current_store_id() to authenticated;
grant execute on function public.is_store_admin() to authenticated;
grant execute on function public.ensure_owner_profile() to authenticated;
grant execute on function public.ensure_registered_store_owner(text, text) to authenticated;
grant execute on function public.checkout_sale(uuid, bigint, jsonb, jsonb, numeric, text) to authenticated;
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;
grant execute on all functions in schema public to service_role;

alter table public.roles enable row level security;
alter table public.stores enable row level security;
alter table public.profiles enable row level security;
alter table public.registers enable row level security;
alter table public.products enable row level security;
alter table public.product_barcodes enable row level security;
alter table public.sales enable row level security;
alter table public.sale_items enable row level security;
alter table public.sale_payments enable row level security;
alter table public.inventory_movements enable row level security;
alter table public.cash_shifts enable row level security;
alter table public.cash_movements enable row level security;
alter table public.audit_logs enable row level security;
alter table public.settings enable row level security;

create policy roles_read on public.roles
for select to authenticated
using (true);

create policy stores_read_own on public.stores
for select to authenticated
using (id = public.current_store_id());

create policy stores_admin_update_own on public.stores
for update to authenticated
using (id = public.current_store_id() and public.is_store_admin())
with check (id = public.current_store_id() and public.is_store_admin());

create policy profiles_read_own_store on public.profiles
for select to authenticated
using (auth_user_id = auth.uid() or store_id = public.current_store_id());

create policy profiles_admin_update_own_store on public.profiles
for update to authenticated
using (store_id = public.current_store_id() and public.is_store_admin())
with check (store_id = public.current_store_id() and public.is_store_admin());

create policy registers_tenant_read on public.registers
for select to authenticated
using (store_id = public.current_store_id());

create policy registers_tenant_write on public.registers
for all to authenticated
using (store_id = public.current_store_id())
with check (store_id = public.current_store_id());

create policy products_tenant_read on public.products
for select to authenticated
using (store_id = public.current_store_id());

create policy products_tenant_write on public.products
for all to authenticated
using (store_id = public.current_store_id())
with check (store_id = public.current_store_id());

create policy product_barcodes_tenant_read on public.product_barcodes
for select to authenticated
using (store_id = public.current_store_id());

create policy product_barcodes_tenant_write on public.product_barcodes
for all to authenticated
using (store_id = public.current_store_id())
with check (store_id = public.current_store_id());

create policy sales_tenant_read on public.sales
for select to authenticated
using (store_id = public.current_store_id());

create policy sales_tenant_write on public.sales
for all to authenticated
using (store_id = public.current_store_id())
with check (store_id = public.current_store_id());

create policy sale_items_tenant_read on public.sale_items
for select to authenticated
using (store_id = public.current_store_id());

create policy sale_items_tenant_write on public.sale_items
for all to authenticated
using (store_id = public.current_store_id())
with check (store_id = public.current_store_id());

create policy sale_payments_tenant_read on public.sale_payments
for select to authenticated
using (store_id = public.current_store_id());

create policy sale_payments_tenant_write on public.sale_payments
for all to authenticated
using (store_id = public.current_store_id())
with check (store_id = public.current_store_id());

create policy inventory_movements_tenant_read on public.inventory_movements
for select to authenticated
using (store_id = public.current_store_id());

create policy inventory_movements_tenant_write on public.inventory_movements
for all to authenticated
using (store_id = public.current_store_id())
with check (store_id = public.current_store_id());

create policy cash_shifts_tenant_read on public.cash_shifts
for select to authenticated
using (store_id = public.current_store_id());

create policy cash_shifts_tenant_write on public.cash_shifts
for all to authenticated
using (store_id = public.current_store_id())
with check (store_id = public.current_store_id());

create policy cash_movements_tenant_read on public.cash_movements
for select to authenticated
using (store_id = public.current_store_id());

create policy cash_movements_tenant_write on public.cash_movements
for all to authenticated
using (store_id = public.current_store_id())
with check (store_id = public.current_store_id());

create policy audit_logs_tenant_read on public.audit_logs
for select to authenticated
using (store_id = public.current_store_id());

create policy audit_logs_tenant_insert on public.audit_logs
for insert to authenticated
with check (store_id = public.current_store_id());

create policy settings_tenant_read on public.settings
for select to authenticated
using (store_id = public.current_store_id());

create policy settings_tenant_write on public.settings
for all to authenticated
using (store_id = public.current_store_id())
with check (store_id = public.current_store_id());

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'product-images',
    'product-images',
    true,
    5242880,
    array['image/jpeg', 'image/png', 'image/webp', 'image/gif']
)
on conflict (id) do update set
    public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

create policy product_images_public_read on storage.objects
for select
using (bucket_id = 'product-images');

create policy product_images_tenant_insert on storage.objects
for insert to authenticated
with check (
    bucket_id = 'product-images'
    and (storage.foldername(name))[1] = public.current_store_id()::text
);

create policy product_images_tenant_update on storage.objects
for update to authenticated
using (
    bucket_id = 'product-images'
    and (storage.foldername(name))[1] = public.current_store_id()::text
)
with check (
    bucket_id = 'product-images'
    and (storage.foldername(name))[1] = public.current_store_id()::text
);

create policy product_images_tenant_delete on storage.objects
for delete to authenticated
using (
    bucket_id = 'product-images'
    and (storage.foldername(name))[1] = public.current_store_id()::text
);
