"""
modules/moderation.py — ban, unban, kick, mute, unmute, tban, tmute,
                         purge, del, approve, unapprove, pin, unpin
"""

from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

import db
from helpers import (
    require_admin, resolve_target, parse_time,
    MUTED_PERMS, UNMUTED_PERMS, log_action, fmt_user
)


# ── Ban ───────────────────────────────────────────────────────────────────────

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    uid, name, reason = await resolve_target(update, context)
    if uid is None:
        return
    try:
        await update.effective_chat.ban_member(uid)
        text = f"🚫 Banned {name}" + (f"\nReason: {reason}" if reason else "")
        await update.message.reply_html(text)
        await log_action(context, update.effective_chat,
                         f"#BAN in {update.effective_chat.title}\n"
                         f"User: {name} (<code>{uid}</code>)\n"
                         f"By: {fmt_user(update.effective_user)}\n"
                         + (f"Reason: {reason}" if reason else ""))
    except BadRequest as e:
        await update.message.reply_text(f"❌ Failed to ban: {e}")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    uid, name, _ = await resolve_target(update, context)
    if uid is None:
        return
    try:
        await update.effective_chat.unban_member(uid)
        await update.message.reply_html(f"✅ Unbanned {name}. They can rejoin.")
    except BadRequest as e:
        await update.message.reply_text(f"❌ Failed to unban: {e}")


async def tban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Temporary ban: /tban @user 2h [reason]"""
    if not await require_admin(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /tban @user <time> [reason]  (e.g. 1h, 30m, 7d)")
        return

    uid, name, rest = await resolve_target(update, context)
    if uid is None:
        return

    # rest might be "2h reason text" if no reply, or just "2h reason" if reply
    parts = rest.split(None, 1) if rest else []
    time_str = parts[0] if parts else (context.args[1] if len(context.args) > 1 else "")
    reason = parts[1] if len(parts) > 1 else ""

    delta = parse_time(time_str)
    if delta is None:
        await update.message.reply_text("❌ Invalid time. Use 30s, 10m, 2h, 7d, 1w.")
        return

    until = datetime.now(timezone.utc) + delta
    try:
        await update.effective_chat.ban_member(uid, until_date=until)
        await update.message.reply_html(
            f"⏱ Temporarily banned {name} for <b>{time_str}</b>"
            + (f"\nReason: {reason}" if reason else "")
        )
    except BadRequest as e:
        await update.message.reply_text(f"❌ Failed: {e}")


# ── Kick ──────────────────────────────────────────────────────────────────────

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    uid, name, reason = await resolve_target(update, context)
    if uid is None:
        return
    try:
        await update.effective_chat.ban_member(uid)
        await update.effective_chat.unban_member(uid)  # unban immediately = kick
        await update.message.reply_html(
            f"👢 Kicked {name}" + (f"\nReason: {reason}" if reason else "")
        )
    except BadRequest as e:
        await update.message.reply_text(f"❌ Failed to kick: {e}")


# ── Mute ─────────────────────────────────────────────────────────────────────

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    uid, name, reason = await resolve_target(update, context)
    if uid is None:
        return
    try:
        await update.effective_chat.restrict_member(uid, MUTED_PERMS)
        await update.message.reply_html(
            f"🔇 Muted {name}" + (f"\nReason: {reason}" if reason else "")
        )
    except BadRequest as e:
        await update.message.reply_text(f"❌ Failed to mute: {e}")


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    uid, name, _ = await resolve_target(update, context)
    if uid is None:
        return
    try:
        await update.effective_chat.restrict_member(uid, UNMUTED_PERMS)
        await update.message.reply_html(f"🔊 Unmuted {name}.")
    except BadRequest as e:
        await update.message.reply_text(f"❌ Failed to unmute: {e}")


async def tmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Temporary mute: /tmute @user 2h [reason]"""
    if not await require_admin(update, context):
        return
    uid, name, rest = await resolve_target(update, context)
    if uid is None:
        return

    parts = rest.split(None, 1) if rest else []
    time_str = parts[0] if parts else (context.args[1] if len(context.args) > 1 else "")
    reason = parts[1] if len(parts) > 1 else ""

    delta = parse_time(time_str)
    if delta is None:
        await update.message.reply_text("❌ Invalid time. Use 30s, 10m, 2h, 7d.")
        return

    until = datetime.now(timezone.utc) + delta
    try:
        await update.effective_chat.restrict_member(uid, MUTED_PERMS, until_date=until)
        await update.message.reply_html(
            f"⏱ Muted {name} for <b>{time_str}</b>"
            + (f"\nReason: {reason}" if reason else "")
        )
    except BadRequest as e:
        await update.message.reply_text(f"❌ Failed: {e}")


# ── Purge ─────────────────────────────────────────────────────────────────────

async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    msg = update.message
    if not msg.reply_to_message:
        await msg.reply_text("Reply to the first message you want to delete.")
        return
    start_id = msg.reply_to_message.message_id
    end_id   = msg.message_id
    deleted  = 0
    for mid in range(start_id, end_id + 1):
        try:
            await context.bot.delete_message(msg.chat_id, mid)
            deleted += 1
        except BadRequest:
            pass
    notice = await msg.reply_text(f"🗑 Purged {deleted} messages.")
    try:
        await notice.delete()
    except BadRequest:
        pass


async def delete_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the message you want to delete.")
        return
    try:
        await update.message.reply_to_message.delete()
        await update.message.delete()
    except BadRequest as e:
        await update.message.reply_text(f"❌ {e}")


# ── Approve ───────────────────────────────────────────────────────────────────

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    uid, name, _ = await resolve_target(update, context)
    if uid is None:
        return
    approved = db.get(update.effective_chat.id, "approved") or []
    if uid not in approved:
        approved.append(uid)
        db.set(update.effective_chat.id, "approved", approved)
    await update.message.reply_html(f"✅ {name} is now approved and bypasses locks.")


async def unapprove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    uid, name, _ = await resolve_target(update, context)
    if uid is None:
        return
    approved = db.get(update.effective_chat.id, "approved") or []
    if uid in approved:
        approved.remove(uid)
        db.set(update.effective_chat.id, "approved", approved)
    await update.message.reply_html(f"❌ {name} is no longer approved.")


# ── Pin ───────────────────────────────────────────────────────────────────────

async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the message you want to pin.")
        return
    silent = "silent" in (context.args or [])
    try:
        await update.message.reply_to_message.pin(disable_notification=silent)
        await update.message.reply_text("📌 Message pinned.")
    except BadRequest as e:
        await update.message.reply_text(f"❌ {e}")


async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    try:
        await update.effective_chat.unpin_message()
        await update.message.reply_text("📌 Message unpinned.")
    except BadRequest as e:
        await update.message.reply_text(f"❌ {e}")
