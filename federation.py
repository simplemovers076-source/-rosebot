"""
modules/federation.py — cross-group ban federations
/newfed, /delfed, /joinfed, /leavefed
/fban, /unfban, /fedinfo, /fedbans, /fadmin, /fpromote, /fdemote
"""

import uuid
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

import db
from helpers import require_admin, resolve_target


def _get_feds() -> dict:
    return db.get_global("federations") or {}


def _save_feds(feds: dict):
    db.set_global("federations", feds)


def _find_fed_by_owner(user_id: int) -> tuple[str | None, dict | None]:
    for fid, fed in _get_feds().items():
        if fed["owner"] == user_id:
            return fid, fed
    return None, None


def _find_chat_fed(chat_id: int) -> tuple[str | None, dict | None]:
    for fid, fed in _get_feds().items():
        if chat_id in fed.get("chats", []):
            return fid, fed
    return None, None


async def new_fed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    _, existing = _find_fed_by_owner(user.id)
    if existing:
        await update.message.reply_text(f"❌ You already own a federation: {existing['name']}")
        return
    name = " ".join(context.args)
    if not name:
        await update.message.reply_text("Usage: /newfed <name>")
        return
    fid = str(uuid.uuid4())[:8]
    feds = _get_feds()
    feds[fid] = {"name": name, "owner": user.id, "chats": [], "bans": {}, "admins": []}
    _save_feds(feds)
    await update.message.reply_html(
        f"✅ Federation <b>{name}</b> created!\n"
        f"ID: <code>{fid}</code>\n\n"
        f"Join chats to this federation with:\n/joinfed {fid}"
    )


async def del_fed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fid, fed = _find_fed_by_owner(update.effective_user.id)
    if not fed:
        await update.message.reply_text("❌ You don't own a federation.")
        return
    feds = _get_feds()
    del feds[fid]
    _save_feds(feds)
    await update.message.reply_text(f"✅ Federation '{fed['name']}' deleted.")


async def join_fed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /joinfed <federation_id>")
        return
    fid = context.args[0]
    feds = _get_feds()
    if fid not in feds:
        await update.message.reply_text("❌ Federation not found.")
        return
    cid = update.effective_chat.id
    if cid in feds[fid]["chats"]:
        await update.message.reply_text("This chat is already in that federation.")
        return
    # Leave any current federation first
    for f in feds.values():
        if cid in f.get("chats", []):
            f["chats"].remove(cid)
    feds[fid]["chats"].append(cid)
    _save_feds(feds)
    await update.message.reply_html(f"✅ Joined federation <b>{feds[fid]['name']}</b>.")


async def leave_fed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    cid = update.effective_chat.id
    feds = _get_feds()
    for fid, fed in feds.items():
        if cid in fed.get("chats", []):
            fed["chats"].remove(cid)
            _save_feds(feds)
            await update.message.reply_text(f"✅ Left federation '{fed['name']}'.")
            return
    await update.message.reply_text("This chat is not in any federation.")


async def fban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name, reason = await resolve_target(update, context)
    if uid is None:
        return
    user = update.effective_user
    feds = _get_feds()
    # find federation this chat belongs to
    cid = update.effective_chat.id
    fid, fed = _find_chat_fed(cid)
    if not fed:
        await update.message.reply_text("❌ This chat is not in a federation.")
        return
    if user.id != fed["owner"] and user.id not in fed.get("admins", []):
        await update.message.reply_text("⛔ Only federation admins can use /fban.")
        return
    fed["bans"][str(uid)] = reason or "No reason given"
    _save_feds(feds)
    # Ban in all federation chats
    banned_in = 0
    for chat_id in fed["chats"]:
        try:
            await context.bot.ban_chat_member(chat_id, uid)
            banned_in += 1
        except BadRequest:
            pass
    await update.message.reply_html(
        f"🚫 Federation banned {name} across {banned_in} chat(s).\n"
        + (f"Reason: {reason}" if reason else "")
    )


async def unfban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name, _ = await resolve_target(update, context)
    if uid is None:
        return
    user = update.effective_user
    feds = _get_feds()
    cid = update.effective_chat.id
    fid, fed = _find_chat_fed(cid)
    if not fed:
        await update.message.reply_text("❌ This chat is not in a federation.")
        return
    if user.id != fed["owner"] and user.id not in fed.get("admins", []):
        await update.message.reply_text("⛔ Only federation admins can use /unfban.")
        return
    fed["bans"].pop(str(uid), None)
    _save_feds(feds)
    unbanned_in = 0
    for chat_id in fed["chats"]:
        try:
            await context.bot.unban_chat_member(chat_id, uid)
            unbanned_in += 1
        except BadRequest:
            pass
    await update.message.reply_html(f"✅ {name} un-federation-banned across {unbanned_in} chat(s).")


async def fed_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    fid, fed = _find_chat_fed(cid)
    if not fed:
        await update.message.reply_text("This chat is not in any federation.")
        return
    await update.message.reply_html(
        f"<b>Federation: {fed['name']}</b>\n"
        f"ID: <code>{fid}</code>\n"
        f"Chats: {len(fed.get('chats', []))}\n"
        f"Bans: {len(fed.get('bans', {}))}\n"
        f"Admins: {len(fed.get('admins', []))}"
    )


async def fed_bans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    _, fed = _find_chat_fed(cid)
    if not fed:
        await update.message.reply_text("This chat is not in any federation.")
        return
    bans = fed.get("bans", {})
    if not bans:
        await update.message.reply_text("No federation bans.")
        return
    lines = "\n".join(f"• <code>{uid}</code>: {reason}" for uid, reason in list(bans.items())[:50])
    await update.message.reply_html(f"<b>Federation bans ({len(bans)}):</b>\n{lines}")


async def fed_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    fid, fed = _find_chat_fed(cid)
    if not fed:
        await update.message.reply_text("This chat is not in any federation.")
        return
    admins = fed.get("admins", [])
    text = f"<b>Federation admins:</b>\nOwner: <code>{fed['owner']}</code>\n"
    if admins:
        text += "\n".join(f"• <code>{a}</code>" for a in admins)
    await update.message.reply_html(text)


async def fed_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    fid, fed = _find_fed_by_owner(user.id)
    if not fed:
        await update.message.reply_text("❌ You don't own a federation.")
        return
    uid, name, _ = await resolve_target(update, context)
    if uid is None:
        return
    feds = _get_feds()
    if uid not in feds[fid]["admins"]:
        feds[fid]["admins"].append(uid)
        _save_feds(feds)
    await update.message.reply_html(f"✅ {name} is now a federation admin.")


async def fed_demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    fid, fed = _find_fed_by_owner(user.id)
    if not fed:
        await update.message.reply_text("❌ You don't own a federation.")
        return
    uid, name, _ = await resolve_target(update, context)
    if uid is None:
        return
    feds = _get_feds()
    if uid in feds[fid]["admins"]:
        feds[fid]["admins"].remove(uid)
        _save_feds(feds)
    await update.message.reply_html(f"✅ {name} removed from federation admins.")
