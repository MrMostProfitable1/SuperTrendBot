"""
config.py — Environment variables se padhta hai (Railway ke liye)
Local testing ke liye directly values bhi likh sakte ho
"""

import os

CONFIG = {

    # ── BYBIT API ─────────────────────────────────────────
    # Railway pe Environment Variables mein set karo (neeche tutorial mein)
    # Local test ke liye yahan seedha likh sakte ho
    "API_KEY":    os.environ.get("BYBIT_API_KEY",    "YOUR_API_KEY_HERE"),
    "API_SECRET": os.environ.get("BYBIT_API_SECRET", "YOUR_API_SECRET_HERE"),
    "TESTNET":    os.environ.get("TESTNET", "true").lower() == "true",

    # ── SYMBOLS ───────────────────────────────────────────
    "SYMBOLS": ["BTCUSDT", "ETHUSDT"],

    # ── SUPERTREND ────────────────────────────────────────
    "ST_PERIOD":     10,
    "ST_MULTIPLIER": 3.0,

    # ── FILTERS ───────────────────────────────────────────
    "ADX_PERIOD":      14,
    "ADX_MIN":         25,
    "EMA_PERIOD":      200,
    "VOLUME_MULT":     1.4,
    "RSI_PERIOD":      14,
    "RSI_OVERBOUGHT":  72,
    "RSI_OVERSOLD":    28,

    # ── RISK ──────────────────────────────────────────────
    "LEVERAGE":           5,
    "RISK_PERCENT":       2.0,
    "ATR_SL_MULT":        1.8,
    "TP1_MULT":           2.0,
    "TRAIL_ATR_MULT":     1.2,
    "MAX_DAILY_LOSS_PCT": 6.0,
    "MAX_OPEN_TRADES":    2,

    # ── TELEGRAM ──────────────────────────────────────────
    "TELEGRAM_ENABLED": os.environ.get("TELEGRAM_ENABLED", "false").lower() == "true",
    "TELEGRAM_TOKEN":   os.environ.get("TELEGRAM_TOKEN",   ""),
    "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", ""),

    # ── TIMING ────────────────────────────────────────────
    "INTERVAL":     "60",
    "CANDLE_LIMIT": 250,
    "CHECK_EVERY":  300,
}
