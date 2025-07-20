import streamlit as st
from datetime import datetime
import requests
import pytz
import pandas as pd
import threading
from streamlit_autorefresh import st_autorefresh
from iqoptionapi.stable_api import IQ_Option

API_KEY = 'a9efceaa17e34769bd79c9a40ae9bd67'
TIMEZONE = 'Asia/Kolkata'
REFRESH_INTERVAL_SEC = 5

AVAILABLE_PAIRS = [
    "EUR/USD", "GBP/USD", "USD/JPY",
    "AUD/USD", "USD/CAD", "EUR/GBP"
]

VALID_USERS = {
    "admin": "admin123",
    "user1": "pass123"
}

def login():
    st.title("🔐 Forex Signal App Login💲")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in VALID_USERS and VALID_USERS[username] == password:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Invalid username or password.")

@st.cache_data(show_spinner=False)
def fetch_data(symbol, date_str):
    start = f"{date_str} 00:00:00"
    end = f"{date_str} 23:59:00"
    interval = '1min'
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&start_date={start}&end_date={end}&timezone={TIMEZONE}&apikey={API_KEY}&format=JSON"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        json_data = res.json()
        if "values" not in json_data:
            return None, False
        return list(reversed(json_data["values"])), True
    except Exception:
        return None, False

def calculate_confidence(candles, index):
    current = candles[index]
    prev = candles[index - 1]

    open_price = float(current['open'])
    close_price = float(current['close'])
    high = float(current['high'])
    low = float(current['low'])

    body = abs(close_price - open_price)
    wick = (high - low) - body
    trend_confirm = 1 if (float(prev['close']) > float(prev['open']) and close_price > open_price) or (float(prev['close']) < float(prev['open']) and close_price < open_price) else 0

    confidence = min(100, int((body / (body + wick + 0.00001)) * 100) + trend_confirm * 10)
    return confidence

