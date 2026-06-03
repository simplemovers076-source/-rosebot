"""
config.py — Edit this before running the bot.
"""

# ── Required ──────────────────────────────────────────────────────────────────
# Get your token from @BotFather on Telegram
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Your Telegram user ID (get it from @userinfobot). Bot owners bypass all checks.
OWNER_ID = 123456789

# ── Optional ──────────────────────────────────────────────────────────────────
# Extra user IDs who share owner-level access
SUDO_USERS = []

# Bot name shown in /help and /start
BOT_NAME = "RoseBot"

# Default warn limit before action is taken
DEFAULT_WARN_LIMIT = 3

# Default warn mode: "ban", "kick", or "mute"
DEFAULT_WARN_MODE = "ban"

# Default antiflood limit (messages per 10 seconds, 0 = disabled)
DEFAULT_FLOOD_LIMIT = 10

# Where to log admin actions (set to a channel/group ID, or None to disable)
LOG_CHANNEL = None

# Max filters, notes, blocklist entries per group
MAX_FILTERS   = 500
MAX_NOTES     = 2000
MAX_BLOCKLIST = 500
