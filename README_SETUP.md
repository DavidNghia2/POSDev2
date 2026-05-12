# POS App Setup

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

Under 'Progress,' I've listed everything I’ve completed for the project. If you work on something, please update it there. Also, make sure to sync the data on GitHub first before uploading your local changes.
