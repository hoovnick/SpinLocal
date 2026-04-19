# SpinLocal — Self-Hosted Discord Music Bot

Play your **local music files** in Discord voice channels — no YouTube, no Spotify, no external APIs. SpinLocal is a self-hosted Discord bot that streams your own MP3, FLAC, WAV, and more directly from your machine. Your music, your server, your control.

Supports playlists, queue management, category folders, looping, shuffle-looping, and an interactive playlist editor with Discord buttons. Built for streamers and communities that want full control over their music.

---

## Features

- Stream local MP3, WAV, OGG, FLAC, and M4A files directly in Discord voice channels
- Organize music into category subfolders — queue or loop entire folders
- Full queue control — skip, remove, reorder, shuffle
- Named playlists with an interactive button-based editor
- Loop a single track, a playlist, or an entire category
- Continuous shuffle-loop (re-shuffles every pass)
- Role-based access control via a configurable Discord "DJ" role
- 100% self-hosted — zero external music APIs, just Python and FFmpeg

---

## Requirements

- Python 3.10 or higher
- FFmpeg installed and available on your system PATH
- A Discord bot token

### Installing FFmpeg

**Windows:**
1. Download from [ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Extract to a folder (e.g. `C:\ffmpeg`)
3. Add `C:\ffmpeg\bin` to your system PATH
4. Verify: open a terminal and run `ffmpeg -version`

**Mac:**
```bash
brew install ffmpeg
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install ffmpeg
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/hoovnick/SpinLocal.git
cd SpinLocal
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure your environment

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` in any text editor:

```env
DISCORD_TOKEN=your_discord_bot_token_here
MUSIC_ROOT=C:/Users/YourName/Music
```

All other settings are optional — the defaults work out of the box.

### 4. Add your music

Point `MUSIC_ROOT` at a folder containing your audio files. You can organize them into subfolders — each subfolder becomes a "category" you can queue or loop as a group:

```
music/
  rock/
    song1.mp3
    song2.mp3
  jazz/
    track1.flac
  ambient/
    ...
```

Supported formats: `.mp3` `.wav` `.ogg` `.flac` `.m4a`

### 5. Create your Discord bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → name it **SpinLocal**
3. Go to **Bot** → click **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - `Server Members Intent`
   - `Message Content Intent`
5. Copy your bot token and paste it into `.env` as `DISCORD_TOKEN`

### 6. Invite the bot to your server

Go to **OAuth2 → URL Generator**, select:
- Scopes: `bot`
- Bot Permissions: `Connect`, `Speak`, `Send Messages`, `Read Message History`

Open the generated URL and invite the bot to your server.

### 7. Create the DJ role

In your Discord server:
1. Go to **Server Settings → Roles → Create Role**
2. Name it exactly **`DJ`** (or whatever you set `DJ_ROLE_NAME` to in `.env`)
3. Assign this role to anyone you want to control the bot

### 8. Run the bot

**Windows** — double-click `run.bat`, or from a terminal:
```bash
python bot.py
```

**Mac/Linux:**
```bash
chmod +x run.sh
./run.sh
```

The bot will print `SpinLocal online as ...` when it's ready.

---

## Command Reference

### Playback

| Command | Description |
|---|---|
| `!join` | Join your current voice channel |
| `!leave` | Disconnect and clear queue |
| `!play <song>` | Search all music, queue first match |
| `!playnext <song>` | Insert a song at position 1 (plays right after current) |
| `!playcat <category>` | Queue every song in a category folder |
| `!skip` | Skip the current track |
| `!stop` | Stop playback and clear everything |
| `!pause` | Pause playback |
| `!resume` | Resume paused playback |
| `!volume <0–100>` | Set playback volume |
| `!loop` | Toggle looping the current track |
| `!loopcat <category>` | Play and loop a category continuously in order |
| `!shuffleloop <category>` | Play and shuffle-loop a category (re-shuffles each pass) |
| `!loopoff` | Disable queue loop after current queue finishes |
| `!shuffle` | Shuffle the current queue |
| `!clear` | Clear the queue without stopping current track |
| `!remove <#>` | Remove a track from the queue by position number |

### Info & Browse

| Command | Description |
|---|---|
| `!nowplaying` / `!np` | Show current track, category, and queue count |
| `!queue` / `!q` | Show the current queue (up to 15 tracks) |
| `!search <term>` | List all songs matching a search term |
| `!list` | Show all music category folders |
| `!list <category>` | Show all songs in a category |
| `!ping` | Check bot latency |

### Playlists

| Command | Description |
|---|---|
| `!playlist list` | Show all saved playlists with track counts |
| `!playlist create <name>` | Create a new empty playlist |
| `!playlist edit <name>` | Open the interactive editor (buttons for add/remove/move/rename) |
| `!playlist show <name>` | Display all tracks in a playlist |
| `!playlist play <name>` | Queue all tracks from a playlist |
| `!playlist shuffle <name>` | Queue all tracks in random order |
| `!playlist loop <name>` | Loop a playlist continuously in order |
| `!playlist loopshuffle <name>` | Shuffle-loop a playlist (re-shuffles each pass) |
| `!playlist delete <name>` | Permanently delete a playlist |
| `!playlist rename <old> <new>` | Rename a playlist |
| `!playlist add <name> <song>` | Add a song to a playlist |
| `!playlist remove <name> <song>` | Remove a song from a playlist by name |
| `!playlist move <name> <pos> <newpos>` | Reorder a track within a playlist |

> **Note:** All playback and DJ commands require the **DJ** role. `!search`, `!list`, `!nowplaying`, `!queue`, and `!ping` are open to everyone.

---

## Configuration

All settings live in `.env`. Copy `.env.example` to get started.

| Variable | Default | Description |
|---|---|---|
| `DISCORD_TOKEN` | *(required)* | Your Discord bot token |
| `MUSIC_ROOT` | `./music` | Path to your local music folder |
| `DJ_ROLE_NAME` | `DJ` | Discord role name that grants bot control |
| `DEFAULT_VOLUME` | `0.5` | Starting volume (0.0–1.0) |
| `COMMAND_PREFIX` | `!` | Bot command prefix |
| `DB_PATH` | `./data/playlists.db` | Where playlist data is stored |

---

## Troubleshooting

**Bot joins voice but plays nothing / immediately says "Queue finished"**
- FFmpeg is not installed or not on your PATH. Run `ffmpeg -version` in a terminal to check. If it fails, install FFmpeg and add it to PATH.

**`RuntimeError: PyNaCl library needed`**
- Run `pip install "discord.py[voice]"` — the `[voice]` extra includes PyNaCl which is required for voice connections.

**Bot doesn't respond to commands**
- Make sure `Message Content Intent` is enabled in the Discord Developer Portal under your bot's settings.
- Confirm the command prefix matches what's in your `.env`.

**Songs not found with `!play`**
- Check that `MUSIC_ROOT` in `.env` points to the correct folder.
- Song search matches against filenames (without extension). Use `!list` to browse what's available.

---

## License

MIT — see [LICENSE](LICENSE)
