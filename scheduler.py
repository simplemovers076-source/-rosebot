"""
modules/scheduler.py — /echo, /say, /broadcast, /schedule, /unschedule, /scheduled
"""

import asyncio
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes

import db
from helpers import require_admin, parse_time
from config import OWNER_ID, SUDO_USERS

# In-memory task registry: {chat_id: {note_name: asyncio.Task}}
_tasks: dict[int, dict[str, asyncio.Task]] = {}


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /echo <text>")
        return
    try:
        await update.message.delete()
    except Exception:
        pass
    await context.bot.send_message(update.effective_chat.id, text, parse_mode="HTML")


async def say(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await echo(update, context)


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message to all groups the bot is in. Owner only."""
    if update.effective_user.id not in [OWNER_ID] + SUDO_USERS:
        await update.message.reply_text("⛔ Owner only.")
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /broadcast <text>")
        return
    import os, json
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    sent = 0
    for fname in os.listdir(data_dir):
        if fname.startswith("_") or not fname.endswith(".json"):
            continue
        chat_id = int(fname[:-5])
        try:
            await context.bot.send_message(chat_id, text, parse_mode="HTML")
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ Broadcast sent to {sent} chats.")


async def schedule_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /schedule <interval> <note_name>
    Sends the saved note at the given interval (e.g. 30m, 2h, 1d).
    """
    if not await require_admin(update, context):
        return
    if len(context.args) < 2:
        await update.message.reply_html(
            "Usage: /schedule &lt;interval&gt; &lt;note_name&gt;\n"
            "Example: /schedule 1h rules\n"
            "The note must already be saved with /save."
        )
        return

    interval_str = context.args[0]
    note_name    = context.args[1].lower()
    delta        = parse_time(interval_str)

    if delta is None:
        await update.message.reply_text("❌ Invalid interval. Use 30s, 10m, 2h, 1d, 1w.")
        return

    cid = update.effective_chat.id
    notes_dict = db.get(cid, "notes") or {}
    if note_name not in notes_dict:
        await update.message.reply_text(f"❌ No note named '{note_name}'. Save it first with /save.")
        return

    # Save schedule to DB
    scheduled = db.get(cid, "scheduled") or {}
    scheduled[note_name] = {"interval": interval_str, "seconds": int(delta.total_seconds())}
    db.set(cid, "scheduled", scheduled)

    # Start async task
    _start_schedule_task(context, cid, note_name, int(delta.total_seconds()), notes_dict[note_name])
    await update.message.reply_text(
        f"✅ '{note_name}' will be sent every {interval_str}."
    )


def _start_schedule_task(context, chat_id: int, note_name: str, seconds: int, text: str):
    if chat_id not in _tasks:
        _tasks[chat_id] = {}
    existing = _tasks[chat_id].get(note_name)
    if existing and not existing.done():
        existing.cancel()

    async def _loop():
        while True:
            await asyncio.sleep(seconds)
            try:
                await context.bot.send_message(chat_id, text, parse_mode="HTML")
            except Exception:
                break

    _tasks[chat_id][note_name] = asyncio.create_task(_loop())


async def unschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /unschedule <note_name>")
        return
    note_name = context.args[0].lower()
    cid = update.effective_chat.id
    scheduled = db.get(cid, "scheduled") or {}
    if note_name not in scheduled:
        await update.message.reply_text(f"No schedule found for '{note_name}'.")
        return
    del scheduled[note_name]
    db.set(cid, "scheduled", scheduled)
    # Cancel task if running
    task = _tasks.get(cid, {}).get(note_name)
    if task and not task.done():
        task.cancel()
    await update.message.reply_text(f"✅ Unscheduled '{note_name}'.")


async def list_scheduled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    scheduled = db.get(cid, "scheduled") or {}
    if not scheduled:
        await update.message.reply_text("No scheduled messages in this group.")
        return
    lines = "\n".join(
        f"• <code>{name}</code> — every {info['interval']}"
        for name, info in scheduled.items()
    )
    await update.message.reply_html(f"<b>Scheduled messages:</b>\n{lines}")
