# CSU Halal Menu Telegram Bot

This project is a production-ready Python Telegram bot that checks the Colorado State University Nutrislice menus at `https://csumenus.nutrislice.com/`, searches all discoverable dining locations for today's breakfast, lunch, and dinner menus, filters items containing `halal` case-insensitively, and sends the results through Telegram.

The bot now also:

- shows the highest-calorie Kosher Bistro item for lunch and dinner separately at the bottom of each menu message
- records sent-message stats in a durable database so stats survive restarts, redeploys, and free-host sleep cycles
- provides an admin-only `/stats` command for usage reporting

## Project Structure

```text
csuhalalmenu/
+-- .env.example
+-- .dockerignore
+-- .gitignore
+-- Dockerfile
+-- README.md
+-- bot.py
+-- config.py
+-- constants.py
+-- db.py
+-- formatter.py
+-- logging_config.py
+-- main.py
+-- menu_service.py
+-- models.py
+-- nutrislice_client.py
+-- requirements.txt
+-- render.yaml
+-- scheduler.py
+-- stats_service.py
+-- utils.py
+-- tests
    +-- test_formatter.py
    +-- test_menu_service.py
    +-- test_stats_service.py
```

## What The Bot Does

When a user presses `Todays Halal Menu`, the bot:

1. Discovers CSU dining locations from Nutrislice.
2. Fetches today's breakfast, lunch, and dinner menu data for each location.
3. Filters menu entries whose name or description contains `halal`, case-insensitively.
4. Deduplicates repeated food items within each meal and location.
5. Finds the highest-calorie Kosher Bistro lunch item and highest-calorie Kosher Bistro dinner item from The Foundry.
6. Sends a formatted Telegram message.

If nothing halal is found for the day, the bot still includes the Kosher Bistro section at the bottom.

## Kosher Bistro Output

The bot appends this section to the bottom of every manual and scheduled menu message:

```text
Kosher Bistro Main Foods:
Lunch:
- {item name} ({calories} cal)

Dinner:
- {item name} ({calories} cal)
```

Fallbacks:

- If no lunch item exists: `- No Kosher Bistro items found for lunch`
- If no dinner item exists: `- No Kosher Bistro items found for dinner`
- If items exist but calorie data is unavailable: `- Found Kosher Bistro items, but calorie data is unavailable`

## Installation

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

The requirements include:

- `python-telegram-bot[webhooks]` for both local polling and webhook deployment
- `SQLAlchemy` for database access
- `psycopg[binary]` for PostgreSQL-backed persistent stats

## Environment Setup

1. Copy `.env.example` to `.env`
2. Fill in the values:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
DAILY_SEND_HOUR=7
DAILY_SEND_MINUTE=0
TIMEZONE=America/Denver
USE_WEBHOOK=false
WEBHOOK_BASE_URL=
DATABASE_URL=postgresql://username:password@host:5432/database_name
ADMIN_CHAT_ID=your_admin_chat_id
ADMIN_USER_ID=
```

### Environment Variables

- `TELEGRAM_BOT_TOKEN`: Required. Telegram Bot API token from BotFather.
- `TELEGRAM_CHAT_ID`: Required. Chat ID that receives the scheduled daily menu message.
- `DAILY_SEND_HOUR`: Optional. Hour in 24-hour format. Default `7`.
- `DAILY_SEND_MINUTE`: Optional. Minute. Default `0`.
- `TIMEZONE`: Optional. IANA timezone name. Default `America/Denver`.
- `USE_WEBHOOK`: Optional. Set to `true` for webhook deployments such as Render web services.
- `WEBHOOK_BASE_URL`: Optional for local use. In webhook deployments, set this if your host does not provide `RENDER_EXTERNAL_URL`.
- `DATABASE_URL`: Required. Durable database connection string. Use PostgreSQL on hosted environments so stats survive restarts and free-host shutdowns.
- `ADMIN_CHAT_ID`: Required for admin stats access. Only this chat can use `/stats` unless `ADMIN_USER_ID` is also configured.
- `ADMIN_USER_ID`: Optional. Restricts `/stats` to a specific Telegram user ID.

## Persistent Stats Storage

The bot records every outgoing message attempt in a database-backed `message_logs` table.

Tracked fields include:

- `event_date`
- `chat_id`
- `message_type`
- `success`
- `sent_at`
- `failure_reason`

The bot also calculates daily and all-time aggregates for:

- total messages
- successful sends
- failed sends
- unique chats
- scheduled sends
- manual sends

### Why Remote DB Storage Matters

Free web hosts often sleep, restart, or redeploy services, which can wipe in-memory state and sometimes local writable storage. Because of that, this bot is designed to use a durable database through `DATABASE_URL` instead of relying on memory-only counters or temporary files.

For production or free-host deployments, use a remote PostgreSQL database.

## Admin Stats Command

Use the admin-only command:

```text
/stats
```

Example output:

```text
Bot Stats

