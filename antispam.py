"""
modules/antispam.py — antiflood, locks, blocklist, antiraid
"""

import time
import re
from collections import defaultdict
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from telegram.error import BadRequest

import db
from config import DEFAULT_FLOOD_LIMIT
from helpers import require_admin, resolve_target, MUTED_PERMS

# ── Flood tracking (in-memory) ────────────────────────────────────────────────
# {chat_id: {user_id: [timestamps]}}
_flood_tracker: dict[int, dict[int, list]] = defaultdict(lambda: defaultdict(list))

LOCK_TYPES = {
    "text", "media", "sticker", "gif", "music", "document",
    "photo", "video", "voice", "voicenote", "contact", "location",
    "forward", "game", "link", "url", "bot", "poll", "inline"
}


# ── Flood ─────────────────────────────────────────────────────────────────────

async def check_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    limit   = db.get(chat_id, "flood_limit") or DEFAULT_FLOOD_LIMIT
    if limit == 0:
        return

    approved = db.get(chat_id, "approved") or []
    if user_id in approved:
        return

    # Check if user is admin
    try:
        member = await update.effective_chat.get_member(user_id)
        if member.status in ("administrator", "creator"):
            return
    except BadRequest:
        return

    now = time.time()
    timestamps = _flood_tracker[chat_id][user_id]
    timestamps = [t for t in timestamps if now - t < 10]
    timestamps.append(now)
    _flood_tracker[chat_id][user_id] = timestamps

    if len(timestamps) >= limit:
        _flood_tracker[chat_id][user_id] = []
        mode = db.get(chat_id, "flood_mode") or "mute"
        user = update.effective_user
        name = user.full_name or user.first_name
        try:
            if mode == "ban":
                await update.effective_chat.ban_member(user_id)
                await update.message.reply_html(f"🌊 {name} was <b>banned</b> for flooding.")
            elif mode == "kick":
                await update.effective_chat.ban_member(user_id)
                await update.effective_chat.unban_member(user_id)
                await update.message.reply_html(f"🌊 {name} was <b>kicked</b> for flooding.")
            else:
                await update.effective_chat.restrict_member(user_id, MUTED_PERMS)
                await update.message.reply_html(f"🌊 {name} was <b>muted</b> for flooding.")
        except BadRequest:
            pass


async def antiflood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    arg = context.args[0].lower() if context.args else None
    cid = update.effective_chat.id
    if arg == "off":
        db.set(cid, "flood_limit", 0)
        await update.message.reply_text("✅ Antiflood disabled.")
    elif arg == "on":
        limit = db.get(cid, "flood_limit") or DEFAULT_FLOOD_LIMIT
        if limit == 0:
            db.set(cid, "flood_limit", DEFAULT_FLOOD_LIMIT)
        await update.message.reply_text(f"✅ Antiflood enabled (limit: {limit} msgs/10s).")
    else:
        limit = db.get(cid, "flood_limit") or DEFAULT_FLOOD_LIMIT
        await update.message.reply_text(
            f"Antiflood: {'enabled' if limit else 'disabled'} (limit: {limit})\n"
            "Use /antiflood on|off"
        )


async def set_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /setflood <number>  (0 to disable)")
        return
    n = int(context.args[0])
    db.set(update.effective_chat.id, "flood_limit", n)
    await update.message.reply_text(f"✅ Flood limit set to {n} messages per 10 seconds." if n else "✅ Antiflood disabled.")


async def flood_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    cid = update.effective_chat.id
    if not context.args or context.args[0] not in ("ban", "kick", "mute"):
        mode = db.get(cid, "flood_mode") or "mute"
        await update.message.reply_text(f"Flood mode: {mode}\nOptions: ban, kick, mute")
        return
    db.set(cid, "flood_mode", context.args[0])
    await update.message.reply_text(f"✅ Flood mode set to {context.args[0]}.")


# ── Locks ─────────────────────────────────────────────────────────────────────

async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not context.args or context.args[0] not in LOCK_TYPES:
        await update.message.reply_text(f"Valid lock types: {', '.join(sorted(LOCK_TYPES))}")
        return
    locks = db.get(update.effective_chat.id, "locks") or []
    ltype = context.args[0]
    if ltype not in locks:
        locks.append(ltype)
        db.set(update.effective_chat.id, "locks", locks)
    await update.message.reply_text(f"🔒 Locked: {ltype}")


async def unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /unlock <type>")
        return
    locks = db.get(update.effective_chat.id, "locks") or []
    ltype = context.args[0]
    if ltype in locks:
        locks.remove(ltype)
        db.set(update.effective_chat.id, "locks", locks)
    await update.message.reply_text(f"🔓 Unlocked: {ltype}")


