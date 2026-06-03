"""
modules/admin.py — /start, /help, /info, /rules, /id, /limits
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

import db
from config import BOT_NAME, MAX_FILTERS, MAX_NOTES, MAX_BLOCKLIST
from helpers import require_admin, fmt_user

HELP_TEXT = f"""
<b>{BOT_NAME} — Command Reference</b>

<b>Moderation</b>
/ban, /unban, /tban &lt;time&gt; — Ban users
/kick — Kick a user
/mute, /unmute, /tmute &lt;time&gt; — Mute users
/purge — Delete messages up to a reply
/del — Delete a replied message
/approve, /unapprove — Approve users (bypass locks)
/pin, /unpin — Pin messages

<b>Warnings</b>
/warn, /unwarn, /resetwarns — Manage warnings
/warns — View a user's warnings
/warnlimit &lt;n&gt; — Set warn limit (default 3)
/warnmode &lt;ban|kick|mute&gt; — Set action on limit

<b>Anti-Spam</b>
/antiflood &lt;on|off&gt; — Toggle flood protection
/setflood &lt;n&gt; — Messages per 10s before action
/floodmode &lt;ban|kick|mute&gt; — Flood action
/lock &lt;type&gt;, /unlock &lt;type&gt;, /locks — Message locks
/blocklist, /addblocklist, /rmblocklist — Keyword blocklist
/blocklistmode &lt;ban|kick|mute|warn&gt; — Blocklist action
/antiraid &lt;on|off&gt; — Toggle raid protection

<b>Welcome / Goodbye</b>
/welcome &lt;on|off&gt; — Toggle welcome messages
/setwelcome &lt;text&gt; — Set welcome message
/goodbye &lt;on|off&gt; — Toggle goodbye messages
/setgoodbye &lt;text&gt; — Set goodbye message
/resetwelcome — Reset to default
/captcha &lt;on|off&gt; — Toggle join captcha

<b>Filters</b>
/filter &lt;keyword&gt; &lt;reply&gt; — Add a filter
/filters — List all filters
/stop &lt;keyword&gt; — Remove a filter
/stopall — Remove all filters

<b>Notes</b>
/save &lt;name&gt; &lt;text&gt; — Save a note
/get &lt;name&gt; or #name — Retrieve a note
/notes — List all notes
/clear &lt;name&gt; — Delete a note
/clearall — Delete all notes

<b>Scheduler / Echo</b>
/echo &lt;text&gt; — Make bot say something
/say &lt;text&gt; — Alias for /echo
/broadcast &lt;text&gt; — Send to all groups
/schedule &lt;interval&gt; &lt;note&gt; — Schedule a note
/unschedule &lt;name&gt; — Remove a schedule
/scheduled — List scheduled messages

<b>Federations</b>
/newfed &lt;name&gt; — Create a federation
/delfed — Delete your federation
/joinfed &lt;id&gt; — Join a federation
/leavefed — Leave a federation
/fban, /unfban — Federation ban/unban
/fedinfo, /fedbans — Federation info
/fpromote, /fdemote — Manage fed admins

<b>Info</b>
/info — User info
/rules — Group rules
/setrules &lt;text&gt; — Set rules (admin)
/id — Get user/chat IDs
/limits — Show bot limits
/help — This message
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        f"👋 Hi! I'm <b>{BOT_NAME}</b>, a full-featured group moderation bot.\n\n"
        f"Add me to a group and make me admin to get started.\n"
        f"Use /help to see all commands."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(HELP_TEXT)


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    target = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user

    try:
        member = await update.effective_chat.get_member(target.id)
        status = member.status
    except BadRequest:
        status = "unknown"

    warns = db.get(update.effective_chat.id, f"warns_{target.id}") or []
    text = (
        f"<b>User Info</b>\n"
        f"Name: {target.full_name}\n"
        f"ID: <code>{target.id}</code>\n"
        f"Username: @{target.username or 'none'}\n"
        f"Status: {status}\n"
        f"Warnings: {len(warns)}\n"
        f'<a href="tg://user?id={target.id}">Link</a>'
    )
    await msg.reply_html(text)


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    r = db.get(chat_id, "rules")
    if not r:
        await update.message.reply_text("No rules have been set for this group.")
    else:
        await update.message.reply_html(f"<b>Rules for {update.effective_chat.title}:</b>\n\n{r}")


async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    text = " ".join(context.args) or (
        update.message.reply_to_message.text if update.message.reply_to_message else None
    )
    if not text:
        await update.message.reply_text("Usage: /setrules <rules text>")
        return
    db.set(update.effective_chat.id, "rules", text)
    await update.message.reply_text("✅ Rules updated.")


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat = update.effective_chat
    user = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
    await msg.reply_html(
        f"<b>IDs</b>\n"
        f"User: <code>{user.id}</code>\n"
        f"Chat: <code>{chat.id}</code>"
    )


async def limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        f"<b>Bot Limits</b>\n"
        f"Filters per group: {MAX_FILTERS}\n"
        f"Notes per group:   {MAX_NOTES}\n"
        f"Blocklist entries: {MAX_BLOCKLIST}"
    )
