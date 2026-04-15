# CSU Halal Menu Telegram Bot

This project is a Python Telegram bot that checks the Colorado State University Nutrislice menus at `https://csumenus.nutrislice.com/`, searches all discoverable dining locations for today's breakfast, lunch, and dinner menus, filters items containing `halal` case-insensitively, and sends the results through Telegram.

The bot also:

- shows the highest-calorie Kosher Bistro item for lunch and dinner separately at the bottom of each menu message
- sends an admin notification whenever a user manually requests today's halal menu
- supports a daily scheduled menu message

## Project Structure

```text
csuhalalmenu/
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
├── notifications.py
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
5. Finds the highest-calorie Kosher Bistro lunch item and highest-calorie Kosher Bistro dinner item from The Foundry.
6. Sends a formatted Telegram message to the user.
7. Sends a separate notification message to the configured admin chat.

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

## Admin Usage Notification

Every time a user manually requests today's halal menu, the bot sends an admin notification to `ADMIN_CHAT_ID`.

Example notification:

```text
This user used the bot:
- Name: John Doe
- Username: @johndoe
- User ID: 123456789
- Chat ID: 123456789
- Time: April 15, 2026 07:30 PM MDT
- Action: Requested Today's Halal Menu
```

If the admin notification fails, the bot logs the error and still replies to the user normally.

## Installation

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

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
ADMIN_CHAT_ID=your_admin_chat_id
```

### Environment Variables

- `TELEGRAM_BOT_TOKEN`: Required. Telegram Bot API token from BotFather.
- `TELEGRAM_CHAT_ID`: Required. Chat ID that receives the scheduled daily menu message.
- `DAILY_SEND_HOUR`: Optional. Hour in 24-hour format. Default `7`.
- `DAILY_SEND_MINUTE`: Optional. Minute. Default `0`.
- `TIMEZONE`: Optional. IANA timezone name. Default `America/Denver`.
- `USE_WEBHOOK`: Optional. Set to `true` for webhook deployments such as Render web services.
- `WEBHOOK_BASE_URL`: Optional for local use. In webhook deployments, set this if your host does not provide `RENDER_EXTERNAL_URL`.
- `ADMIN_CHAT_ID`: Required. Chat ID that receives manual-use notifications from the bot.

## Running The Bot Locally

```bash
python main.py
```

On startup the bot will:

- validate required environment variables
- configure structured logging
- start Telegram polling locally, or webhook mode if configured
- start the daily scheduler

## Deploying Online

This repository includes both a `Dockerfile` and `render.yaml`, so it can be deployed to platforms like Render.

### Render Free Web Service Notes

You can deploy the bot as a free web service using Telegram webhooks, but there is one important limitation:

- free Render web services can sleep after inactivity
- webhook requests can wake them up
- in-process scheduled jobs may be delayed or skipped if the service is asleep

Because of that:

- the manual menu reply works reasonably well in webhook mode
- scheduled daily sends are best on always-on hosting or paid plans

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
   - `ADMIN_CHAT_ID`
4. Deploy the service.

## How The Scheduler Works

The project uses `APScheduler` with `AsyncIOScheduler`.

- The scheduled send runs once per day using the configured hour and minute.
- The scheduler uses the configured timezone.
- It coalesces missed runs and limits concurrent executions to one instance.
- The scheduled message uses the same menu formatter as the manual button-triggered reply.
- Scheduled sends do not generate admin usage notifications.

## Troubleshooting

### Missing environment variables

If startup fails with a configuration error, check:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `ADMIN_CHAT_ID`

### Telegram messages are not arriving

- Verify the bot token is correct.
- Make sure the target chat has started a conversation with the bot.
- Double-check `TELEGRAM_CHAT_ID`.

### Admin notifications are not arriving

- Make sure `ADMIN_CHAT_ID` is correct.
- Make sure the bot is allowed to message that chat.
- Check the app logs for notification send errors.

### No halal items are returned

- The bot only checks today's menus.
- It only matches items containing the word `halal` in the item name or description.
- If CSU does not publish halal text on the menu for that day, the bot will return no results.

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
