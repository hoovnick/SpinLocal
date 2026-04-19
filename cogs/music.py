import asyncio
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

import config


def has_dj_role():
    async def predicate(ctx):
        role = discord.utils.get(ctx.author.roles, name=config.DJ_ROLE_NAME)
        if role is None:
            await ctx.send(f"You need the **{config.DJ_ROLE_NAME}** role to use music commands.")
            return False
        return True
    return commands.check(predicate)


@dataclass
class GuildState:
    queue: list[Path] = field(default_factory=list)
    current: Optional[Path] = None
    volume: float = config.DEFAULT_VOLUME
    loop: bool = False
    loop_source: list[Path] = field(default_factory=list)  # tracks to refill from when queue empties
    loop_shuffle: bool = False                              # shuffle each refill
    voice_client: Optional[discord.VoiceClient] = None


def _find_songs(query: str) -> list[Path]:
    results = []
    query_lower = query.lower()
    for ext in config.SUPPORTED_EXTENSIONS:
        for p in config.MUSIC_ROOT.rglob(f"*{ext}"):
            if query_lower in p.stem.lower():
                results.append(p)
    return sorted(results, key=lambda p: p.stem.lower())


def _get_category_songs(category: str) -> list[Path]:
    cat_path = config.MUSIC_ROOT / category
    if not cat_path.is_dir():
        return []
    songs = []
    for ext in config.SUPPORTED_EXTENSIONS:
        songs.extend(cat_path.rglob(f"*{ext}"))
    return sorted(songs, key=lambda p: p.stem.lower())


def _get_categories() -> list[str]:
    return sorted(
        [d.name for d in config.MUSIC_ROOT.iterdir() if d.is_dir()],
        key=str.lower,
    )


