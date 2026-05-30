#!/usr/bin/env python
"""Worker entrypoint — runs Django migrations then starts background task processor."""
import os
import subprocess
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

print("=== DTC-Brightbean Worker Starting ===", flush=True)

print("[1/2] Running migrations...", flush=True)
result = subprocess.run(
    [sys.executable, "manage.py", "migrate", "--noinput"],
    check=True,
)
print(f"[1/2] Migrations complete (exit {result.returncode})", flush=True)

print("[2/2] Starting process_tasks...", flush=True)
sys.exit(
    subprocess.run([sys.executable, "manage.py", "process_tasks"]).returncode
)

