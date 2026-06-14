# Build Retail POS EXE And Installer

Updated: 2026-06-14

This document describes the current build flow for the project. The app is a Python + PyQt6 desktop POS that signs in and syncs through Supabase, while SQLite is used on the user's machine as a local cache and offline store.

## 1. Prepare the environment

Run this in PowerShell from the project folder:

```powershell
.\setup.ps1
```

By default, the script creates `.venv` with Python 3.12 and installs the dependencies from `requirements.txt`. If Python 3.12 is not available:

```powershell
.\setup.ps1 -PythonVersion 3.11
```

The root `.env` file must contain:

```env
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
```

Use only the anon public key. Never put a service-role key in the desktop app, `.env`, EXE, or installer.

## 2. Build the portable EXE

```powershell
.\build_exe.ps1
```

Output:

```text
dist\RetailPOS\RetailPOS.exe
```

This command:

- verifies the code with `compileall`
- creates `assets\app_logo.ico` from `assets\app_logo.png`
- builds a folder-based PyInstaller app
- bundles the main runtime modules: `main.py`, `app_paths.py`, `admin`, `cloud`, `database`, `login`, `pos_terminal`, `product_management`, `ui`
- bundles the Supabase packages needed for Auth, Database, Realtime, Storage, and Edge Functions
- includes only the required UI assets

Bundled assets:

```text
assets\app_logo.png
assets\ui_check.svg
assets\ui_chevron_down.svg
assets\ui_radio_dot.svg
assets\ui_radio_dot_muted.svg
```

`assets\products` is not packaged into the EXE or installer. Real product images are synced from Supabase Storage and cached at runtime under `%LOCALAPPDATA%\RetailPOS\cache`.

For the portable build, copy `.env` next to `RetailPOS.exe` if the target machine does not define Supabase environment variables:

```text
dist\RetailPOS\.env
```

## 3. Build a one-file EXE

```powershell
.\build_exe.ps1 -OneFile
```

Output:

```text
dist\RetailPOS.exe
```

The one-file build starts more slowly because PyInstaller extracts temporary files every time it runs. The current installer uses the folder build under `dist\RetailPOS`, not the one-file build.

## 4. Build the installer with Inno Setup

If Inno Setup is not installed:

```powershell
winget install JRSoftware.InnoSetup
```

Build the installer:

```powershell
.\build_installer.ps1
```

Output:

```text
installer\Output\RetailPOSSetup.exe
```

This command rebuilds the EXE from the current saved source code before calling Inno Setup. Any saved code changes are included in the installer.

Only this command skips rebuilding the code:

```powershell
.\build_installer.ps1 -SkipPyInstallerBuild
```

The installer installs for the current Windows user at:

```text
%LOCALAPPDATA%\Programs\RetailPOS
```

The installer copies the current build machine `.env` file into the install folder so the app can run immediately. Review `.env` before building and make sure it contains only safe client configuration.

## 5. Runtime data

Do not copy `pos.db` into the build. The app creates the runtime database at:

```text
%LOCALAPPDATA%\RetailPOS\pos.db
```

Supabase is the source of truth for cloud stores. Local SQLite is used for cache data, pending offline sales, sessions, settings, and fast local display.

For development, the database path can be overridden in `.env`:

```env
POS_DB_PATH=pos.dev.db
```

Do not enable demo seed data for production builds when `assets\products` is not packaged.

## 6. Supabase requirements before production builds

The Supabase project must have its schema and functions deployed according to `supabase/SETUP_NEW_PROJECT.md`.

Required backend pieces:

- product, sale, user, and register tables from the migrations
- RPC `checkout_sale`
- owner/profile repair RPC helpers
- Edge Functions `admin-create-user` and `admin-update-user`
- Storage bucket `product-images`
- Realtime enabled for the data that should sync back to the desktop app

## 7. Common commands

Set up the environment:

```powershell
.\setup.ps1
```

Run from source:

```powershell
.\.venv\Scripts\python.exe main.py
```

Build the folder EXE:

```powershell
.\build_exe.ps1
```

Build the full installer:

```powershell
.\build_installer.ps1
```





#Created by Truong Quang Nghia, David Nghia SWUST