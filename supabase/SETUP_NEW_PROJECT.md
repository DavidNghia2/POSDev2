# New Supabase Project Setup

Use these steps when you create a fresh Supabase project for the POS app. The `supabase/migrations` folder is intentionally a clean single-migration schema for a new project.

1. Create a new project in Supabase.
2. In the Supabase dashboard, open Authentication > Providers > Email and turn off email confirmations for local desktop testing. If confirmations stay on, Register Store creates the Auth user but the app cannot log in until the email is confirmed.
3. Copy `.env.example` to `.env`.
4. Fill `.env` with the new project's Project URL and anon public key from Project Settings > API.
5. Link and push the database schema:

```powershell
npx supabase link --project-ref YOUR_PROJECT_REF
npx supabase db push
```

6. Deploy the admin Edge Functions used by User Management:

```powershell
npx supabase functions deploy admin-create-user
npx supabase functions deploy admin-update-user
```

7. Run the app:

```powershell
.\.venv\Scripts\python.exe main.py
```

After this, the first account created from Register Store should be created as `Admin`.

If you reuse an email from an old Supabase project, delete that user from Authentication > Users in the new project first, or use a different email. The desktop app stores its local cache at `%LOCALAPPDATA%\RetailPOS\pos.db`; do not package a project-folder `pos.db` with production builds.
