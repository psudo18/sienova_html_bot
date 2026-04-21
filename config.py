"""
Configuration - Sienova Converter Bot
All settings loaded from environment variables
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ── Auth ──────────────────────────────────────────────────────────────────────
# Comma-separated Telegram user IDs allowed to use the bot
# e.g.  ALLOWED_USERS=123456789,987654321
_raw = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: set[int] = (
    {int(uid.strip()) for uid in _raw.split(",") if uid.strip()}
    if _raw else set()
)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Paths ─────────────────────────────────────────────────────────────────────
TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/sienova_bot")

# ── Platform branding ─────────────────────────────────────────────────────────
# You can override these via env vars for white-label deployments
GANGLEADER_BRAND = {
    "name": "GangLeader",
    "tagline": "Crack the Code. Lead the Gang.",
    "primary": "#D4A843",       # saffron-gold
    "primary_dark": "#B8912A",
    "bg": "#FEFCF7",            # warm ivory
    "surface": "#FFFEF9",
    "text": "#1A1A1A",
    "accent": "#C8A030",
    "logo_emoji": "🏆",
}

SIENOVA_BRAND = {
    "name": "Sienova",
    "tagline": "Smart Exam Solutions",
    "primary": "#2563EB",       # blue
    "primary_dark": "#1D4ED8",
    "bg": "#F8FAFF",
    "surface": "#FFFFFF",
    "text": "#0F172A",
    "accent": "#3B82F6",
    "logo_emoji": "📘",
}