Today (April 15, 2026):
- Total messages: 17
- Successful: 16
- Failed: 1
- Unique chats: 9
- Scheduled: 1
- Manual: 16

All-time:
- Total messages: 428
- Successful: 420
- Failed: 8
- Unique chats: 57
```

Access control:

- The bot checks `ADMIN_CHAT_ID`
- If `ADMIN_USER_ID` is set, it also allows that specific user
- Non-admin users receive an access denied response

## Running The Bot Locally

```bash
python main.py
```

On startup the bot will:

- validate required environment variables
- configure structured logging
- initialize the database schema if needed
- start Telegram polling locally, or webhook mode if configured
- start the daily scheduler

## Deploying Online

This repository includes both a `Dockerfile` and `render.yaml`, so it can be deployed to platforms like Render.

### Render Free Web Service Notes

You can deploy the bot as a free web service using Telegram webhooks, but there is an important limitation:

- free Render web services can sleep after inactivity
- webhook requests can wake them up
- in-process scheduled jobs may be delayed or skipped if the service is asleep

Because of that:

- the manual menu reply works reasonably well in webhook mode
- scheduled daily sends are best on always-on hosting or paid plans
- the stats data itself still survives, because it is stored in the database, not only in memory

### Deploy Steps

1. Push the project to GitHub.
2. Create a Render Blueprint or web service from the repo.
3. Set these environment variables in Render:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `DAILY_SEND_HOUR`
   - `DAILY_SEND_MINUTE`
   - `TIMEZONE`
   - `USE_WEBHOOK=true`
   - `DATABASE_URL`
   - `ADMIN_CHAT_ID`
   - optionally `ADMIN_USER_ID`
4. Deploy the service.

## How The Scheduler Works

The project uses `APScheduler` with `AsyncIOScheduler`.

- The scheduled send runs once per day using the configured hour and minute.
- The scheduler uses the configured timezone.
- It coalesces missed runs and limits concurrent executions to one instance.
- The scheduled message uses the same menu formatter and stats logging flow as the manual button-triggered reply.

## Troubleshooting

### Missing environment variables

If startup fails with a configuration error, check:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `DATABASE_URL`
- `ADMIN_CHAT_ID`

### Telegram messages are not arriving

- Verify the bot token is correct.
- Make sure the target chat has started a conversation with the bot.
- Double-check `TELEGRAM_CHAT_ID`.

### /stats does not work

- Make sure you are sending `/stats` from the configured `ADMIN_CHAT_ID`
- If using `ADMIN_USER_ID`, make sure it matches your Telegram user ID
- Check logs for database connectivity or permission issues

### Database connection errors

- Verify `DATABASE_URL` is valid
- For PostgreSQL, make sure the database is reachable from your host
- If your provider gives `postgres://...`, the app normalizes it automatically for SQLAlchemy/psycopg

### Free host restarted and stats still matter

That is exactly why this project uses database-backed storage. As long as `DATABASE_URL` points to a durable remote database, the stats survive bot restarts and redeploys.

## Tests

Run the included tests with:

```bash
pytest
```

The tests cover:

- halal filtering and cache reuse
- highest-calorie Kosher Bistro lunch item
- highest-calorie Kosher Bistro dinner item
- message formatting
- persistent stats logging and aggregate queries
