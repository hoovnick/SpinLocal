"""
SpinLocal Guardian
A tiny, separate Discord bot that gives your partner a way to restart
SpinLocal from Discord when it freezes. Runs independently of the main bot
so it stays responsive even when SpinLocal's event loop is frozen.

Requires its own Discord bot token (GUARDIAN_TOKEN in .env).
Set GUARDIAN_CHANNEL_ID to lock the command to a private channel.

Usage: python guardian.py  (or let run_all.bat / launcher.py handle it)
Command: !spinrestart  (in the configured channel)
"""

import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

GUARDIAN_TOKEN      = os.getenv("GUARDIAN_TOKEN", "")
GUARDIAN_CHANNEL_ID = int(os.getenv("GUARDIAN_CHANNEL_ID", "0"))
RESTART_FLAG        = Path(__file__).parent / "data" / "restart.flag"

if not GUARDIAN_TOKEN:
    print("[Guardian] GUARDIAN_TOKEN not set in .env — guardian will not start.")
    print("[Guardian] Set GUARDIAN_TOKEN in your .env file to enable remote restart.")
    raise SystemExit(0)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"[Guardian] Online as {bot.user}", flush=True)
    if GUARDIAN_CHANNEL_ID:
        print(f"[Guardian] Listening for !spinrestart in channel {GUARDIAN_CHANNEL_ID}", flush=True)
    else:
        print("[Guardian] Warning: GUARDIAN_CHANNEL_ID not set — !spinrestart works in any channel.", flush=True)


@bot.command()
async def spinrestart(ctx: commands.Context):
    """Signal the watchdog to restart SpinLocal."""
    if GUARDIAN_CHANNEL_ID and ctx.channel.id != GUARDIAN_CHANNEL_ID:
        return

    RESTART_FLAG.parent.mkdir(exist_ok=True)
    RESTART_FLAG.touch()
    await ctx.send(
        "🔄 SpinLocal restart triggered. Bot should be back in **30–60 seconds**.\n"
        "Use `!ping` on SpinLocal to confirm it's back."
    )
    print(f"[Guardian] Restart flagged by {ctx.author}", flush=True)


@bot.command()
async def guardianping(ctx: commands.Context):
    """Check that the guardian itself is alive."""
    await ctx.send("Guardian is online ✅")


bot.run(GUARDIAN_TOKEN)
