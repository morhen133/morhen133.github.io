# UX Weekly Shortlist Telegram Bot

A Telegram bot that sends you the best UX design links from the last week every week at 10:00, plus an inline button to fetch the shortlist on demand.

## Features
- Weekly digest scheduled via Telegram JobQueue
- Aggregates from curated UX RSS feeds (NN/g, Smashing Magazine UX, Sidebar, UX Collective, UX Planet, A List Apart)
- Inline button: "Get shortlist now"
- Simple file-based subscriber list (`data/subscribers.json`)

## Setup
1. Create a Telegram bot with BotFather and get the token.
2. Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN` and `TIMEZONE`.
3. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

4. Run the bot:

```bash
python bot.py
```

The weekly digest defaults to Monday 10:00 in your `TIMEZONE`. You can change weekday/hour via env vars: `DISPATCH_WEEKDAY`, `DISPATCH_HOUR`, `DISPATCH_MINUTE`.

## Commands
- `/start` – subscribe and receive the inline button
- `/shortlist` – fetch the latest 7‑day shortlist immediately
- `/unsubscribe` – stop receiving weekly messages
- `/help` – list commands

## Notes
- The shortlist ranks by recency across multiple feeds; you can extend ranking heuristics if needed.
- The bot stores subscribers under `data/subscribers.json`.