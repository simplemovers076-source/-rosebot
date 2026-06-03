"""
helpers.py — Shared utilities used across all modules.
"""

import re
from datetime import timedelta
from typing import Optional, Tuple

from telegram import Update, Chat, User, ChatPermissions
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from config import OWNER_ID, SUDO_USERS


# ── Permission checks ─────────────────────────────────────────────────────────

async def is_admin(update: Update, user_id: int) -> bool:
    """Return True if user_id is an admin in the chat."""
    if user_id in [OWNER_ID] + SUDO_USERS:
        return True
    try:
        member = await update.effective_chat.get_member(user_id)
        return member.status in ("administrator", "creator")
    except BadRequest:
        return False


async def is_bot_admin(chat: Chat, bot) -> bool:
    """Return True if the bot has admin rights in the chat."""
    try:
        member = await chat.get_member(bot.id)
        return member.status == "administrator"
    except BadRequest:
        return False


async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Reply with an error if the sender is not an admin.
    Returns True if the user IS an admin, False otherwise.
    """
    user = update.effective_user
    if not await is_admin(update, user.id):
        await update.message.reply_text("⛔ You need to be an admin to use this command.")
        return False
    return True


# ── Target resolution ────────────────────────────────────────────────────────

async def resolve_target(update: Update, context: ContextTypes.DEFAULT_TYPE
                         ) -> Tuple[Optional[int], Optional[str], str]:
    """
    Resolve the target user from a reply or @username/user_id argument.
    Returns (user_id, username, reason).
    """
    message = update.message
    reason = " ".join(context.args[1:]) if context.args and len(context.args) > 1 else ""

    # Reply to a message
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        reason = " ".join(context.args) if context.args else ""
        return target.id, target.username or target.first_name, reason

    # Username or ID as first argument
    if context.args:
        arg = context.args[0]
        if arg.startswith("@"):
            try:
                chat = await context.bot.get_chat(arg)
                return chat.id, chat.username or chat.first_name, reason
            except BadRequest:
                await message.reply_text(f"❌ Could not find user {arg}.")
                return None, None, ""
        elif arg.isdigit():
            return int(arg), str(arg), reason

    await message.reply_text("❓ Please reply to a user or provide @username / user_id.")
    return None, None, ""


# ── Time parsing ─────────────────────────────────────────────────────────────

def parse_time(text: str) -> Optional[timedelta]:
    """
    Parse a time string like '10m', '2h', '1d', '1w' into a timedelta.
    Returns None if invalid.
    """
    match = re.fullmatch(r"(\d+)([smhdw])", text.strip().lower())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    return {
        "s": timedelta(seconds=amount),
        "m": timedelta(minutes=amount),
        "h": timedelta(hours=amount),
        "d": timedelta(days=amount),
        "w": timedelta(weeks=amount),
    }[unit]


# ── Formatting ────────────────────────────────────────────────────────────────

def mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def fmt_user(user: User) -> str:
    name = user.full_name or user.first_name
    return mention(user.id, name)


# ── Permission presets ────────────────────────────────────────────────────────

MUTED_PERMS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
)

UNMUTED_PERMS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
)


# ── Log helper ────────────────────────────────────────────────────────────────

async def log_action(context: ContextTypes.DEFAULT_TYPE, chat, text: str):
    from config import LOG_CHANNEL
    if LOG_CHANNEL:
        try:
            await context.bot.send_message(LOG_CHANNEL, text, parse_mode="HTML")
        except Exception:
            pass
