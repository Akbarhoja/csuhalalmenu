# CSU Halal Menu Telegram Bot

This project is a Python Telegram bot that checks the Colorado State University Nutrislice menus at `https://csumenus.nutrislice.com/`, searches all discoverable dining locations for today's breakfast, lunch, and dinner menus, filters items containing `halal` case-insensitively, and sends the results through Telegram on demand.

The bot also:

- shows the most likely Kosher Bistro lunch and dinner main foods using entree heuristics
- falls back to listing all Kosher Bistro items for a meal if no clear main dish is detected
- sends an admin notification whenever a user manually requests today's halal menu
- uses a short in-memory cache to speed up repeated requests during the same runtime

## Project Structure

```text
csuhalalmenu/
|-- .env.example
|-- .dockerignore
|-- .gitignore
|-- Dockerfile
|-- README.md
|-- bot.py
|-- config.py
|-- constants.py
|-- formatter.py
|-- kosher_bistro_service.py
|-- logging_config.py
|-- main.py
|-- menu_service.py
|-- models.py
|-- notifications.py
|-- nutrislice_client.py
|-- requirements.txt
|-- render.yaml
|-- utils.py
`-- tests
    |-- test_bot.py
    |-- test_formatter.py
    |-- test_kosher_bistro_service.py
    |-- test_menu_service.py
    `-- test_notifications.py
```

## What The Bot Does

When a user presses `Todays Halal Menu`, the bot:

1. Acknowledges the request quickly.
2. Fetches or reuses a short-lived in-memory cache of today's menu data.
3. Checks all discoverable CSU dining locations for today's breakfast, lunch, and dinner menus.
4. Filters items whose name or description contains `halal`, case-insensitively.
5. Identifies likely Kosher Bistro lunch and dinner mains from The Foundry using item-name heuristics.
6. Sends the final formatted menu to the user.
7. Sends a separate admin notification to `ADMIN_CHAT_ID`.

The bot responds only on demand. There is no automatic scheduled daily send anymore.

## Kosher Bistro Output

The bot appends this section to the bottom of every manual menu response:

```text
Kosher Bistro Main Foods:
Lunch:
- {best lunch item}

Dinner:
- {best dinner item}
```

If no clear main item is found for a meal, the bot falls back to:

```text
Lunch:
- Main item unclear, showing all items:
  - {item 1}
  - {item 2}
```

If no items exist for a meal, the bot shows:

```text
Dinner:
- No Kosher Bistro items found for dinner
```

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

## Performance Notes

To improve responsiveness:

- location discovery is cached in memory during runtime
- today's menu snapshot is cached for a short time window
- per-location meal fetches are run concurrently
- HTTP timeouts are shorter and retries are limited to transient transport issues

This keeps repeated button presses from hammering Nutrislice unnecessarily while still refreshing data often enough for normal use.

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
TIMEZONE=America/Denver
USE_WEBHOOK=false
WEBHOOK_BASE_URL=
ADMIN_CHAT_ID=your_admin_chat_id
```

### Environment Variables

- `TELEGRAM_BOT_TOKEN`: Required. Telegram Bot API token from BotFather.
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

## Deploying Online

This repository includes both a `Dockerfile` and `render.yaml`, so it can be deployed to platforms like Render.

### Render Free Web Service Notes

You can deploy the bot as a free web service using Telegram webhooks. Because free Render services can sleep after inactivity, the bot is designed for on-demand use instead of automatic scheduled sends.

### Deploy Steps

1. Push the project to GitHub.
2. Create a Render Blueprint or web service from the repo.
3. Set these environment variables in Render:
   - `TELEGRAM_BOT_TOKEN`
   - `TIMEZONE`
   - `USE_WEBHOOK=true`
   - `ADMIN_CHAT_ID`
4. Deploy the service.

## Troubleshooting

### Missing environment variables

If startup fails with a configuration error, check:

- `TELEGRAM_BOT_TOKEN`
- `ADMIN_CHAT_ID`

### Telegram messages are not arriving

- Verify the bot token is correct.
- Make sure the user has started a conversation with the bot.
- Check the Render logs for webhook or API errors.

### Admin notifications are not arriving

- Make sure `ADMIN_CHAT_ID` is correct.
- Make sure the bot is allowed to message that chat.
- Check the app logs for notification send errors.

### The first press feels slow

On Render free hosting, the service may need to wake up after inactivity. Once awake, the shorter Nutrislice timeouts, limited retries, and short-lived cache reduce repeated delays.

## Tests

Run the included tests with:

```bash
pytest
```

The tests cover:

- menu caching behavior
- graceful error handling on the first request
- heuristic Kosher Bistro main-item selection
- fallback formatting
- admin notifications
