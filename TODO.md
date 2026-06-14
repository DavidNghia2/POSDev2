# Retail POS TODO

Cap nhat: 2026-06-14

## Current status

- [x] Python + PyQt6 desktop POS shell
- [x] Supabase login/register store owner
- [x] Local SQLite cache under `%LOCALAPPDATA%\RetailPOS\pos.db`
- [x] Product sync with Supabase, Storage image upload/download, retry status
- [x] Checkout through Supabase `checkout_sale` RPC
- [x] Admin-only offline checkout pending sync
- [x] Background sync timer and realtime dirty-event sync
- [x] User/register sync from Supabase
- [x] Light/dark runtime theme toggle
- [x] Inno Setup installer script and build scripts
