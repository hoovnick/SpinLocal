"""
SpinLocal Background Launcher
Starts guardian.py and watchdog.py as hidden background processes with no
console windows. Output is redirected to data/guardian.log and data/watchdog.log.

Called by start_silent.vbs (which Task Scheduler runs at logon).
For debugging with visible windows, use run_all.bat instead.

Windows only — relies on CREATE_NO_WINDOW process flag.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)

CREATE_NO_WINDOW = 0x08000000

def open_log(name: str):
    path = DATA / name
    f = open(path, "a", encoding="utf-8")
    f.write(f"\n{'='*60}\n[Launcher] Started at {datetime.now()}\n{'='*60}\n")
    f.flush()
    return f

guardian_log = open_log("guardian.log")
watchdog_log = open_log("watchdog.log")

subprocess.Popen(
    [sys.executable, str(BASE / "guardian.py")],
    stdout=guardian_log,
    stderr=guardian_log,
    cwd=str(BASE),
    creationflags=CREATE_NO_WINDOW,
)

subprocess.Popen(
    [sys.executable, str(BASE / "watchdog.py")],
    stdout=watchdog_log,
    stderr=watchdog_log,
    cwd=str(BASE),
    creationflags=CREATE_NO_WINDOW,
)

print("SpinLocal started in background.")
print(f"  Guardian log: {DATA / 'guardian.log'}")
print(f"  Watchdog log: {DATA / 'watchdog.log'}")
print(f"  Bot log:      {DATA / 'bot.log'}")
