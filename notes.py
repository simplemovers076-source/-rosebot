"""
modules/notes.py — /save, /get, /notes, /clear, /clearall, #notename trigger
"""

from telegram import Update
from telegram.ext import ContextTypes

import db
from config import MAX_NOTES
from helpers import require_admin


async def save_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    msg = update.message
    if not context.args:
        await msg.reply_html("Usage: /save &lt;name&gt; &lt;text&gt;\nOr reply to a message with /save &lt;name&gt;")
        return

    name = context.args[0].lower()
    content = " ".join(context.args[1:])

    if not content and msg.reply_to_message:
        content = msg.reply_to_message.text or msg.reply_to_message.caption or ""

    if not content:
        await msg.reply_text("Provide the note content or reply to a message.")
        return

    cid = update.effective_chat.id
    notes_dict = db.get(cid, "notes") or {}

    if name not in notes_dict and len(notes_dict) >= MAX_NOTES:
        await msg.reply_text(f"❌ Maximum notes limit ({MAX_NOTES}) reached.")
        return

    notes_dict[name] = content
    db.set(cid, "notes", notes_dict)
    await msg.reply_html(f"✅ Note saved: <code>{name}</code>\nRetrieve with /get {name} or #{name}")


async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /get <note_name>")
        return
    name = context.args[0].lower()
    cid  = update.effective_chat.id
    notes_dict = db.get(cid, "notes") or {}
    if name not in notes_dict:
        await update.message.reply_text(f"No note found: {name}")
        return
    await update.message.reply_html(notes_dict[name])


async def list_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    notes_dict = db.get(cid, "notes") or {}
    if not notes_dict:
        await update.message.reply_text("No notes saved in this group.")
        return
    lines = "\n".join(f"• <code>#{k}</code>" for k in sorted(notes_dict.keys()))
    await update.message.reply_html(
        f"<b>Notes ({len(notes_dict)}/{MAX_NOTES}):</b>\n{lines}\n\n"
        "Retrieve with /get &lt;name&gt; or #name"
    )


async def clear_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /clear <note_name>")
        return
    name = context.args[0].lower()
    cid  = update.effective_chat.id
    notes_dict = db.get(cid, "notes") or {}
    if name in notes_dict:
        del notes_dict[name]
        db.set(cid, "notes", notes_dict)
        await update.message.reply_text(f"✅ Note deleted: {name}")
    else:
        await update.message.reply_text(f"No note found: {name}")


async def clear_all_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    db.delete(update.effective_chat.id, "notes")
    await update.message.reply_text("✅ All notes deleted.")


async def check_note_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respond to #notename in messages."""
    if not update.effective_message or not update.effective_message.text:
        return
    text = update.effective_message.text
    cid  = update.effective_chat.id
    notes_dict = db.get(cid, "notes") or {}
    if not notes_dict:
        return
    words = text.split()
    for word in words:
        if word.startswith("#") and len(word) > 1:
            name = word[1:].lower()
            if name in notes_dict:
                await update.message.reply_html(notes_dict[name])
                return
