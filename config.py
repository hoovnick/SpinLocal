import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Required ──────────────────────────────────────────────────────────────────
# Set these in your .env file (copy .env.example to .env to get started)

# Path to the folder containing your local music files.
# Can be an absolute path (e.g. C:/Users/You/Music) or relative to this file.
MUSIC_ROOT = Path(os.getenv("MUSIC_ROOT", "./music"))

# ── Optional — defaults work out of the box ───────────────────────────────────

# Discord role name that grants access to music commands.
# Create a role with this exact name in your server and assign it to trusted users.
DJ_ROLE_NAME = os.getenv("DJ_ROLE_NAME", "DJ")

# Starting volume (0.0 – 1.0)
DEFAULT_VOLUME = float(os.getenv("DEFAULT_VOLUME", "0.5"))

# Bot command prefix
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

# Where the playlist database is stored
DB_PATH = Path(os.getenv("DB_PATH", "./data/playlists.db"))

# ── Audio ─────────────────────────────────────────────────────────────────────

FFMPEG_OPTIONS = {
    "options": "-vn",
}

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}
