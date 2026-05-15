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

The app uses `pos.db` in the project folder. Product Management and POS Terminal both read and write products through the same SQLite database.

The app logo is stored at `assets/app_logo.png`; keep that file in the project when copying or packaging the app.

Under `Progress`, I've listed everything completed for the project. If you work on something, please update it there. Also, make sure to sync the data on GitHub first before uploading your local changes.
