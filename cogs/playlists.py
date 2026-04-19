import random
import sqlite3
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

import config


# ── Database helpers ──────────────────────────────────────────────────────────

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL COLLATE NOCASE,
                created_by TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS playlist_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                filepath TEXT NOT NULL,
                position INTEGER NOT NULL
            );
        """)


def _get_playlist_id(name: str) -> Optional[int]:
    with _db() as conn:
        row = conn.execute("SELECT id FROM playlists WHERE name = ?", (name,)).fetchone()
        return row["id"] if row else None


def _get_playlist_name(pid: int) -> Optional[str]:
    with _db() as conn:
        row = conn.execute("SELECT name FROM playlists WHERE id = ?", (pid,)).fetchone()
        return row["name"] if row else None


def _get_tracks(pid: int) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, filepath FROM playlist_tracks WHERE playlist_id = ? ORDER BY position", (pid,)
        ).fetchall()
    return [{"id": r["id"], "filepath": r["filepath"], "stem": Path(r["filepath"]).stem} for r in rows]


def _find_song(query: str) -> Optional[Path]:
    query_lower = query.lower()
    for ext in config.SUPPORTED_EXTENSIONS:
        for p in config.MUSIC_ROOT.rglob(f"*{ext}"):
            if query_lower in p.stem.lower():
                return p
    return None


def _reorder(pid: int, track_ids: list[int]):
    with _db() as conn:
        for i, tid in enumerate(track_ids, 1):
            conn.execute("UPDATE playlist_tracks SET position = ? WHERE id = ?", (i, tid))


def _build_embed(pid: int) -> discord.Embed:
    name = _get_playlist_name(pid) or "Playlist"
    tracks = _get_tracks(pid)
    embed = discord.Embed(title=f"Editing: {name}", color=discord.Color.blurple())
    if tracks:
        lines = [f"`{i}.` {t['stem']}" for i, t in enumerate(tracks[:25], 1)]
        if len(tracks) > 25:
            lines.append(f"*...and {len(tracks) - 25} more*")
        embed.description = "\n".join(lines)
    else:
        embed.description = "*Empty playlist*"
    embed.set_footer(text=f"{len(tracks)} track(s)")
    return embed


# ── Modals ────────────────────────────────────────────────────────────────────

class AddSongModal(discord.ui.Modal, title="Add Song"):
    query = discord.ui.TextInput(label="Song name (or partial)", placeholder="e.g. Take the Sea", max_length=100)

    def __init__(self, pid: int, view: "PlaylistEditorView"):
        super().__init__()
        self.pid = pid
        self.editor_view = view

    async def on_submit(self, interaction: discord.Interaction):
        song = _find_song(self.query.value)
        if song is None:
            await interaction.response.send_message(
                f"No song found matching **{self.query.value}**.", ephemeral=True
            )
            return
        with _db() as conn:
            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), 0) FROM playlist_tracks WHERE playlist_id = ?", (self.pid,)
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO playlist_tracks (playlist_id, filepath, position) VALUES (?, ?, ?)",
                (self.pid, str(song), max_pos + 1),
            )
        await interaction.response.edit_message(embed=_build_embed(self.pid), view=self.editor_view)
        await interaction.followup.send(f"Added **{song.stem}**.", ephemeral=True)


class RenameModal(discord.ui.Modal, title="Rename Playlist"):
    new_name = discord.ui.TextInput(label="New name", max_length=50)

    def __init__(self, pid: int, view: "PlaylistEditorView"):
        super().__init__()
        self.pid = pid
        self.editor_view = view

    async def on_submit(self, interaction: discord.Interaction):
        new = self.new_name.value.strip()
        try:
            with _db() as conn:
                conn.execute("UPDATE playlists SET name = ? WHERE id = ?", (new, self.pid))
            self.editor_view.playlist_name = new
            await interaction.response.edit_message(embed=_build_embed(self.pid), view=self.editor_view)
            await interaction.followup.send(f"Renamed to **{new}**.", ephemeral=True)
        except sqlite3.IntegrityError:
            await interaction.response.send_message(
                f"A playlist named **{new}** already exists.", ephemeral=True
            )


class MoveTrackModal(discord.ui.Modal, title="Move Track"):
    from_pos = discord.ui.TextInput(label="Move FROM position", placeholder="e.g. 3", max_length=4)
    to_pos = discord.ui.TextInput(label="Move TO position", placeholder="e.g. 1", max_length=4)

    def __init__(self, pid: int, view: "PlaylistEditorView"):
        super().__init__()
        self.pid = pid
        self.editor_view = view

    async def on_submit(self, interaction: discord.Interaction):
        tracks = _get_tracks(self.pid)
        count = len(tracks)
        try:
            frm = int(self.from_pos.value)
            to = int(self.to_pos.value)
        except ValueError:
            await interaction.response.send_message("Positions must be numbers.", ephemeral=True)
            return
        if not (1 <= frm <= count) or not (1 <= to <= count):
            await interaction.response.send_message(
                f"Positions must be between 1 and {count}.", ephemeral=True
            )
            return
        if frm == to:
            await interaction.response.send_message("Nothing to move.", ephemeral=True)
            return
        ids = [t["id"] for t in tracks]
        moved_id = ids.pop(frm - 1)
        moved_name = tracks[frm - 1]["stem"]
        ids.insert(to - 1, moved_id)
        _reorder(self.pid, ids)
        await interaction.response.edit_message(embed=_build_embed(self.pid), view=self.editor_view)
        await interaction.followup.send(
            f"Moved **{moved_name}** from position {frm} to {to}.", ephemeral=True
        )


# ── Remove Select ─────────────────────────────────────────────────────────────

class RemoveSelect(discord.ui.Select):
    def __init__(self, pid: int, tracks: list[dict], view: "PlaylistEditorView"):
        self.pid = pid
        self.editor_view = view
        options = [
            discord.SelectOption(label=f"{i}. {t['stem'][:95]}", value=str(t["id"]))
            for i, t in enumerate(tracks[:25], 1)
        ]
        super().__init__(placeholder="Select a track to remove...", options=options)

    async def callback(self, interaction: discord.Interaction):
        track_id = int(self.values[0])
        with _db() as conn:
            row = conn.execute("SELECT filepath FROM playlist_tracks WHERE id = ?", (track_id,)).fetchone()
            if row:
                name = Path(row["filepath"]).stem
                conn.execute("DELETE FROM playlist_tracks WHERE id = ?", (track_id,))
        await interaction.response.edit_message(embed=_build_embed(self.pid), view=self.editor_view)
        await interaction.followup.send(f"Removed **{name}**.", ephemeral=True)


class RemoveView(discord.ui.View):
    def __init__(self, pid: int, tracks: list[dict], editor_view: "PlaylistEditorView"):
        super().__init__(timeout=60)
        self.add_item(RemoveSelect(pid, tracks, editor_view))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=None, embed=_build_embed(self.children[0].pid), view=self.children[0].editor_view
        )


# ── Main Editor View ──────────────────────────────────────────────────────────

class PlaylistEditorView(discord.ui.View):
    def __init__(self, pid: int, playlist_name: str, owner_id: int):
        super().__init__(timeout=300)
        self.pid = pid
        self.playlist_name = playlist_name
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the person who opened the editor can use it.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Add Song", style=discord.ButtonStyle.success, emoji="➕")
    async def add_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddSongModal(self.pid, self))

    @discord.ui.button(label="Remove Track", style=discord.ButtonStyle.danger, emoji="➖")
    async def remove_track(self, interaction: discord.Interaction, button: discord.ui.Button):
        tracks = _get_tracks(self.pid)
        if not tracks:
            await interaction.response.send_message("Playlist is empty.", ephemeral=True)
            return
        remove_view = RemoveView(self.pid, tracks, self)
        await interaction.response.edit_message(
            content="Select a track to remove:", embed=None, view=remove_view
        )

    @discord.ui.button(label="Move Track", style=discord.ButtonStyle.primary, emoji="↕️")
    async def move_track(self, interaction: discord.Interaction, button: discord.ui.Button):
        tracks = _get_tracks(self.pid)
        if len(tracks) < 2:
            await interaction.response.send_message("Need at least 2 tracks to reorder.", ephemeral=True)
            return
        await interaction.response.send_modal(MoveTrackModal(self.pid, self))

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RenameModal(self.pid, self))

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, emoji="✅", row=1)
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"Finished editing **{self.playlist_name}**.", embed=None, view=self
        )
        self.stop()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


# ── Cog ───────────────────────────────────────────────────────────────────────

class PlaylistCog(commands.Cog, name="Playlists"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        _init_db()

    @commands.group(invoke_without_command=True)
    async def playlist(self, ctx: commands.Context):
        """Playlist management. Use !playlist <subcommand>."""
        await ctx.send(
            "**Playlist commands:**\n"
            "`!playlist list` — show all playlists\n"
            "`!playlist create <name>` — create a playlist\n"
            "`!playlist edit <name>` — interactive editor (add/remove/move/rename)\n"
            "`!playlist show <name>` — list songs in a playlist\n"
            "`!playlist play <name>` — queue all songs\n"
            "`!playlist shuffle <name>` — play in random order\n"
            "`!playlist loop <name>` — loop playlist continuously in order\n"
            "`!playlist loopshuffle <name>` — shuffle-loop playlist (re-shuffles each pass)\n"
            "`!playlist delete <name>` — delete a playlist\n"
            "\n*Quick commands:*\n"
            "`!playlist rename <old> <new>` — rename\n"
            "`!playlist add <name> <song>` — add a song\n"
            "`!playlist remove <name> <song>` — remove a song\n"
            "`!playlist move <name> <pos> <newpos>` — reorder a track"
        )

    @playlist.command(name="list")
    async def playlist_list(self, ctx: commands.Context):
        """List all saved playlists."""
        with _db() as conn:
            rows = conn.execute(
                "SELECT p.name, COUNT(t.id) AS count "
                "FROM playlists p LEFT JOIN playlist_tracks t ON t.playlist_id = p.id "
                "GROUP BY p.id ORDER BY p.name COLLATE NOCASE"
            ).fetchall()
        if not rows:
            await ctx.send("No playlists saved yet. Use `!playlist create <name>` to make one.")
            return
        lines = [f"`{r['name']}` — {r['count']} track(s)" for r in rows]
        await ctx.send("**Saved playlists:**\n" + "\n".join(lines))

    @playlist.command(name="create")
    async def playlist_create(self, ctx: commands.Context, *, name: str):
        """Create a new playlist."""
        try:
            with _db() as conn:
                conn.execute(
                    "INSERT INTO playlists (name, created_by) VALUES (?, ?)",
                    (name, str(ctx.author)),
                )
            await ctx.send(f"Playlist **{name}** created. Open the editor with `!playlist edit {name}`.")
        except sqlite3.IntegrityError:
            await ctx.send(f"A playlist named **{name}** already exists.")

    @playlist.command(name="edit")
    async def playlist_edit(self, ctx: commands.Context, *, name: str):
        """Open the interactive playlist editor."""
        pid = _get_playlist_id(name)
        if pid is None:
            await ctx.send(f"Playlist **{name}** not found.")
            return
        view = PlaylistEditorView(pid, name, ctx.author.id)
        await ctx.send(embed=_build_embed(pid), view=view)

    @playlist.command(name="delete")
    async def playlist_delete(self, ctx: commands.Context, *, name: str):
        """Delete a playlist."""
        pid = _get_playlist_id(name)
        if pid is None:
            await ctx.send(f"Playlist **{name}** not found.")
            return
        with _db() as conn:
            conn.execute("DELETE FROM playlists WHERE id = ?", (pid,))
        await ctx.send(f"Playlist **{name}** deleted.")

    @playlist.command(name="show")
    async def playlist_show(self, ctx: commands.Context, *, name: str):
        """Show all songs in a playlist."""
        pid = _get_playlist_id(name)
        if pid is None:
            await ctx.send(f"Playlist **{name}** not found.")
            return
        tracks = _get_tracks(pid)
        if not tracks:
            await ctx.send(f"Playlist **{name}** is empty.")
            return
        lines = [f"`{i}.` {t['stem']}" for i, t in enumerate(tracks[:30], 1)]
        if len(tracks) > 30:
            lines.append(f"... and {len(tracks) - 30} more")
        await ctx.send(f"**{name}** ({len(tracks)} tracks):\n" + "\n".join(lines))

    @playlist.command(name="rename")
    async def playlist_rename(self, ctx: commands.Context, old: str, *, new: str):
        """Rename a playlist. Usage: !playlist rename <old> <new>"""
        pid = _get_playlist_id(old)
        if pid is None:
            await ctx.send(f"Playlist **{old}** not found.")
            return
        try:
            with _db() as conn:
                conn.execute("UPDATE playlists SET name = ? WHERE id = ?", (new, pid))
            await ctx.send(f"Renamed **{old}** to **{new}**.")
        except sqlite3.IntegrityError:
            await ctx.send(f"A playlist named **{new}** already exists.")

    @playlist.command(name="add")
    async def playlist_add(self, ctx: commands.Context, name: str, *, query: str):
        """Add a song to a playlist. Usage: !playlist add <name> <song>"""
        pid = _get_playlist_id(name)
        if pid is None:
            await ctx.send(f"Playlist **{name}** not found.")
            return
        song = _find_song(query)
        if song is None:
            await ctx.send(f"No song found matching **{query}**.")
            return
        with _db() as conn:
            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), 0) FROM playlist_tracks WHERE playlist_id = ?", (pid,)
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO playlist_tracks (playlist_id, filepath, position) VALUES (?, ?, ?)",
                (pid, str(song), max_pos + 1),
            )
        await ctx.send(f"Added **{song.stem}** to **{name}**.")

    @playlist.command(name="remove")
    async def playlist_remove(self, ctx: commands.Context, name: str, *, query: str):
        """Remove a song from a playlist by name. Usage: !playlist remove <name> <song>"""
        pid = _get_playlist_id(name)
        if pid is None:
            await ctx.send(f"Playlist **{name}** not found.")
            return
        query_lower = query.lower()
        tracks = _get_tracks(pid)
        match = next((t for t in tracks if query_lower in t["stem"].lower()), None)
        if match is None:
            await ctx.send(f"No track matching **{query}** found in **{name}**.")
            return
        with _db() as conn:
            conn.execute("DELETE FROM playlist_tracks WHERE id = ?", (match["id"],))
        await ctx.send(f"Removed **{match['stem']}** from **{name}**.")

    @playlist.command(name="move")
    async def playlist_move(self, ctx: commands.Context, name: str, position: int, new_position: int):
        """Move a track to a new position. Usage: !playlist move <name> <pos> <newpos>"""
        pid = _get_playlist_id(name)
        if pid is None:
            await ctx.send(f"Playlist **{name}** not found.")
            return
        tracks = _get_tracks(pid)
        count = len(tracks)
        if count == 0:
            await ctx.send(f"Playlist **{name}** is empty.")
            return
        if not (1 <= position <= count) or not (1 <= new_position <= count):
            await ctx.send(f"Positions must be between 1 and {count}.")
            return
        if position == new_position:
            await ctx.send("Nothing to move.")
            return
        ids = [t["id"] for t in tracks]
        moved_name = tracks[position - 1]["stem"]
        moved_id = ids.pop(position - 1)
        ids.insert(new_position - 1, moved_id)
        _reorder(pid, ids)
        await ctx.send(f"Moved **{moved_name}** from position {position} to {new_position}.")

    @playlist.command(name="play")
    async def playlist_play(self, ctx: commands.Context, *, name: str):
        """Queue all songs from a playlist."""
        await self._queue_playlist(ctx, name, shuffle=False, loop=False)

    @playlist.command(name="shuffle")
    async def playlist_shuffle(self, ctx: commands.Context, *, name: str):
        """Play a playlist in random order."""
        await self._queue_playlist(ctx, name, shuffle=True, loop=False)

    @playlist.command(name="loop")
    async def playlist_loop(self, ctx: commands.Context, *, name: str):
        """Loop a playlist continuously in order. !stop to end."""
        await self._queue_playlist(ctx, name, shuffle=False, loop=True)

    @playlist.command(name="loopshuffle")
    async def playlist_loopshuffle(self, ctx: commands.Context, *, name: str):
        """Continuously shuffle-loop a playlist. Re-shuffles every pass. !stop to end."""
        await self._queue_playlist(ctx, name, shuffle=True, loop=True)

    async def _queue_playlist(self, ctx: commands.Context, name: str, shuffle: bool, loop: bool = False):
        from cogs.music import MusicCog

        pid = _get_playlist_id(name)
        if pid is None:
            await ctx.send(f"Playlist **{name}** not found.")
            return

        tracks = _get_tracks(pid)
        if not tracks:
            await ctx.send(f"Playlist **{name}** is empty.")
            return

        paths = [Path(t["filepath"]) for t in tracks if Path(t["filepath"]).exists()]
        missing = len(tracks) - len(paths)
        if not paths:
            await ctx.send(f"All tracks in **{name}** are missing from disk.")
            return

        if shuffle:
            random.shuffle(paths)

        music_cog: MusicCog = self.bot.cogs.get("Music")
        if music_cog is None:
            await ctx.send("Music cog not loaded.")
            return

        vc = await music_cog._get_voice_client(ctx)
        if vc is None:
            return

        state = music_cog._state(ctx.guild.id)

        if loop:
            if vc.is_playing() or vc.is_paused():
                vc.stop()
            # Store original unshuffled paths as the loop source so each pass can re-shuffle
            with _db() as conn:
                rows = conn.execute(
                    "SELECT filepath FROM playlist_tracks WHERE playlist_id = ? ORDER BY position", (pid,)
                ).fetchall()
            state.loop_source = [Path(r["filepath"]) for r in rows if Path(r["filepath"]).exists()]
            state.loop_shuffle = shuffle
            state.queue = list(paths[1:])
            state.current = paths[0]
            mode = "shuffle-looping" if shuffle else "looping"
            msg = f"Now {mode} **{name}** — {len(paths)} tracks. Use `!loopoff` or `!stop` to end."
            music_cog._play_track(vc, state, ctx)
        elif vc.is_playing() or vc.is_paused():
            state.queue.extend(paths)
            msg = f"Queued **{len(paths)}** tracks from **{name}**."
        else:
            state.current = paths[0]
            state.queue.extend(paths[1:])
            msg = f"Playing **{name}** — {len(paths)} tracks. First: **{paths[0].stem}**"
            music_cog._play_track(vc, state, ctx)

        if missing:
            msg += f"\n⚠️ {missing} track(s) missing from disk and skipped."
        await ctx.send(msg)


async def setup(bot: commands.Bot):
    await bot.add_cog(PlaylistCog(bot))
