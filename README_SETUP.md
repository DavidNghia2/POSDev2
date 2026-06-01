# POS App Setup

Requirements:

- Python 3.11+ recommended
- PowerShell on Windows

Run this in PowerShell at the project folder:

```powershell
.\setup.ps1
```

Then run the app:

```powershell
.\.venv\Scripts\python.exe main.py
```

If Python 3.12 is not found:

```powershell
.\setup.ps1 -PythonVersion 3.11
```

The app creates its runtime SQLite cache at `%LOCALAPPDATA%\RetailPOS\pos.db` on Windows. Do not package or commit the project-folder `pos.db`; Supabase is the source of truth and SQLite is only a local cache. For development, set `POS_DB_PATH` in `.env` if you need a custom database path.

For cloud stores, product edits sync to Supabase and checkout uses the Supabase `checkout_sale` RPC so payment, sales, and inventory stock are committed together. Offline checkout is limited to Admin users and is saved locally as pending until the next sync.

For a fresh Supabase backend, follow `supabase/SETUP_NEW_PROJECT.md`, then update `.env` with the new Supabase URL and anon key.

The app logo is stored at `assets/app_logo.png`; keep that file in the project when copying or packaging the app.

Under `Progress`, I've listed everything completed for the project. If you work on something, please update it there. Also, make sure to sync the data on GitHub first before uploading your local changes.
