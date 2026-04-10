import telebot
import pandas as pd
from binance.client import Client
import ta
import time

API_KEY = "gzC0CS0BdGYeFRLKB7MWFhMcv9ginV9BBeS6MBL5gxRzU3Az0aoXg9HxHF8vNluO"
API_SECRET = "oknEbdAoHazoi2kf1BJfcPjUohfCtUPenTuaNGLTULmjVsJLdsn7b7WQNrfTAL1b"
TG_TOKEN = "ТВОЙ_TELEGRAM_TOKEN"
CHAT_ID = "ТВОЙ_CHAT_ID"

bot = telebot.TeleBot(TG_TOKEN)
client = Client(API_KEY, API_SECRET)

symbols = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT",
    "XRPUSDT", "DOTUSDT", "AVAXUSDT", "LINKUSDT", "MATICUSDT",
    "NEARUSDT", "LTCUSDT", "ATOMUSDT", "APTUSDT", "ARBUSDT",
    "FILUSDT", "OPUSDT", "INJUSDT", "TIAUSDT", "SUIUSDT"
]

active_signals = []

def get_data(symbol):
    try:
        klines = client.get_klines(symbol=symbol, interval="1h", limit=300)
        df = pd.DataFrame(klines)
        df = df.iloc[:, :6]
        df.columns = ["time", "open", "high", "low", "close", "volume"]
        df[["open", "high", "low", "close", "volume"]] = df[
            ["open", "high", "low", "close", "volume"]
        ].astype(float)
        return df
    except:
        return None

def get_levels(df):
    resistance = df["high"].rolling(window=20).max().iloc[-2]
    support = df["low"].rolling(window=20).min().iloc[-2]
    return support, resistance

def confirmation_candle(df):
    last = df.iloc[-1]
    body = abs(last["close"] - last["open"])
    lower_wick = min(last["open"], last["close"]) - last["low"]
    upper_wick = last["high"] - max(last["open"], last["close"])

    bullish = lower_wick > body * 1.5 and last["close"] > last["open"]
    bearish = upper_wick > body * 1.5 and last["close"] < last["open"]

    return bullish, bearish

def analyze(symbol):
    df = get_data(symbol)
    if df is None or len(df) < 210:
        return None, None, None

    df["ema50"] = ta.trend.ema_indicator(df["close"], window=50)
    df["ema200"] = ta.trend.ema_indicator(df["close"], window=200)
    df["rsi"] = ta.momentum.rsi(df["close"], window=14)
    df["adx"] = ta.trend.adx(df["high"], df["low"], df["close"], window=14)
    df["atr"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"], window=14)

    df = df.dropna()
    if df.empty:
        return None, None, None

    support, resistance = get_levels(df)
    bullish, bearish = confirmation_candle(df)

    last = df.iloc[-1]
    price = last["close"]
    atr = last["atr"]
    rsi = last["rsi"]
    adx = last["adx"]

    if adx < 20:
        return None, None, None

    if price > last["ema50"] and price > last["ema200"]:
        if rsi < 65 and abs(price - support) / price < 0.005 and bullish:
            return "LONG", price, atr

    if price < last["ema50"] and price < last["ema200"]:
        if rsi > 35 and abs(price - resistance) / price < 0.005 and bearish:
            return "SHORT", price, atr

    return None, None, None

def send_signal(symbol, direction, price, atr):
    stop_distance = atr * 2

    sl = price - stop_distance if direction == "LONG" else price + stop_distance
    tp = price + stop_distance * 2 if direction == "LONG" else price - stop_distance * 2

    entry_min = price * 0.998
    entry_max = price * 1.002

    signal = {
        "symbol": symbol,
        "direction": direction,
        "entry_min": entry_min,
        "entry_max": entry_max,
        "sl": sl,
        "tp": tp,
        "time": time.time()
    }

    active_signals.append(signal)

    text = f"""🚨 {symbol} | {direction}
Вход: {entry_min:.4f} - {entry_max:.4f}
SL: {sl:.4f}
TP: {tp:.4f}
Статус: ЖДЁМ"""

    bot.send_message(CHAT_ID, text)

def check_signals():
    for signal in active_signals[:]:
        try:
            price = float(client.get_symbol_ticker(symbol=signal["symbol"])["price"])

            if time.time() - signal["time"] > 3600:
                bot.send_message(CHAT_ID, f"❌ {signal['symbol']} отмена")
                active_signals.remove(signal)
                continue

            if signal["entry_min"] <= price <= signal["entry_max"]:
                bot.send_message(CHAT_ID, f"🟢 {signal['symbol']} ВХОД СЕЙЧАС\nЦена: {price}")
                active_signals.remove(signal)

        except:
            continue

def run():
    while True:
        for symbol in symbols:
            direction, price, atr = analyze(symbol)
            if direction:
                if not any(s["symbol"] == symbol for s in active_signals):
                    send_signal(symbol, direction, price, atr)

            time.sleep(0.5)

        check_signals()
        time.sleep(300)

if __name__ == "__main__":
    run()
