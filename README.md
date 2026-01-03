# AsiaPac Sales Bot

A Telegram bot for sales teams to track leads and follow-ups using voice or text.

## Features

- **Voice-first**: Send voice notes to add leads, update status, mark done
- **Simple lead tracking**: Name, company, next steps - that's it
- **Daily digests**: Morning (8:30 AM) and evening (5:30 PM) reminders, Mon-Fri
- **Sunday preview**: Week-ahead summary at 8 PM
- **Out-of-office mode**: Pause reminders when you're away

## Setup

### 1. Create Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow prompts
3. Copy the bot token

### 2. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a project
2. Go to SQL Editor and run the contents of `schema.sql`
3. Copy your project URL and anon key from Settings > API

### 3. Get Groq API Key

1. Go to [console.groq.com](https://console.groq.com)
2. Create an API key

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your keys:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_supabase_anon_key
GROQ_API_KEY=your_groq_api_key
```

### 5. Run Locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python bot.py
```

### 6. Deploy to Railway

1. Push code to GitHub
2. Go to [railway.app](https://railway.app) and create new project from GitHub
3. Add environment variables in Railway dashboard
4. Deploy!

## Usage

### Voice Commands

- "Add lead John at Acme, need to send proposal"
- "Show my leads"
- "Update John - meeting scheduled"
- "Done with John" or "Won John"

### Text Commands

| Command | Description |
|---------|-------------|
| `/start` | Register/welcome |
| `/help` | Show all commands |
| `/add Name \| Company \| Next Steps \| YYYY-MM-DD` | Add a lead |
| `/leads` | List active leads |
| `/today` | Today's follow-ups |
| `/update ID field value` | Update a lead |
| `/done ID [won\|lost]` | Mark lead complete |
| `/ooo YYYY-MM-DD` | Set out-of-office |
| `/ooo off` | Disable OOO |

## Digest Schedule (Singapore Time)

- **Mon-Fri 8:30 AM**: Morning digest - today's follow-ups
- **Mon-Fri 5:30 PM**: Evening check-in - pending items
- **Sunday 8:00 PM**: Week ahead preview
