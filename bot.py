import time
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from pybit.unified_trading import HTTP
from config import CONFIG

# ==== INIT ====
session = HTTP(
    testnet=CONFIG["TESTNET"],
    api_key=CONFIG["hEsic2EIJm3fieCuzY"],
    api_secret=CONFIG["NOGtsTzZXIBOXaz23f4dqSbrKoy216WpeExX"]
)

daily_loss = 0.0
last_reset = datetime.now().date()

# ==== TELEGRAM ====
def send_msg(msg):
    if not CONFIG["TELEGRAM_ENABLED"]:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{CONFIG['TELEGRAM_TOKEN']}/sendMessage",
            data={"chat_id": CONFIG["TELEGRAM_CHAT_ID"], "text": msg, "parse_mode": "HTML"}
        )
    except:
        pass

# ==== GET KLINES ====
def get_df(symbol, interval, limit=250):
    try:
        url = (
            f"https://api.bybit.com/v5/market/kline"
            f"?category=linear&symbol={symbol}"
            f"&interval={interval}&limit={limit}"
        )
        resp = requests.get(url).json()
        data = resp['result']['list']
        data.reverse()
        df = pd.DataFrame(data, columns=[
            'time','open','high','low','close','volume','turnover'
        ])
        for col in ['open','high','low','close','volume']:
            df[col] = df[col].astype(float)
        return df
    except Exception as e:
        print(f"Kline error {symbol}: {e}")
        return None

