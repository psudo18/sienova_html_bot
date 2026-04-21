# 🏆 Sienova Converter Bot

> A Telegram bot that extracts quiz data from HTML files and generates **GangLeader** or **Sienova** branded quiz HTMLs — for free hosting on Railway or Render.

---

## ✨ Features

| Feature | Description |
|---|---|
| `/extract` | Upload HTML → extract quizData → choose output format |
| `/fromjson` | Upload or paste JSON → generate HTML(s) |
| `/both` | Upload HTML → instantly get both brands + JSON |
| 🔐 Auth | Only whitelisted Telegram user IDs can use the bot |
| 🎨 GangLeader | Warm ivory + saffron-gold theme, 5-state palette |
| 📘 Sienova | Clean blue + white theme, Pipes & Cistern style |
| 📄 JSON export | Always get the raw extracted JSON too |
| ⏱ Timer | 60-minute countdown on all generated quizzes |
| 📊 Score screen | Auto-graded with correct/wrong/unattempted |
| 💡 Solutions | Shown after submit |

---

## 📁 Project Structure

```
sienova-bot/
├── bot.py                  ← Entry point
├── config.py               ← Settings & branding tokens
├── requirements.txt
├── .env.example            ← Copy to .env and fill in
├── Procfile                ← For Railway (non-Docker)
├── railway.toml            ← Railway config
├── nixpacks.toml           ← Railway Playwright deps
├── Dockerfile              ← For Render / Docker
├── render.yaml             ← Render config
│
├── handlers/
│   ├── __init__.py
│   ├── auth.py             ← @require_auth decorator
│   ├── commands.py         ← /start /help /status
│   ├── conversation.py     ← All state machine logic
│   ├── extract.py          ← /extract entry
│   └── generate.py         ← /fromjson /both entries
│
└── utils/
    ├── __init__.py
    ├── extractor.py        ← Playwright HTML → JSON
    └── builder.py          ← JSON → GangLeader/Sienova HTML
```

---

## 🚀 Quick Start (Local)

### 1. Clone & install

```bash
git clone <your-repo>
cd sienova-bot

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and set BOT_TOKEN and ALLOWED_USERS
```

Get your Telegram bot token from [@BotFather](https://t.me/BotFather).
Get your Telegram user ID from [@userinfobot](https://t.me/userinfobot).

### 3. Run

```bash
python bot.py
```

---

## 🌐 Free Hosting

### Option A — Railway (Recommended)

Railway gives you **500 free hours/month** (enough for a bot).

1. Push the project to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select your repo
4. Go to **Variables** and add:
   - `BOT_TOKEN` → your bot token
   - `ALLOWED_USERS` → comma-separated user IDs
5. Railway auto-detects `nixpacks.toml` and `railway.toml`
6. Done — your bot is live!

> ⚠️ Playwright needs Chromium. The `nixpacks.toml` handles this automatically on Railway.

### Option B — Render (Docker)

1. Push to GitHub
2. [render.com](https://render.com) → New → Background Worker
3. Connect your repo → select **Docker** runtime
4. Add environment variables (`BOT_TOKEN`, `ALLOWED_USERS`)
5. Deploy

Render free tier has a 750 hour/month limit — enough for a background worker.

---

## 🤖 Bot Commands

```
/start      Welcome message
/help       Show all commands
/status     Bot health check

/extract    Upload HTML → extract + choose output format
/fromjson   Upload/paste JSON → generate HTML(s)
/both       Upload HTML → get ALL outputs at once (GL + Sienova + JSON)
/cancel     Cancel current operation
```

### Output Modes (shown as keyboard buttons after extraction)

| Button | Output |
|---|---|
| `gangleader` | GangLeader branded HTML (ivory + gold) |
| `sienova` | Sienova branded HTML (blue + white) |
| `both` | Both HTMLs + extracted JSON |
| `json` | Just the extracted JSON |

---

## 🔐 Authorization

Only Telegram users whose IDs are in `ALLOWED_USERS` can use the bot.

To find your Telegram user ID:
1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. Copy the ID number
3. Add it to `ALLOWED_USERS` in your `.env`:
   ```
   ALLOWED_USERS=123456789,987654321
   ```

If `ALLOWED_USERS` is empty, **everyone** can use the bot.

---

## 🎨 Branding Customization

Edit `config.py` to change colors/names:

```python
GANGLEADER_BRAND = {
    "name": "GangLeader",
    "tagline": "Crack the Code. Lead the Gang.",
    "primary": "#D4A843",       # saffron-gold
    "bg":      "#FEFCF7",       # warm ivory
    ...
}

SIENOVA_BRAND = {
    "name": "Sienova",
    "primary": "#2563EB",       # blue
    ...
}
```

---

## 📋 JSON Format

The bot accepts and produces JSON in this format:

```json
{
  "test_name": "Pipes and Cistern",
  "total_questions": 30,
  "extracted_at": "2024-01-01T12:00:00",
  "questions": [
    {
      "id": 1,
      "question_number": 1,
      "question_text": "Pipe A fills a tank in 6 hours...",
      "marks": 1,
      "correct_answer": "B",
      "options": [
        { "label": "A", "text": "3 hours" },
        { "label": "B", "text": "4 hours" },
        { "label": "C", "text": "5 hours" },
        { "label": "D", "text": "6 hours" }
      ],
      "solution": "Let pipe A do 1/6 work per hour..."
    }
  ]
}
```

You can also pass a **raw list** (the `questions` array only) to `/fromjson` — the bot will wrap it automatically.

---

## 🛠 Troubleshooting

| Problem | Fix |
|---|---|
| `playwright install` fails on Railway | The `nixpacks.toml` handles this — don't modify it |
| Bot doesn't respond | Check `BOT_TOKEN` in environment variables |
| "Access Denied" message | Your user ID isn't in `ALLOWED_USERS` |
| Extraction fails | The HTML must have a `quizData` JS variable |
| Docker build slow | Normal — Playwright Chromium is ~200MB |

---

## 📝 License

Private project — GangLeader / Sienova. All rights reserved.
