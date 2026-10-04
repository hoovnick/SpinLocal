"""
SpinLocal Watchdog
Manages the bot process. Auto-restarts if:
  - The process crashes/exits unexpectedly
  - The heartbeat file goes stale (event loop frozen)
  - guardian.py drops a restart.flag file (manual Discord restart)

Run this instead of bot.py directly. Use run_all.bat on Windows.
"""

import sys
import time
import subprocess
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR      = Path(__file__).parent
BOT_SCRIPT    = BASE_DIR / "bot.py"
HEARTBEAT     = BASE_DIR / "data" / "heartbeat.txt"
RESTART_FLAG  = BASE_DIR / "data" / "restart.flag"
PID_FILE      = BASE_DIR / "data" / "bot.pid"

CHECK_INTERVAL = 60   # seconds between watchdog checks
MAX_STALE      = 90   # seconds before a stale heartbeat triggers restart

# ── Process management ────────────────────────────────────────────────────────

bot_proc: subprocess.Popen | None = None


def start_bot():
    global bot_proc
    HEARTBEAT.unlink(missing_ok=True)

    bot_log = open(BASE_DIR / "data" / "bot.log", "a", encoding="utf-8")
    from datetime import datetime
    bot_log.write(f"\n{'='*60}\n[Watchdog] Bot (re)started at {datetime.now()}\n{'='*60}\n")
    bot_log.flush()

    bot_proc = subprocess.Popen(
        [sys.executable, str(BOT_SCRIPT)],
        cwd=str(BASE_DIR),
        stdout=bot_log,
        stderr=bot_log,
    )
    PID_FILE.write_text(str(bot_proc.pid))
    print(f"[Watchdog] Bot started — PID {bot_proc.pid}", flush=True)

    time.sleep(5)
    if bot_proc.poll() is not None:
        print(f"[Watchdog] Bot exited immediately (code {bot_proc.returncode}) — check data/bot.log for details.", flush=True)
        bot_proc = None


def kill_bot():
    global bot_proc
    if bot_proc and bot_proc.poll() is None:
        print("[Watchdog] Terminating bot process...", flush=True)
        bot_proc.terminate()
        try:
            bot_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            bot_proc.kill()
            bot_proc.wait()
    bot_proc = None
    PID_FILE.unlink(missing_ok=True)


def restart_bot(reason: str):
    print(f"[Watchdog] Restarting — {reason}", flush=True)
    kill_bot()
    time.sleep(2)
    start_bot()


# ── Main loop ─────────────────────────────────────────────────────────────────

Path("data").mkdir(exist_ok=True)
start_bot()

print("[Watchdog] Running. Ctrl+C to stop everything.", flush=True)

try:
    while True:
        time.sleep(CHECK_INTERVAL)

        if RESTART_FLAG.exists():
            RESTART_FLAG.unlink(missing_ok=True)
            restart_bot("manual restart requested via Discord")
            continue

        if bot_proc is None or bot_proc.poll() is not None:
            restart_bot("bot process exited unexpectedly")
            continue

        if HEARTBEAT.exists():
            try:
                age = time.time() - float(HEARTBEAT.read_text().strip())
                if age > MAX_STALE:
                    restart_bot(f"heartbeat stale ({age:.0f}s — event loop frozen)")
            except (ValueError, OSError):
                pass

except KeyboardInterrupt:
    print("\n[Watchdog] Shutting down...", flush=True)
    kill_bot()
    print("[Watchdog] Goodbye.", flush=True)