# ==== SUPERTREND ====
def calc_supertrend(df, period=10, multiplier=3.0):
    high = df['high']
    low  = df['low']
    close = df['close']

    # ATR
    tr = pd.concat([
        high - low,
        abs(high - close.shift()),
        abs(low  - close.shift())
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()

    # Basic bands
    hl2 = (high + low) / 2
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr

    # Supertrend
    supertrend = pd.Series(index=df.index, dtype=float)
    direction  = pd.Series(index=df.index, dtype=int)

    for i in range(period, len(df)):
        if close.iloc[i] > upper.iloc[i-1]:
            direction.iloc[i] = 1   # Green — Long
        elif close.iloc[i] < lower.iloc[i-1]:
            direction.iloc[i] = -1  # Red — Short
        else:
            direction.iloc[i] = direction.iloc[i-1]

        if direction.iloc[i] == 1:
            supertrend.iloc[i] = lower.iloc[i]
        else:
            supertrend.iloc[i] = upper.iloc[i]

    df['supertrend'] = supertrend
    df['st_dir']     = direction
    return df

# ==== ADX ====
def calc_adx(df, period=14):
    high  = df['high']
    low   = df['low']
    close = df['close']

    plus_dm  = high.diff()
    minus_dm = low.diff().abs()
    plus_dm  = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

    tr = pd.concat([
        high - low,
        abs(high - close.shift()),
        abs(low  - close.shift())
    ], axis=1).max(axis=1)

    atr      = tr.rolling(period).mean()
    plus_di  = 100 * (plus_dm.rolling(period).mean()  / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    dx       = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx      = dx.rolling(period).mean()

    df['adx'] = adx
    return df

# ==== RSI ====
def calc_rsi(df, period=14):
    delta = df['close'].diff()
    gain  = delta.where(delta > 0, 0).rolling(period).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs    = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

# ==== EMA ====
def calc_ema(df, period=200):
    df['ema'] = df['close'].ewm(span=period, adjust=False).mean()
    return df

# ==== ATR VALUE ====
def get_atr(df, period=14):
    tr = pd.concat([
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift()),
        abs(df['low']  - df['close'].shift())
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean().iloc[-1]

# ==== POSITION SIZE ====
def calc_qty(symbol, entry, sl):
    try:
        balance_url = "https://api.bybit.com/v5/account/wallet-balance?accountType=UNIFIED"
        bal = session.get_wallet_balance(accountType="UNIFIED")
        usdt_bal = float(bal['result']['list'][0]['totalWalletBalance'])

        risk_amt  = usdt_bal * (CONFIG["RISK_PERCENT"] / 100)
        sl_dist   = abs(entry - sl)
        qty       = round(risk_amt / sl_dist, 3)
        return qty
    except Exception as e:
        print(f"Qty error: {e}")
        return 0.01

# ==== GET OPEN POSITION ====
def get_position(symbol):
    try:
        pos = session.get_positions(category="linear", symbol=symbol)
        for p in pos['result']['list']:
            if float(p['size']) > 0:
                return p
        return None
    except:
        return None

# ==== PLACE ORDER ====
def place_order(symbol, side, qty, sl, tp1):
    try:
        # Set leverage
        session.set_leverage(
            category="linear",
            symbol=symbol,
            buyLeverage=str(CONFIG["LEVERAGE"]),
            sellLeverage=str(CONFIG["LEVERAGE"])
        )

        # Market entry
        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=str(qty),
            stopLoss=str(round(sl, 4)),
            takeProfit=str(round(tp1, 4))
        )
        print(f"✅ Order placed: {side} {symbol} qty={qty}")
        return order
    except Exception as e:
        print(f"❌ Order error: {e}")
        return None

# ==== CLOSE POSITION ====
def close_position(symbol, pos):
    try:
        side = "Sell" if pos['side'] == "Buy" else "Buy"
        session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=pos['size'],
            reduceOnly=True
        )
        print(f"🔴 Position closed: {symbol}")
    except Exception as e:
        print(f"Close error: {e}")

# ==== DAILY LOSS RESET ====
def check_daily_reset():
    global daily_loss, last_reset
    today = datetime.now().date()
    if today != last_reset:
        daily_loss = 0.0
        last_reset = today
        print("📅 Daily loss reset!")

# ==== MAIN LOGIC ====
def process_symbol(symbol):
    global daily_loss

    # Daily loss check
    check_daily_reset()

    try:
        # Get balance for daily loss check
        bal = session.get_wallet_balance(accountType="UNIFIED")
        total_bal = float(bal['result']['list'][0]['totalWalletBalance'])
        max_loss  = total_bal * (CONFIG["MAX_DAILY_LOSS_PCT"] / 100)

        if daily_loss >= max_loss:
            print(f"⛔ Daily loss limit reached! No more trades today.")
            return

        # Check open trades count
        open_pos = get_position(symbol)

        # ==== 4H Trend Confirmation ====
        df_4h = get_df(symbol, "240", limit=100)
        if df_4h is None: return
        df_4h = calc_supertrend(df_4h, CONFIG["ST_PERIOD"], CONFIG["ST_MULTIPLIER"])
        trend_4h = df_4h['st_dir'].iloc[-1]  # 1=Bull, -1=Bear

        # ==== 1H Main Signal ====
        df_1h = get_df(symbol, CONFIG["INTERVAL"], limit=CONFIG["CANDLE_LIMIT"])
        if df_1h is None: return

        df_1h = calc_supertrend(df_1h, CONFIG["ST_PERIOD"], CONFIG["ST_MULTIPLIER"])
        df_1h = calc_adx(df_1h, CONFIG["ADX_PERIOD"])
        df_1h = calc_rsi(df_1h, CONFIG["RSI_PERIOD"])
        df_1h = calc_ema(df_1h, CONFIG["EMA_PERIOD"])

        last      = df_1h.iloc[-1]
        prev      = df_1h.iloc[-2]
        st_now    = last['st_dir']
        st_prev   = prev['st_dir']
        adx       = last['adx']
        rsi       = last['rsi']
        ema       = last['ema']
        close     = last['close']
        volume    = last['volume']
        vol_avg   = df_1h['volume'].rolling(20).mean().iloc[-1]

        # ==== SIGNAL FLIP DETECT ====
        long_signal  = (st_now == 1  and st_prev == -1)  # ST flipped Green
        short_signal = (st_now == -1 and st_prev == 1)   # ST flipped Red

        # ==== FILTERS ====
        adx_ok     = adx > CONFIG["ADX_MIN"]
        vol_ok     = volume > vol_avg * CONFIG["VOLUME_MULT"]
        rsi_long   = rsi < CONFIG["RSI_OVERBOUGHT"]
        rsi_short  = rsi > CONFIG["RSI_OVERSOLD"]
        ema_long   = close > ema   # Price above EMA = uptrend
        ema_short  = close < ema   # Price below EMA = downtrend
        trend_long  = trend_4h == 1   # 4H bullish
        trend_short = trend_4h == -1  # 4H bearish

        atr = get_atr(df_1h)

        # ==== EXISTING POSITION — TRAIL STOP ====
        if open_pos:
            pos_side = open_pos['side']
            pos_sl   = float(open_pos['stopLoss'])

            if pos_side == "Buy" and st_now == -1:
                # ST flipped red — close long
                close_position(symbol, open_pos)
                send_msg(f"🔴 <b>{symbol}</b> Long closed — ST flipped Red!")

            elif pos_side == "Sell" and st_now == 1:
                # ST flipped green — close short
                close_position(symbol, open_pos)
                send_msg(f"🟢 <b>{symbol}</b> Short closed — ST flipped Green!")

            else:
                # Trail stop
                new_sl = None
                if pos_side == "Buy":
                    trail = close - atr * CONFIG["TRAIL_ATR_MULT"]
                    if trail > pos_sl:
                        new_sl = round(trail, 4)
                elif pos_side == "Sell":
                    trail = close + atr * CONFIG["TRAIL_ATR_MULT"]
                    if trail < pos_sl:
                        new_sl = round(trail, 4)

                if new_sl:
                    try:
                        session.set_trading_stop(
                            category="linear",
                            symbol=symbol,
                            stopLoss=str(new_sl)
                        )
                        print(f"📈 Trail SL updated: {symbol} → {new_sl}")
                    except:
                        pass
            return

        # ==== NEW LONG ENTRY ====
        if long_signal and adx_ok and vol_ok and rsi_long and ema_long and trend_long:
            sl  = round(close - atr * CONFIG["ATR_SL_MULT"], 4)
            tp1 = round(close + atr * CONFIG["TP1_MULT"] * CONFIG["ATR_SL_MULT"], 4)
            qty = calc_qty(symbol, close, sl)

            if qty > 0:
                order = place_order(symbol, "Buy", qty, sl, tp1)
                if order:
                    sl_pct  = round((close - sl) / close * 100, 2)
                    tp1_pct = round((tp1 - close) / close * 100, 2)
                    send_msg(f"""
🟢 <b>LONG ENTRY</b>

📌 <b>{symbol}</b>
💰 Entry: {close}
🛑 SL: {sl} (-{sl_pct}%)
🎯 TP1: {tp1} (+{tp1_pct}%)
📊 ADX: {adx:.1f} | RSI: {rsi:.1f}
⚡ 4H Trend: Bullish ✅
""")

        # ==== NEW SHORT ENTRY ====
        elif short_signal and adx_ok and vol_ok and rsi_short and ema_short and trend_short:
            sl  = round(close + atr * CONFIG["ATR_SL_MULT"], 4)
            tp1 = round(close - atr * CONFIG["TP1_MULT"] * CONFIG["ATR_SL_MULT"], 4)
            qty = calc_qty(symbol, close, sl)

            if qty > 0:
                order = place_order(symbol, "Sell", qty, sl, tp1)
                if order:
                    sl_pct  = round((sl - close) / close * 100, 2)
                    tp1_pct = round((close - tp1) / close * 100, 2)
                    send_msg(f"""
🔴 <b>SHORT ENTRY</b>

📌 <b>{symbol}</b>
💰 Entry: {close}
🛑 SL: {sl} (+{sl_pct}%)
🎯 TP1: {tp1} (-{tp1_pct}%)
📊 ADX: {adx:.1f} | RSI: {rsi:.1f}
⚡ 4H Trend: Bearish ✅
""")

        else:
            print(f"⏭  No signal: {symbol} | ST:{st_now} | ADX:{adx:.1f} | RSI:{rsi:.1f}")

    except Exception as e:
        print(f"❌ Error {symbol}: {e}")

# ==== MAIN LOOP ====
def main():
    print("🚀 Supertrend Auto-Trade Bot Starting...")
    send_msg("🤖 <b>Supertrend Bot Started!</b>\nBTC + ETH monitoring...")

    while True:
        print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')} — Checking...")
        for symbol in CONFIG["SYMBOLS"]:
            process_symbol(symbol)
            time.sleep(2)
        print(f"✅ Done — {CONFIG['CHECK_EVERY']}s baad dobara...")
        time.sleep(CONFIG["CHECK_EVERY"])

if __name__ == "__main__":
    main()
