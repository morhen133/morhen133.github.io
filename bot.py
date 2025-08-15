import json
import os
from datetime import datetime, timedelta, timezone, time as dt_time
from typing import List

import pytz
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

from news import fetch_ux_news, format_news_digest


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SUBSCRIBERS_FILE = os.path.join(DATA_DIR, "subscribers.json")


def ensure_data_dir() -> None:
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.isfile(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def load_subscribers() -> List[int]:
    ensure_data_dir()
    try:
        with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [int(x) for x in data]
    except Exception:
        return []


def save_subscribers(chat_ids: List[int]) -> None:
    ensure_data_dir()
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sorted(set(int(x) for x in chat_ids))), f)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    subs = load_subscribers()
    if chat_id not in subs:
        subs.append(chat_id)
        save_subscribers(subs)

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Get shortlist now", callback_data="get_now")]]
    )
    await update.message.reply_text(
        "Subscribed. You'll receive a weekly UX design shortlist every week at 10:00.\n"
        "Tap the button anytime to fetch the latest shortlist.",
        reply_markup=keyboard,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Get shortlist now", callback_data="get_now")]]
    )
    await update.message.reply_text(
        "/start – subscribe to weekly shortlist\n"
        "/shortlist – get this week's shortlist now\n"
        "/unsubscribe – stop receiving weekly messages",
        reply_markup=keyboard,
    )


async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    subs = load_subscribers()
    if chat_id in subs:
        subs.remove(chat_id)
        save_subscribers(subs)
        await update.message.reply_text("Unsubscribed. You will no longer receive the weekly shortlist.")
    else:
        await update.message.reply_text("You are not subscribed.")


async def cmd_shortlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_shortlist(update.effective_chat.id, context)


async def on_get_now_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await _send_shortlist(update.effective_chat.id, context)


async def _send_shortlist(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    items = fetch_ux_news(since, limit=5)
    text = format_news_digest(items)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Get shortlist now", callback_data="get_now")]]
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


async def weekly_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    subs = load_subscribers()
    if not subs:
        return

    since = datetime.now(timezone.utc) - timedelta(days=7)
    items = fetch_ux_news(since, limit=5)
    text = format_news_digest(items)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Get shortlist now", callback_data="get_now")]]
    )

    for chat_id in subs:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard,
            )
        except Exception:
            continue


def _weekday_to_int(weekday_str: str) -> int:
    mapping = {
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    }
    return mapping.get(weekday_str.strip().lower(), 0)


def main() -> None:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set. Create a .env with TELEGRAM_BOT_TOKEN=<token> or export it.")

    timezone_name = os.getenv("TIMEZONE", "UTC")
    tz = pytz.timezone(timezone_name)

    dispatch_hour = int(os.getenv("DISPATCH_HOUR", "10"))
    dispatch_minute = int(os.getenv("DISPATCH_MINUTE", "0"))
    dispatch_weekday = _weekday_to_int(os.getenv("DISPATCH_WEEKDAY", "mon"))

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("shortlist", cmd_shortlist))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))
    app.add_handler(CallbackQueryHandler(on_get_now_button, pattern="^get_now$"))

    run_time = dt_time(hour=dispatch_hour, minute=dispatch_minute, tzinfo=tz)
    app.job_queue.run_daily(weekly_job, time=run_time, days=(dispatch_weekday,))

    print(
        f"Bot started. Weekly shortlist scheduled for {timezone_name} on weekday {dispatch_weekday} at {dispatch_hour:02d}:{dispatch_minute:02d}."
    )

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()