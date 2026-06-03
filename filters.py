"""
modules/filters.py — keyword filters that auto-reply when a word is detected
/filter <keyword> <reply>
/filters
/stop <keyword>
/stopall
"""

import re
from telegram import Update
from telegram.ext import ContextTypes

import db
from config import MAX_FILTERS
from helpers import require_admin


async def add_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    msg = update.message
    if not context.args:
        await msg.reply_text("Usage: /filter <keyword> <reply text>\nOr reply to a message with /filter <keyword>")
        return

    keyword = context.args[0].lower()
    reply_text = " ".join(context.args[1:])

    if not reply_text and msg.reply_to_message:
        reply_text = msg.reply_to_message.text or ""

    if not reply_text:
        await msg.reply_text("You need to provide a reply text (or reply to a message).")
        return

    cid = update.effective_chat.id
    filters_dict = db.get(cid, "filters") or {}

    if len(filters_dict) >= MAX_FILTERS:
        await msg.reply_text(f"❌ Maximum filter limit ({MAX_FILTERS}) reached.")
        return

    filters_dict[keyword] = reply_text
    db.set(cid, "filters", filters_dict)
    await msg.reply_text(f"✅ Filter added for: <code>{keyword}</code>", parse_mode="HTML")


async def list_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    filters_dict = db.get(cid, "filters") or {}
    if not filters_dict:
        await update.message.reply_text("No filters active in this group.")
        return
    lines = "\n".join(f"• <code>{k}</code>" for k in sorted(filters_dict.keys()))
    await update.message.reply_html(f"<b>Active filters ({len(filters_dict)}/{MAX_FILTERS}):</b>\n{lines}")


async def remove_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /stop <keyword>")
        return
    keyword = context.args[0].lower()
    cid = update.effective_chat.id
    filters_dict = db.get(cid, "filters") or {}
    if keyword in filters_dict:
        del filters_dict[keyword]
        db.set(cid, "filters", filters_dict)
        await update.message.reply_text(f"✅ Filter removed: {keyword}")
    else:
        await update.message.reply_text(f"No filter found for: {keyword}")


async def remove_all_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    db.delete(update.effective_chat.id, "filters")
    await update.message.reply_text("✅ All filters removed.")


async def check_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_message.text:
        return
    cid = update.effective_chat.id
    filters_dict = db.get(cid, "filters") or {}
    if not filters_dict:
        return
    text_lower = update.effective_message.text.lower()
    for keyword, reply in filters_dict.items():
        pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
        if pattern.search(text_lower):
            await update.message.reply_html(reply)
            return  # only trigger first match
