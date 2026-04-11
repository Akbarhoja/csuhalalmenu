# CSU Halal Menu Telegram Bot

This project is a production-ready Python Telegram bot that checks the Colorado State University Nutrislice menus at `https://csumenus.nutrislice.com/`, searches all discoverable dining locations for today's breakfast, lunch, and dinner menus, filters items containing `halal` case-insensitively, and sends the results through Telegram.

The bot supports:

- A single visible reply-keyboard button: `Todays Halal Menu`
- On-demand halal menu lookups for today
- One automatic daily Telegram message to a predefined chat ID
- Configurable schedule and timezone
- Logging, retry logic, graceful parsing, and duplicate filtering

## Project Structure

```text
csu-halal-bot/
├── .env.example
├── .dockerignore
├── .gitignore
├── Dockerfile
├── README.md
├── bot.py
├── config.py
├── constants.py
├── formatter.py
├── logging_config.py
├── main.py
├── menu_service.py
├── models.py
├── nutrislice_client.py
├── requirements.txt
├── render.yaml
├── scheduler.py
├── utils.py
└── tests
    ├── test_formatter.py
    └── test_menu_service.py
```

## What The Bot Does

When a user presses `Todays Halal Menu`, the bot:

1. Discovers CSU dining locations from Nutrislice.
2. Fetches today's breakfast, lunch, and dinner menu data for each location.
3. Filters menu entries whose name or description contains `halal`, case-insensitively.
4. Deduplicates repeated food items within each meal and location.
5. Sends a formatted Telegram message.

If nothing halal is found for the day, the bot sends:

```text
Meow, meow! No halal options were found for today.
```

## Installation

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

The requirements include the `webhooks` extra for `python-telegram-bot`, so the same install works for both local polling and Render webhook deployments.

## Environment Setup

1. Copy `.env.example` to `.env`
2. Fill in the values:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
DAILY_SEND_HOUR=7
DAILY_SEND_MINUTE=0
TIMEZONE=America/Denver
```

### Environment Variables

- `TELEGRAM_BOT_TOKEN`: Required. Telegram Bot API token from BotFather.
- `TELEGRAM_CHAT_ID`: Required. Chat ID that receives the scheduled daily message.
- `DAILY_SEND_HOUR`: Optional. Hour in 24-hour format. Default `7`.
- `DAILY_SEND_MINUTE`: Optional. Minute. Default `0`.
- `TIMEZONE`: Optional. IANA timezone name. Default `America/Denver`.
- `USE_WEBHOOK`: Optional. Set to `true` for webhook deployments such as Render web services.
- `WEBHOOK_BASE_URL`: Optional for local use. In webhook deployments, set this to your public app URL if your host does not provide `RENDER_EXTERNAL_URL`.

## Running The Bot

```bash
python main.py
```

On startup the bot will:

- Validate required environment variables
- Configure structured logging
- Start Telegram polling
- Start the daily scheduler

## Deploying Online

The bot should be deployed as an always-on background worker because it uses Telegram polling and an in-process daily scheduler.

### Option 1: Render Free Web Service

This repository now includes both a `Dockerfile` and `render.yaml`, so it can be deployed to Render as a free web service using Telegram webhooks instead of polling.

1. Push the project to GitHub.
2. Sign in to Render.
3. Click `New +` and choose `Blueprint`.
4. Connect the GitHub repository.
5. Render will detect `render.yaml` and create a web service named `csu-halal-bot`.
6. Set these environment variables in Render:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `DAILY_SEND_HOUR`
   - `DAILY_SEND_MINUTE`
   - `TIMEZONE`
   - `USE_WEBHOOK=true`
7. Deploy the worker.

After deployment, the bot will stay online even when your computer is off.

Important: Render free web services can sleep after inactivity. That means webhook replies usually work after a short cold start, but the in-process daily scheduled message may be unreliable unless you keep the app awake with an external uptime monitor.

### Option 2: Any Docker-Based Host

You can also deploy the bot anywhere Docker is supported, including Railway, Fly.io, DigitalOcean, or your own VPS.

Build the image:

```bash
docker build -t csu-halal-bot .
```

Run it with environment variables:

```bash
docker run --env-file .env csu-halal-bot
```

## How The Scheduler Works

The project uses `APScheduler` with `AsyncIOScheduler`, which is well suited for a continuously running async Python process.

- The scheduled send runs once per day using the configured hour and minute.
- The scheduler uses the configured timezone.
- It coalesces missed runs and limits concurrent executions to one instance.
- The scheduled message uses the same formatter as the on-demand button flow.

## Troubleshooting

### Missing environment variables

If startup fails with a configuration error, make sure `.env` exists and includes:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### Telegram messages are not arriving

- Verify the bot token is correct.
- Make sure the target chat has started a conversation with the bot.
- Double-check `TELEGRAM_CHAT_ID`.

### The bot works locally but not online

- Make sure the hosting platform runs it as a worker or background service, not a web app.
- Confirm all environment variables are configured in the host dashboard.
- Check the host logs for startup, Telegram authentication, or Nutrislice request errors.
- If your bot token was shared in chat or logs, rotate it in BotFather and update the hosted environment variable.

### Nutrislice location discovery fails

The bot first tries Nutrislice JSON discovery endpoints and then falls back to homepage parsing. If CSU changes their Nutrislice site structure, review `nutrislice_client.py` and update the discovery logic.

### No halal items are returned

- The bot only checks today's menus.
- It only matches items containing the word `halal` in the item name or description.
- If CSU does not publish halal text on the menu for that day, the bot will return no results.

### Scheduler timing looks off

Check that `TIMEZONE` is a valid IANA timezone such as `America/Denver`.

## Tests

Run the included tests with:

```bash
pytest
```