def place_trade(api, symbol, action, amount):
    direction = "call" if action == "BUY" else "put"
    duration = 1  # minute trade
    api.buy(amount, symbol.replace("/", ""), direction, duration)
    st.session_state.trade_log.append({
        "symbol": symbol,
        "action": action,
        "amount": amount,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def run_signal_engine_gui(symbol, candles):
    total = wins = losses = 0
    results = []

    for i in range(15, len(candles)-2):
        signal_time = candles[i]['datetime']
        o = float(candles[i]['open'])
        c = float(candles[i]['close'])

        if c > o and float(candles[i-1]['close']) > float(candles[i-1]['open']):
            action = "BUY"
        elif c < o and float(candles[i-1]['close']) < float(candles[i-1]['open']):
            action = "SELL"
        else:
            continue

        confidence = calculate_confidence(candles, i)
        if confidence < 60:
            continue

        entry_candle = candles[i+1]
        exit_candle = candles[i+2]
        entry_price = float(entry_candle['open'])
        exit_price = float(exit_candle['close'])

        result = "WIN" if (
            (action == "BUY" and exit_price > entry_price) or
            (action == "SELL" and exit_price < entry_price)
        ) else "LOSS"

        total += 1
        if result == "WIN":
            wins += 1
        else:
            losses += 1

        current_win_rate = (wins / total) * 100 if total else 0
        if current_win_rate < 75:
            continue

        results.append({
            "Time": datetime.strptime(signal_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S'),
            "Action": action,
            "Entry": entry_candle['datetime'],
            "Exit": exit_candle['datetime'],
            "Entry Price": f"{entry_price:.5f}",
            "Exit Price": f"{exit_price:.5f}",
            "Confidence": f"{confidence}%",
            "Result": result
        })

    df = pd.DataFrame(results)
    st.dataframe(df, use_container_width=True)
    win_rate = (wins / total) * 100 if total else 0
    st.success(f"Total Signals: {total}, Wins: {wins}, Losses: {losses}, Win Rate: {win_rate:.2f}%")

def auto_trade_if_live(api, symbols, trade_amount, tp, sl):
    if datetime.now().strftime("%H:%M:%S")[-1] in ["0", "5"]:
        for symbol in symbols:
            candles, is_healthy = fetch_data(symbol, datetime.now().strftime("%Y-%m-%d"))
            if not is_healthy or not candles:
                continue
            for i in range(15, len(candles)-2):
                o = float(candles[i]['open'])
                c = float(candles[i]['close'])

                if c > o and float(candles[i-1]['close']) > float(candles[i-1]['open']):
                    action = "BUY"
                elif c < o and float(candles[i-1]['close']) < float(candles[i-1]['open']):
                    action = "SELL"
                else:
                    continue

                confidence = calculate_confidence(candles, i)
                if confidence < 60:
                    continue

                if st.session_state.daily_profit >= tp or st.session_state.daily_loss >= sl:
                    return

                threading.Thread(target=place_trade, args=(api, symbol, action, trade_amount), daemon=True).start()
                break

# --- Streamlit UI ---
st.set_page_config(page_title="Forex Signal Engine", layout="wide")

# --- Session State Init ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "trade_log" not in st.session_state:
    st.session_state.trade_log = []
if "daily_profit" not in st.session_state:
    st.session_state.daily_profit = 0.0
if "daily_loss" not in st.session_state:
    st.session_state.daily_loss = 0.0
if "app_running" not in st.session_state:
    st.session_state.app_running = False
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "Signals"

if not st.session_state.logged_in:
    login()
    st.stop()

# --- Sidebar Controls ---
with st.sidebar:
    if st.button("🔓 Logout"):
        st.session_state.logged_in = False
        st.rerun()

    account_mode = st.radio("Account Type", ["Demo", "Real"])
    trade_amount = st.number_input("Per Trade Amount ($)", min_value=1.0, value=1.0, step=1.0)
    tp = st.number_input("Take Profit ($)", min_value=1.0, value=10.0, step=1.0)
    sl = st.number_input("Stop Loss ($)", min_value=1.0, value=10.0, step=1.0)
    st.session_state.view_mode = st.radio("View", ["Signals", "Trade Results"])

# --- Main GUI ---
symbols = st.multiselect("Currency Pairs", AVAILABLE_PAIRS, default=["EUR/USD"])
date_input = st.date_input("Select Date", datetime.now())
mode = st.selectbox("Mode", ["Backtest", "Live"])
col1, col2 = st.columns([1, 2])
with col1:
    if st.button("▶ Start App"):
        st.session_state.app_running = True
    if st.button("⏹ Stop App"):
        st.session_state.app_running = False

# --- IQ Option Connect ---
email = "shabeesan119@gmail.com"
password = "Maxmo1423@"
I_want_money = IQ_Option(email, password)
I_want_money.connect()
I_want_money.change_balance("PRACTICE" if account_mode == "Demo" else "REAL")

# --- App Logic ---
if st.session_state.app_running:
    st_autorefresh(interval=REFRESH_INTERVAL_SEC * 1000, limit=None, key="autorefresh")

    if mode == "Backtest":
        for symbol in symbols:
            candles, is_healthy = fetch_data(symbol, date_input.strftime("%Y-%m-%d"))
            if is_healthy and candles:
                with st.expander(f"📡 {symbol} Backtest Signals"):
                    run_signal_engine_gui(symbol, candles)
    elif mode == "Live":
        auto_trade_if_live(I_want_money, symbols, trade_amount, tp, sl)

    if st.session_state.view_mode == "Trade Results":
        st.subheader("📊 Trade Log")
        if st.session_state.trade_log:
            df_log = pd.DataFrame(st.session_state.trade_log)
            st.dataframe(df_log, use_container_width=True)
        else:
            st.info("No trades placed yet.")
else:
    st.warning("App is stopped. Click ▶ Start App to begin.")
    