class MusicCog(commands.Cog, name="Music"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._states: dict[int, GuildState] = {}

    def _state(self, guild_id: int) -> GuildState:
        if guild_id not in self._states:
            self._states[guild_id] = GuildState()
        return self._states[guild_id]

    async def _get_voice_client(self, ctx: commands.Context) -> Optional[discord.VoiceClient]:
        state = self._state(ctx.guild.id)
        if state.voice_client and state.voice_client.is_connected():
            return state.voice_client

        if ctx.author.voice is None:
            await ctx.send("You need to be in a voice channel.")
            return None

        vc = await ctx.author.voice.channel.connect(timeout=30.0, reconnect=True)
        state.voice_client = vc
        return vc

    def _play_track(self, vc: discord.VoiceClient, state: GuildState, ctx: commands.Context):
        if state.current is None:
            return

        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(str(state.current), **config.FFMPEG_OPTIONS),
            volume=state.volume,
        )

        def after_callback(error):
            if error:
                print(f"[SpinLocal] Player error: {error}")
            coro = self._advance(ctx)
            fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            try:
                fut.result()
            except Exception as e:
                print(f"[SpinLocal] After-callback error: {e}")

        vc.play(source, after=after_callback)

    async def _advance(self, ctx: commands.Context):
        state = self._state(ctx.guild.id)
        vc = state.voice_client

        if vc is None or not vc.is_connected():
            return

        if state.loop and state.current is not None:
            self._play_track(vc, state, ctx)
            return

        # Refill queue from loop source when it empties
        if not state.queue and state.loop_source:
            refill = list(state.loop_source)
            if state.loop_shuffle:
                random.shuffle(refill)
            state.queue.extend(refill)
            mode = "shuffled" if state.loop_shuffle else "in order"
            await ctx.send(f"Looping ({mode}) — {len(refill)} tracks")

        if state.queue:
            state.current = state.queue.pop(0)
            await ctx.send(f"Now playing: **{state.current.stem}**")
            self._play_track(vc, state, ctx)
        else:
            state.current = None
            await ctx.send("Queue finished.")

    # ── Join / Leave ──────────────────────────────────────────────────────────

    @commands.command()
    @has_dj_role()
    async def join(self, ctx: commands.Context):
        """Join your current voice channel."""
        vc = await self._get_voice_client(ctx)
        if vc:
            await ctx.send(f"Joined **{vc.channel.name}**.")

    @commands.command()
    @has_dj_role()
    async def leave(self, ctx: commands.Context):
        """Disconnect from voice."""
        state = self._state(ctx.guild.id)
        vc = state.voice_client
        if vc and vc.is_connected():
            if vc.is_playing() or vc.is_paused():
                vc.stop()
            await asyncio.sleep(0.3)
            await vc.disconnect(force=False)
            state.voice_client = None
            state.current = None
            state.queue.clear()
            await ctx.send("Disconnected.")
        else:
            await ctx.send("I'm not in a voice channel.")

    # ── Playback ──────────────────────────────────────────────────────────────

    @commands.command()
    @has_dj_role()
    async def play(self, ctx: commands.Context, *, query: str):
        """Search for a song and queue it (plays first match)."""
        matches = _find_songs(query)
        if not matches:
            await ctx.send(f"No songs found matching **{query}**.")
            return

        vc = await self._get_voice_client(ctx)
        if vc is None:
            return

        state = self._state(ctx.guild.id)
        song = matches[0]

        if vc.is_playing() or vc.is_paused():
            state.queue.append(song)
            await ctx.send(f"Queued: **{song.stem}** (position {len(state.queue)})")
        else:
            state.current = song
            await ctx.send(f"Now playing: **{song.stem}**")
            self._play_track(vc, state, ctx)

    @commands.command()
    @has_dj_role()
    async def playnext(self, ctx: commands.Context, *, query: str):
        """Add a song to play immediately after the current track."""
        matches = _find_songs(query)
        if not matches:
            await ctx.send(f"No songs found matching **{query}**.")
            return

        vc = await self._get_voice_client(ctx)
        if vc is None:
            return

        state = self._state(ctx.guild.id)
        song = matches[0]

        if vc.is_playing() or vc.is_paused():
            state.queue.insert(0, song)
            await ctx.send(f"Up next: **{song.stem}** (inserted at position 1)")
        else:
            state.current = song
            await ctx.send(f"Now playing: **{song.stem}**")
            self._play_track(vc, state, ctx)

    @commands.command()
    @has_dj_role()
    async def playcat(self, ctx: commands.Context, *, category: str):
        """Queue all songs from a category folder."""
        songs = _get_category_songs(category)
        if not songs:
            cats = ", ".join(_get_categories())
            await ctx.send(f"Category **{category}** not found. Available: {cats}")
            return

        vc = await self._get_voice_client(ctx)
        if vc is None:
            return

        state = self._state(ctx.guild.id)

        if vc.is_playing() or vc.is_paused():
            state.queue.extend(songs)
            await ctx.send(f"Queued **{len(songs)}** songs from **{category}**.")
        else:
            state.current = songs[0]
            state.queue.extend(songs[1:])
            await ctx.send(f"Playing **{len(songs)}** songs from **{category}**. First: **{songs[0].stem}**")
            self._play_track(vc, state, ctx)

    @commands.command()
    @has_dj_role()
    async def loopcat(self, ctx: commands.Context, *, category: str):
        """Loop a category continuously in order. Use !stop to end."""
        songs = _get_category_songs(category)
        if not songs:
            cats = ", ".join(_get_categories())
            await ctx.send(f"Category **{category}** not found. Available: {cats}")
            return

        vc = await self._get_voice_client(ctx)
        if vc is None:
            return

        state = self._state(ctx.guild.id)
        if vc.is_playing() or vc.is_paused():
            vc.stop()

        state.loop_source = list(songs)
        state.loop_shuffle = False
        state.queue = list(songs[1:])
        state.current = songs[0]
        await ctx.send(
            f"Looping **{category}** in order — {len(songs)} tracks. Use `!loopoff` or `!stop` to end."
        )
        self._play_track(vc, state, ctx)

    @commands.command()
    @has_dj_role()
    async def shuffleloop(self, ctx: commands.Context, *, category: str):
        """Continuously shuffle-loop a category. Re-shuffles every pass. Use !stop to end."""
        songs = _get_category_songs(category)
        if not songs:
            cats = ", ".join(_get_categories())
            await ctx.send(f"Category **{category}** not found. Available: {cats}")
            return

        vc = await self._get_voice_client(ctx)
        if vc is None:
            return

        state = self._state(ctx.guild.id)
        if vc.is_playing() or vc.is_paused():
            vc.stop()

        first_pass = list(songs)
        random.shuffle(first_pass)
        state.loop_source = list(songs)
        state.loop_shuffle = True
        state.queue = list(first_pass[1:])
        state.current = first_pass[0]
        await ctx.send(
            f"Shuffle-looping **{category}** — {len(songs)} tracks, re-shuffled each pass. Use `!loopoff` or `!stop` to end."
        )
        self._play_track(vc, state, ctx)

    @commands.command()
    @has_dj_role()
    async def loopoff(self, ctx: commands.Context):
        """Stop looping after the current queue finishes (does not cut playback)."""
        state = self._state(ctx.guild.id)
        if not state.loop_source:
            await ctx.send("No queue loop is active.")
            return
        state.loop_source.clear()
        state.loop_shuffle = False
        await ctx.send("Queue loop disabled — will stop after the current queue finishes.")

    @commands.command()
    @has_dj_role()
    async def skip(self, ctx: commands.Context):
        """Skip the current track."""
        state = self._state(ctx.guild.id)
        vc = state.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            was_looping = state.loop
            state.loop = False
            vc.stop()
            state.loop = was_looping
            await ctx.send("Skipped.")
        else:
            await ctx.send("Nothing is playing.")

    @commands.command()
    @has_dj_role()
    async def stop(self, ctx: commands.Context):
        """Stop playback and clear the queue."""
        state = self._state(ctx.guild.id)
        vc = state.voice_client
        state.queue.clear()
        state.loop_source.clear()
        state.loop_shuffle = False
        state.current = None
        state.loop = False
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        await ctx.send("Stopped and queue cleared.")

    @commands.command()
    @has_dj_role()
    async def pause(self, ctx: commands.Context):
        """Pause playback."""
        state = self._state(ctx.guild.id)
        vc = state.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("Paused.")
        else:
            await ctx.send("Nothing is playing.")

    @commands.command()
    @has_dj_role()
    async def resume(self, ctx: commands.Context):
        """Resume paused playback."""
        state = self._state(ctx.guild.id)
        vc = state.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("Resumed.")
        else:
            await ctx.send("Nothing is paused.")

    @commands.command()
    @has_dj_role()
    async def volume(self, ctx: commands.Context, vol: int):
        """Set volume 0-100."""
        if not 0 <= vol <= 100:
            await ctx.send("Volume must be between 0 and 100.")
            return
        state = self._state(ctx.guild.id)
        state.volume = vol / 100
        vc = state.voice_client
        if vc and vc.source:
            vc.source.volume = state.volume
        await ctx.send(f"Volume set to **{vol}%**.")

    @commands.command()
    @has_dj_role()
    async def loop(self, ctx: commands.Context):
        """Toggle looping the current track."""
        state = self._state(ctx.guild.id)
        state.loop = not state.loop
        status = "enabled" if state.loop else "disabled"
        await ctx.send(f"Loop {status}.")

    @commands.command()
    @has_dj_role()
    async def shuffle(self, ctx: commands.Context):
        """Shuffle the current queue."""
        state = self._state(ctx.guild.id)
        if not state.queue:
            await ctx.send("Queue is empty.")
            return
        random.shuffle(state.queue)
        await ctx.send(f"Queue shuffled ({len(state.queue)} tracks).")

    @commands.command()
    @has_dj_role()
    async def clear(self, ctx: commands.Context):
        """Clear the queue without stopping current track."""
        state = self._state(ctx.guild.id)
        state.queue.clear()
        await ctx.send("Queue cleared.")

    @commands.command()
    @has_dj_role()
    async def remove(self, ctx: commands.Context, position: int):
        """Remove a song from the queue by position. Usage: !remove <number>"""
        state = self._state(ctx.guild.id)
        if not state.queue:
            await ctx.send("Queue is empty.")
            return
        if position < 1 or position > len(state.queue):
            await ctx.send(f"Invalid position. Queue has {len(state.queue)} track(s).")
            return
        removed = state.queue.pop(position - 1)
        await ctx.send(f"Removed **{removed.stem}** from position {position}.")

    # ── Info ──────────────────────────────────────────────────────────────────

    @commands.command(aliases=["np"])
    async def nowplaying(self, ctx: commands.Context):
        """Show the currently playing track."""
        state = self._state(ctx.guild.id)
        if state.current:
            loop_indicator = " [LOOP]" if state.loop else ""
            loop_queue = " [QUEUE LOOP]" if state.loop_source else ""
            queue_len = len(state.queue)
            await ctx.send(
                f"Now playing: **{state.current.stem}**{loop_indicator}{loop_queue}\n"
                f"Category: `{state.current.parent.name}` | "
                f"Up next: {queue_len} track(s) in queue"
            )
        else:
            await ctx.send("Nothing is playing right now.")

    @commands.command(aliases=["q"])
    async def queue(self, ctx: commands.Context):
        """Show the current queue."""
        state = self._state(ctx.guild.id)
        if not state.queue and not state.current:
            await ctx.send("Queue is empty.")
            return

        lines = []
        if state.current:
            tags = ""
            if state.loop:
                tags += " [LOOP]"
            if state.loop_source:
                tags += f" [QUEUE LOOP{'~SHUFFLE' if state.loop_shuffle else ''}]"
            lines.append(f"**Now:** {state.current.stem}{tags}")

        page = state.queue[:15]
        for i, track in enumerate(page, 1):
            lines.append(f"`{i}.` {track.stem}")
        if len(state.queue) > 15:
            lines.append(f"... and {len(state.queue) - 15} more")

        await ctx.send("\n".join(lines))

    @commands.command()
    async def search(self, ctx: commands.Context, *, query: str):
        """Search for songs matching a term."""
        matches = _find_songs(query)
        if not matches:
            await ctx.send(f"No songs found matching **{query}**.")
            return
        lines = [f"`{i}.` {m.stem} — `{m.parent.name}`" for i, m in enumerate(matches[:20], 1)]
        if len(matches) > 20:
            lines.append(f"... and {len(matches) - 20} more results")
        await ctx.send("\n".join(lines))

    @commands.command(name="list")
    async def list_music(self, ctx: commands.Context, *, category: str = None):
        """List categories or songs in a category."""
        if category is None:
            cats = _get_categories()
            if not cats:
                await ctx.send(f"No music found. Add folders to: `{config.MUSIC_ROOT}`")
                return
            await ctx.send("**Music categories:**\n" + "\n".join(f"  `{c}`" for c in cats))
        else:
            songs = _get_category_songs(category)
            if not songs:
                await ctx.send(f"Category **{category}** not found.")
                return
            lines = [f"`{i}.` {s.stem}" for i, s in enumerate(songs[:30], 1)]
            if len(songs) > 30:
                lines.append(f"... and {len(songs) - 30} more")
            await ctx.send(f"**{category}** ({len(songs)} tracks):\n" + "\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