async def locks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current = db.get(update.effective_chat.id, "locks") or []
    if not current:
        await update.message.reply_text("No locks active.")
        return
    await update.message.reply_html("<b>Active locks:</b>\n" + "\n".join(f"• {l}" for l in current))


# ── Blocklist ─────────────────────────────────────────────────────────────────

async def check_blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_message.text:
        return
    cid = update.effective_chat.id
    uid = update.effective_user.id
    approved = db.get(cid, "approved") or []
    if uid in approved:
        return
    try:
        member = await update.effective_chat.get_member(uid)
        if member.status in ("administrator", "creator"):
            return
    except BadRequest:
        return

    blocklist = db.get(cid, "blocklist") or []
    text_lower = update.effective_message.text.lower()
    for word in blocklist:
        pattern = re.compile(r'\b' + re.escape(word.lower()) + r'\b')
        if pattern.search(text_lower):
            mode = db.get(cid, "blocklist_mode") or "warn"
            user = update.effective_user
            name = user.full_name or user.first_name
            try:
                await update.message.delete()
            except BadRequest:
                pass
            try:
                if mode == "ban":
                    await update.effective_chat.ban_member(uid)
                    await context.bot.send_message(cid, f"🚫 {name} banned for using a blocked word.")
                elif mode == "kick":
                    await update.effective_chat.ban_member(uid)
                    await update.effective_chat.unban_member(uid)
                    await context.bot.send_message(cid, f"👢 {name} kicked for using a blocked word.")
                elif mode == "mute":
                    await update.effective_chat.restrict_member(uid, MUTED_PERMS)
                    await context.bot.send_message(cid, f"🔇 {name} muted for using a blocked word.")
                elif mode == "warn":
                    warns_list = db.get(cid, f"warns_{uid}") or []
                    warns_list.append(f"Blocklist: {word}")
                    db.set(cid, f"warns_{uid}", warns_list)
                    limit = db.get(cid, "warn_limit") or 3
                    await context.bot.send_message(
                        cid,
                        f"⚠️ {name} warned for using a blocked word. ({len(warns_list)}/{limit})"
                    )
            except BadRequest:
                pass
            return


async def blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bl = db.get(update.effective_chat.id, "blocklist") or []
    if not bl:
        await update.message.reply_text("No blocked words in this group.")
        return
    await update.message.reply_html(
        "<b>Blocked words:</b>\n" + "\n".join(f"• {w}" for w in bl)
    )


async def add_blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /addblocklist <word1> [word2] ...")
        return
    cid = update.effective_chat.id
    from config import MAX_BLOCKLIST
    bl = db.get(cid, "blocklist") or []
    added = []
    for w in context.args:
        if w.lower() not in bl and len(bl) < MAX_BLOCKLIST:
            bl.append(w.lower())
            added.append(w)
    db.set(cid, "blocklist", bl)
    await update.message.reply_text(f"✅ Added {len(added)} word(s) to blocklist.")


async def rm_blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /rmblocklist <word1> [word2] ...")
        return
    cid = update.effective_chat.id
    bl = db.get(cid, "blocklist") or []
    removed = []
    for w in context.args:
        if w.lower() in bl:
            bl.remove(w.lower())
            removed.append(w)
    db.set(cid, "blocklist", bl)
    await update.message.reply_text(f"✅ Removed {len(removed)} word(s) from blocklist.")


async def blocklist_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    cid = update.effective_chat.id
    valid = ("ban", "kick", "mute", "warn")
    if not context.args or context.args[0] not in valid:
        mode = db.get(cid, "blocklist_mode") or "warn"
        await update.message.reply_text(f"Blocklist mode: {mode}\nOptions: {', '.join(valid)}")
        return
    db.set(cid, "blocklist_mode", context.args[0])
    await update.message.reply_text(f"✅ Blocklist mode set to {context.args[0]}.")


# ── Antiraid ─────────────────────────────────────────────────────────────────

async def antiraid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    arg = context.args[0].lower() if context.args else None
    cid = update.effective_chat.id
    if arg not in ("on", "off"):
        state = "on" if db.get(cid, "antiraid") else "off"
        await update.message.reply_text(f"Antiraid is currently {state}. Use /antiraid on|off")
        return
    db.set(cid, "antiraid", arg == "on")
    await update.message.reply_text(
        f"✅ Antiraid {'enabled — new members will be kicked for 5 minutes.' if arg == 'on' else 'disabled.'}"
    )
