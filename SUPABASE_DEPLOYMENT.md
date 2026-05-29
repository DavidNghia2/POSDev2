# Supabase Deployment Notes

This project is currently a Python/PyQt desktop app. Supabase can put the data online, but it does not turn the PyQt interface into a browser app by itself.

## Recommended Path

1. Use the Supabase project at `https://teqfqsgakcxuafkzxelm.supabase.co`.
2. Open the Supabase SQL editor.
3. Paste and run `supabase/migrations/001_initial_pos_schema.sql`.
4. Paste and run `supabase/migrations/002_allow_desktop_app_access.sql`.
5. Paste and run `supabase/migrations/003_enable_rls_with_desktop_policies.sql`.
6. Copy `.env.example` to `.env` and fill in `SUPABASE_ANON_KEY`.
7. Run the desktop app normally. When the anon key is present, products, users, sales, shifts, settings, reports, and dashboard data use Supabase. Without the key, the app falls back to local SQLite.

Supabase docs currently describe the platform deployment flow as database/environment deployment with migrations, branching, GitHub integration, CLI, and Edge Functions. Edge Functions are globally deployed TypeScript functions, and the Python client can query Supabase through the Data API.

## CLI Option

If you install the Supabase CLI, run these from the project folder:

```powershell
supabase login
supabase link --project-ref teqfqsgakcxuafkzxelm
supabase db push
```

## Local Environment

Copy `.env.example` to `.env` and fill in the anon key from:

`Supabase Dashboard > Project Settings > API > Project API keys > anon public`

The local `.env` file is ignored by git so the key is not committed.

For this project, `.env` is already configured with:

```env
SUPABASE_URL=https://teqfqsgakcxuafkzxelm.supabase.co
```

## Current Setup Status

The app can read the Supabase URL and key. A live connection test reached Supabase, but Supabase returned:

```text
Could not find the table 'public.roles' in the schema cache
```

That means the database schema has not been created in the Supabase project yet. Run `supabase/migrations/001_initial_pos_schema.sql` in the Supabase SQL editor, then restart the desktop app.

After the schema was created, Supabase returned:

```text
new row violates row-level security policy for table "roles"
```

Run `supabase/migrations/002_allow_desktop_app_access.sql` in the Supabase SQL editor to allow this desktop app to use the tables with the publishable anon key.

If Supabase Advisor warns that RLS is disabled, run `supabase/migrations/003_enable_rls_with_desktop_policies.sql`. It enables RLS and adds explicit desktop-app policies.

## Important Security Note

Do not put a Supabase `service_role` key inside the desktop app. Anyone who receives the app could extract it. For a real online POS system, put privileged database writes behind Edge Functions or another backend API, then have the app call that API.

## What Is Done In This Repo

- Added `supabase/migrations/001_initial_pos_schema.sql`.
- The migration creates the online Postgres versions of the current SQLite tables.
- Added `database/cloud.py`, a standard-library Supabase REST backend.
- Updated the desktop app to use Supabase automatically when `SUPABASE_ANON_KEY` is configured.
- Kept local SQLite fallback behavior for development or offline use.
