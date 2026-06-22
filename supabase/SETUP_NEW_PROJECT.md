# New Supabase Project Setup

Cap nhat: 2026-06-14

Use these steps when you create a fresh Supabase project for the POS desktop app. The app expects Supabase to be the source of truth for auth, store users, products, product images, registers, checkout, inventory, sales, realtime sync, and admin edge functions.

## 1. Create project

1. Create a new Supabase project.
2. In the Supabase dashboard, open Authentication > Providers > Email.
3. For local desktop testing, turn off email confirmations. If confirmations stay on, Register Store can create the Auth user but the app cannot log in until the email is confirmed.

## 2. Configure `.env`

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Fill these values from Project Settings > API:

```env
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_PUBLIC_KEY
```

Do not put the service-role key in `.env`; the desktop app and installer must only use the anon public key.

## 3. Push database schema

Link the project and push migrations:

```powershell
npx supabase link --project-ref YOUR_PROJECT_REF
npx supabase db push
```

The migrations currently create or configure:

- multi-tenant store/profile/role/register/product/sale tables
- local-friendly fields such as `updated_at`, soft delete/status columns, and sync-related data
- RPC helpers including `ensure_owner_profile`, `ensure_registered_store_owner`, and `checkout_sale`
- Storage bucket `product-images` and storage policies
- Realtime publication for products and sales

## 4. Deploy Edge Functions

Deploy the admin user functions:

```powershell
npx supabase functions deploy admin-create-user
npx supabase functions deploy admin-update-user
```

These functions are used by User Management so an Admin can create/update users in Supabase Auth while keeping profile rows in the same store.

## 5. Run app

Setup Python dependencies if needed:

```powershell
.\setup.ps1
```

Run the app:

```powershell
.\.venv\Scripts\python.exe main.py
```

Create the first account from Register Store. It should become the store Admin.

## Notes

- If you reuse an email from an old Supabase project, delete that user from Authentication > Users first, or use a different email.
- The desktop app stores its local cache at `%LOCALAPPDATA%\RetailPOS\pos.db`.
- Do not package a project-folder `pos.db` with production builds.
- Product images are uploaded to the `product-images` bucket and cached locally under `%LOCALAPPDATA%\RetailPOS\cache`.
- Installer builds copy the current `.env`; verify it contains only safe client config before release.
