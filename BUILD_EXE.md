# Build Retail POS EXE And Installer

## Build portable EXE

Chay trong PowerShell tai thu muc project:

```powershell
.\build_exe.ps1
```

File portable se nam o:

```text
dist\RetailPOS\RetailPOS.exe
```

Ban build chi dong goi cac asset bat buoc:

```text
assets\app_logo.png
assets\ui_check.svg
assets\ui_chevron_down.svg
assets\ui_radio_dot.svg
assets\ui_radio_dot_muted.svg
```

Thu muc `assets\products` va anh demo/QR thua khong duoc nhet vao exe/installer. Cac anh san pham that se lay tu Supabase/cache runtime sau khi app chay.

Voi ban portable, copy `.env` vao cung thu muc voi `RetailPOS.exe` neu may khong co bien moi truong Supabase:

```text
dist\RetailPOS\.env
```

## Build installer dung duoc ngay

Installer se dong goi `.env` hien tai cua may build vao thu muc cai dat, nen nguoi dung khong can copy `.env` thu cong.
Installer su dung output tu `build_exe.ps1`, vi vay no cung khong dong goi `assets\products`.

Neu chua co Inno Setup, cai bang:

```powershell
winget install JRSoftware.InnoSetup
```

Sau do build installer:

```powershell
.\build_installer.ps1
```

Output:

```text
installer\Output\RetailPOSSetup.exe
```

Installer cai theo current user vao:

```text
%LOCALAPPDATA%\Programs\RetailPOS
```

## Supabase config

File `.env` tren may build can co:

```env
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
```

Chi dung `SUPABASE_ANON_KEY`. Khong bao gio dong goi service-role key vao desktop app hoac installer.

Khong copy `pos.db` vao ban build. App tu tao runtime database o:

```text
%LOCALAPPDATA%\RetailPOS\pos.db
```

Khong bat `ENABLE_DEMO_SEED=true` trong `.env` cua installer neu ban da loai `assets\products`, vi demo catalog co tham chieu anh trong thu muc do.

## Build thanh mot file exe duy nhat

```powershell
.\build_exe.ps1 -OneFile
```

Output:

```text
dist\RetailPOS.exe
```

Ban one-file se khoi dong cham hon mot chut vi PyInstaller can giai nen file tam moi lan chay.
