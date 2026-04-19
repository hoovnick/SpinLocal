import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix=os.getenv("COMMAND_PREFIX", "!"), intents=intents)


@bot.event
async def on_ready():
    print(f"SpinLocal online as {bot.user} (ID: {bot.user.id})")
    print(f"discord.py version: {discord.__version__}")
    print("------")


@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! Latency: {round(bot.latency * 1000)}ms")


async def main():
    async with bot:
        await bot.load_extension("cogs.music")
        await bot.load_extension("cogs.playlists")
        token = os.getenv("DISCORD_TOKEN")
        if not token or token == "your_discord_bot_token_here":
            print("ERROR: Add your DISCORD_TOKEN to the .env file and restart.")
            return
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
