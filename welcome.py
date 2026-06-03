"""
modules/welcome.py — welcome, goodbye, captcha
"""

import asyncio
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus

import db
from helpers import require_admin

DEFAULT_WELCOME = "👋 Welcome to {chat}, {name}! Please read the /rules."
DEFAULT_GOODBYE = "👋 {name} has left the group."

CAPTCHA_PERMS   = ChatPermissions(can_send_messages=False)
VERIFIED_PERMS  = ChatPermissions(
    can_send_messages=True, can_send_audios=True, can_send_documents=True,
    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
    can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
)

_pending_captcha: dict[tuple[int, int], int] = {}  # (chat_id, user_id) -> message_id


def _fmt(template: str, user, chat) -> str:
    return (template
            .replace("{name}", user.full_name or user.first_name)
            .replace("{username}", f"@{user.username}" if user.username else user.first_name)
            .replace("{chat}", chat.title or "this group")
            .replace("{id}", str(user.id)))


async def greet_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    user  = result.new_chat_member.user
    chat  = result.chat
    cid   = chat.id

    # ── New member joined ─────────────────────────────────────────
    if old_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED) and \
       new_status == ChatMemberStatus.MEMBER:

        # Captcha
        if db.get(cid, "captcha"):
            try:
                await chat.restrict_member(user.id, CAPTCHA_PERMS)
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "✅ I'm not a bot — tap to verify",
                        callback_data=f"captcha_{user.id}"
                    )
                ]])
                msg = await context.bot.send_message(
                    cid,
                    f"👤 {user.full_name}, please verify you're human within 60 seconds.",
                    reply_markup=kb
                )
                _pending_captcha[(cid, user.id)] = msg.message_id
                asyncio.create_task(_captcha_timeout(context, cid, user.id, msg.message_id))
            except Exception:
                pass
            return

        # Welcome message
        if db.get(cid, "welcome") is not False:
            template = db.get(cid, "welcome_text") or DEFAULT_WELCOME
            try:
                await context.bot.send_message(cid, _fmt(template, user, chat), parse_mode="HTML")
            except Exception:
                pass

    # ── Member left ───────────────────────────────────────────────
    elif new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED) and \
         old_status == ChatMemberStatus.MEMBER:
        if db.get(cid, "goodbye"):
            template = db.get(cid, "goodbye_text") or DEFAULT_GOODBYE
            try:
                await context.bot.send_message(cid, _fmt(template, user, chat), parse_mode="HTML")
            except Exception:
                pass


async def _captcha_timeout(context, chat_id: int, user_id: int, msg_id: int):
    await asyncio.sleep(60)
    if (chat_id, user_id) in _pending_captcha:
        del _pending_captcha[(chat_id, user_id)]
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass


async def captcha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the captcha button press."""
    query = update.callback_query
    data  = query.data
    if not data.startswith("captcha_"):
        return
    uid = int(data.split("_")[1])
    if query.from_user.id != uid:
        await query.answer("This button isn't for you!", show_alert=True)
        return
    cid = query.message.chat_id
    _pending_captcha.pop((cid, uid), None)
    try:
        await query.message.chat.restrict_member(uid, VERIFIED_PERMS)
        await query.message.delete()
        await query.answer("✅ Verified! Welcome.")
    except Exception as e:
        await query.answer(f"Error: {e}", show_alert=True)


# ── Admin commands ────────────────────────────────────────────────────────────

async def welcome_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    arg = context.args[0].lower() if context.args else None
    if arg not in ("on", "off"):
        state = db.get(update.effective_chat.id, "welcome")
        status = "off" if state is False else "on"
        await update.message.reply_text(f"Welcome messages are currently {status}. Use /welcome on|off")
        return
    db.set(update.effective_chat.id, "welcome", arg != "off")
    await update.message.reply_text(f"✅ Welcome messages turned {arg}.")


async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    text = " ".join(context.args) or (
        update.message.reply_to_message.text if update.message.reply_to_message else None
    )
    if not text:
        await update.message.reply_html(
            "Usage: /setwelcome &lt;text&gt;\n\n"
            "Variables: {name}, {username}, {chat}, {id}"
        )
        return
    db.set(update.effective_chat.id, "welcome_text", text)
    db.set(update.effective_chat.id, "welcome", True)
    await update.message.reply_text("✅ Welcome message set.")


async def goodbye_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    arg = context.args[0].lower() if context.args else None
    if arg not in ("on", "off"):
        state = "on" if db.get(update.effective_chat.id, "goodbye") else "off"
        await update.message.reply_text(f"Goodbye messages are currently {state}. Use /goodbye on|off")
        return
    db.set(update.effective_chat.id, "goodbye", arg == "on")
    await update.message.reply_text(f"✅ Goodbye messages turned {arg}.")


async def set_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    text = " ".join(context.args) or (
        update.message.reply_to_message.text if update.message.reply_to_message else None
    )
    if not text:
        await update.message.reply_html(
            "Usage: /setgoodbye &lt;text&gt;\n\nVariables: {name}, {username}, {chat}, {id}"
        )
        return
    db.set(update.effective_chat.id, "goodbye_text", text)
    db.set(update.effective_chat.id, "goodbye", True)
    await update.message.reply_text("✅ Goodbye message set.")


async def reset_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    cid = update.effective_chat.id
    db.delete(cid, "welcome_text")
    db.delete(cid, "goodbye_text")
    await update.message.reply_text("✅ Welcome and goodbye messages reset to default.")


async def captcha_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    arg = context.args[0].lower() if context.args else None
    if arg not in ("on", "off"):
        state = "on" if db.get(update.effective_chat.id, "captcha") else "off"
        await update.message.reply_text(f"Captcha is currently {state}. Use /captcha on|off")
        return
    db.set(update.effective_chat.id, "captcha", arg == "on")
    await update.message.reply_text(f"✅ Captcha turned {arg}.")
