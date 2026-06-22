# POS App Setup

Updated: 2026-06-14

This project is a Python + PyQt6 desktop POS application. Supabase is the main backend for auth, users, products, registers, sales, inventory, storage, realtime sync, and edge functions. Local SQLite is stored under the current user's profile and is used as a cache and offline store.

## Requirements

- Windows with PowerShell
- Python 3.11 or newer; setup uses Python 3.12 by default
- A Supabase project with the schema and functions deployed for cloud stores
- Inno Setup 6 when building the installer

## Local development setup

Run this from the project folder:

```powershell
.\setup.ps1
```

If Python 3.12 is not available:

```powershell
.\setup.ps1 -PythonVersion 3.11
```

Create `.env` from `.env.example` and fill in:

```env
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
```

Never use a service-role key in the desktop app.

## Run the app

```powershell
.\.venv\Scripts\python.exe main.py
```

The legacy entry command still works:

```powershell
.\.venv\Scripts\python.exe pos_terminal.py
```

## Data location

The app creates its runtime SQLite database at:

```text
%LOCALAPPDATA%\RetailPOS\pos.db
```

Do not package or commit a project-folder `pos.db`. For development, use `.env` to override the database path when needed:

```env
POS_DB_PATH=pos.dev.db
```

Product images are synced from Supabase Storage and cached at runtime under:

```text
%LOCALAPPDATA%\RetailPOS\cache
```

## Build

Build the portable EXE:

```powershell
.\build_exe.ps1
```

Build the Inno Setup installer:

```powershell
.\build_installer.ps1
```

See `BUILD_EXE.md` for the full build and packaging details.

## Supabase setup

For a new Supabase project, follow:

```text
supabase\SETUP_NEW_PROJECT.md
```

Deploy the migrations and edge functions before building a production release. The app currently uses Supabase Auth, database tables, RPC `checkout_sale`, admin user Edge Functions, the `product-images` Storage bucket, and realtime sync.

## Project notes

- `app_paths.py` manages `.env` lookup, runtime database paths, and cache paths.
- `cloud/` contains Supabase client, auth, product, and inventory helpers.
- `database/db.py` contains the local SQLite schema, cache logic, product sync, sale sync, and checkout fallback.
- `login/login_window.py` handles Supabase login/register, session persistence, and the local user cache.
- `pos_terminal/pos_window.py` contains the main window, POS terminal, background sync, realtime sync, theme toggle, and receipt flow.
- `product_management/` handles products, barcodes, images, label printing, and sync retry.
- `ui/theme.py` supports the runtime light/dark theme.
- After major runtime or build changes, update `Progress/`, `BUILD_EXE.md`, `README_SETUP.md`, `requirements.txt`, `setup.ps1`, and `TODO.md` when relevant.
#Created by Truong Quang Nghia, David Nghia SWUST
