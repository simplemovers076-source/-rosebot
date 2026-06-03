"""
modules/warnings.py — /warn, /unwarn, /resetwarns, /warns, /warnlimit, /warnmode
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

import db
from config import DEFAULT_WARN_LIMIT, DEFAULT_WARN_MODE
from helpers import require_admin, resolve_target, MUTED_PERMS, fmt_user


async def _get_limit(chat_id: int) -> int:
    return db.get(chat_id, "warn_limit") or DEFAULT_WARN_LIMIT


async def _get_mode(chat_id: int) -> str:
    return db.get(chat_id, "warn_mode") or DEFAULT_WARN_MODE


async def _apply_warn_action(update: Update, context, uid: int, name: str, mode: str):
    chat = update.effective_chat
    if mode == "ban":
        await chat.ban_member(uid)
        await update.message.reply_html(f"⚠️ {name} hit the warn limit and was <b>banned</b>.")
    elif mode == "kick":
        await chat.ban_member(uid)
        await chat.unban_member(uid)
        await update.message.reply_html(f"⚠️ {name} hit the warn limit and was <b>kicked</b>.")
    elif mode == "mute":
        await chat.restrict_member(uid, MUTED_PERMS)
        await update.message.reply_html(f"⚠️ {name} hit the warn limit and was <b>muted</b>.")


async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    uid, name, reason = await resolve_target(update, context)
    if uid is None:
        return

    chat_id = update.effective_chat.id
    key = f"warns_{uid}"
    warns_list = db.get(chat_id, key) or []
    warns_list.append(reason or "No reason given")
    db.set(chat_id, key, warns_list)

    limit = await _get_limit(chat_id)
    count = len(warns_list)

    text = (
        f"⚠️ Warned {name}\n"
        f"Reason: {reason or 'No reason given'}\n"
        f"Warns: {count}/{limit}"
    )
    await update.message.reply_html(text)

    if count >= limit:
        mode = await _get_mode(chat_id)
        db.delete(chat_id, key)  # reset after action
        try:
            await _apply_warn_action(update, context, uid, name, mode)
        except BadRequest as e:
            await update.message.reply_text(f"❌ Could not apply action: {e}")


async def unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    uid, name, _ = await resolve_target(update, context)
    if uid is None:
        return
    chat_id = update.effective_chat.id
    key = f"warns_{uid}"
    warns_list = db.get(chat_id, key) or []
    if warns_list:
        warns_list.pop()
        db.set(chat_id, key, warns_list)
        await update.message.reply_html(f"✅ Removed last warn for {name}. Now at {len(warns_list)} warn(s).")
    else:
        await update.message.reply_text(f"{name} has no warnings.")


async def reset_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    uid, name, _ = await resolve_target(update, context)
    if uid is None:
        return
    db.delete(update.effective_chat.id, f"warns_{uid}")
    await update.message.reply_html(f"✅ Warnings reset for {name}.")


async def warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    target = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
    chat_id = update.effective_chat.id
    warns_list = db.get(chat_id, f"warns_{target.id}") or []
    limit = await _get_limit(chat_id)
    if not warns_list:
        await msg.reply_html(f"{target.full_name} has no warnings.")
        return
    lines = "\n".join(f"{i+1}. {r}" for i, r in enumerate(warns_list))
    await msg.reply_html(
        f"<b>Warnings for {target.full_name}</b> ({len(warns_list)}/{limit}):\n{lines}"
    )


async def warn_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not context.args:
        limit = await _get_limit(update.effective_chat.id)
        await update.message.reply_text(f"Current warn limit: {limit}")
        return
    try:
        n = int(context.args[0])
        assert 1 <= n <= 20
    except (ValueError, AssertionError):
        await update.message.reply_text("❌ Limit must be a number between 1 and 20.")
        return
    db.set(update.effective_chat.id, "warn_limit", n)
    await update.message.reply_text(f"✅ Warn limit set to {n}.")


async def warn_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not context.args or context.args[0] not in ("ban", "kick", "mute"):
        mode = await _get_mode(update.effective_chat.id)
        await update.message.reply_text(f"Current warn mode: {mode}\nOptions: ban, kick, mute")
        return
    db.set(update.effective_chat.id, "warn_mode", context.args[0])
    await update.message.reply_text(f"✅ Warn mode set to {context.args[0]}.")
