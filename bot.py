"""
RoseBot - Telegram Group Moderation Bot
Run with: python bot.py
"""

import logging
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ChatMemberHandler, filters
)
from config import BOT_TOKEN
from modules import (
    moderation, warnings, welcome, antispam,
    filters as filters_mod, notes, scheduler, admin, federation
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ── Admin / info ──────────────────────────────────────────────
    app.add_handler(CommandHandler("start",   admin.start))
    app.add_handler(CommandHandler("help",    admin.help_cmd))
    app.add_handler(CommandHandler("info",    admin.info))
    app.add_handler(CommandHandler("rules",   admin.rules))
    app.add_handler(CommandHandler("setrules",admin.set_rules))
    app.add_handler(CommandHandler("id",      admin.get_id))
    app.add_handler(CommandHandler("limits",  admin.limits))

    # ── Moderation ────────────────────────────────────────────────
    app.add_handler(CommandHandler("ban",     moderation.ban))
    app.add_handler(CommandHandler("unban",   moderation.unban))
    app.add_handler(CommandHandler("kick",    moderation.kick))
    app.add_handler(CommandHandler("mute",    moderation.mute))
    app.add_handler(CommandHandler("unmute",  moderation.unmute))
    app.add_handler(CommandHandler("tmute",   moderation.tmute))
    app.add_handler(CommandHandler("tban",    moderation.tban))
    app.add_handler(CommandHandler("purge",   moderation.purge))
    app.add_handler(CommandHandler("del",     moderation.delete_msg))
    app.add_handler(CommandHandler("approve", moderation.approve))
    app.add_handler(CommandHandler("unapprove",moderation.unapprove))
    app.add_handler(CommandHandler("pin",     moderation.pin))
    app.add_handler(CommandHandler("unpin",   moderation.unpin))

    # ── Warnings ──────────────────────────────────────────────────
    app.add_handler(CommandHandler("warn",    warnings.warn))
    app.add_handler(CommandHandler("unwarn",  warnings.unwarn))
    app.add_handler(CommandHandler("resetwarns", warnings.reset_warns))
    app.add_handler(CommandHandler("warns",   warnings.warns))
    app.add_handler(CommandHandler("warnlimit", warnings.warn_limit))
    app.add_handler(CommandHandler("warnmode",  warnings.warn_mode))

    # ── Welcome / Goodbye ─────────────────────────────────────────
    app.add_handler(CommandHandler("welcome",   welcome.welcome_toggle))
    app.add_handler(CommandHandler("setwelcome",welcome.set_welcome))
    app.add_handler(CommandHandler("goodbye",   welcome.goodbye_toggle))
    app.add_handler(CommandHandler("setgoodbye",welcome.set_goodbye))
    app.add_handler(CommandHandler("resetwelcome", welcome.reset_welcome))
    app.add_handler(CommandHandler("captcha",   welcome.captcha_toggle))
    app.add_handler(ChatMemberHandler(welcome.greet_member,
                                      ChatMemberHandler.CHAT_MEMBER))

    # ── Anti-spam ─────────────────────────────────────────────────
    app.add_handler(CommandHandler("antiflood",  antispam.antiflood))
    app.add_handler(CommandHandler("setflood",   antispam.set_flood))
    app.add_handler(CommandHandler("floodmode",  antispam.flood_mode))
    app.add_handler(CommandHandler("lock",       antispam.lock))
    app.add_handler(CommandHandler("unlock",     antispam.unlock))
    app.add_handler(CommandHandler("locks",      antispam.locks))
    app.add_handler(CommandHandler("blocklist",  antispam.blocklist))
    app.add_handler(CommandHandler("addblocklist",antispam.add_blocklist))
    app.add_handler(CommandHandler("rmblocklist", antispam.rm_blocklist))
    app.add_handler(CommandHandler("blocklistmode",antispam.blocklist_mode))
    app.add_handler(CommandHandler("antiraid",   antispam.antiraid))

    # ── Filters ───────────────────────────────────────────────────
    app.add_handler(CommandHandler("filter",    filters_mod.add_filter))
    app.add_handler(CommandHandler("filters",   filters_mod.list_filters))
    app.add_handler(CommandHandler("stop",      filters_mod.remove_filter))
    app.add_handler(CommandHandler("stopall",   filters_mod.remove_all_filters))

    # ── Notes ─────────────────────────────────────────────────────
    app.add_handler(CommandHandler("save",      notes.save_note))
    app.add_handler(CommandHandler("get",       notes.get_note))
    app.add_handler(CommandHandler("notes",     notes.list_notes))
    app.add_handler(CommandHandler("clear",     notes.clear_note))
    app.add_handler(CommandHandler("clearall",  notes.clear_all_notes))

    # ── Scheduler / Echo ──────────────────────────────────────────
    app.add_handler(CommandHandler("echo",      scheduler.echo))
    app.add_handler(CommandHandler("say",       scheduler.say))
    app.add_handler(CommandHandler("broadcast", scheduler.broadcast))
    app.add_handler(CommandHandler("schedule",  scheduler.schedule_msg))
    app.add_handler(CommandHandler("unschedule",scheduler.unschedule))
    app.add_handler(CommandHandler("scheduled", scheduler.list_scheduled))

    # ── Federations ───────────────────────────────────────────────
    app.add_handler(CommandHandler("newfed",    federation.new_fed))
    app.add_handler(CommandHandler("delfed",    federation.del_fed))
    app.add_handler(CommandHandler("joinfed",   federation.join_fed))
    app.add_handler(CommandHandler("leavefed",  federation.leave_fed))
    app.add_handler(CommandHandler("fban",      federation.fban))
    app.add_handler(CommandHandler("unfban",    federation.unfban))
    app.add_handler(CommandHandler("fedinfo",   federation.fed_info))
    app.add_handler(CommandHandler("fedbans",   federation.fed_bans))
    app.add_handler(CommandHandler("fadmin",    federation.fed_admin))
    app.add_handler(CommandHandler("fpromote",  federation.fed_promote))
    app.add_handler(CommandHandler("fdemote",   federation.fed_demote))

    # ── Message listeners ────────────────────────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                   antispam.check_flood))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                   antispam.check_blocklist))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                   filters_mod.check_filters))
    app.add_handler(MessageHandler(filters.TEXT,
                                   notes.check_note_trigger))

    logger.info("Bot is running…")
    app.run_polling(allowed_updates=["message", "chat_member", "callback_query"])


if __name__ == "__main__":
    main()
