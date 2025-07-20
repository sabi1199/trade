import streamlit as st
from datetime import datetime
import requests
import pytz
import pandas as pd
from streamlit_autorefresh import st_autorefresh

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
    st.title("🔐 Forex Signal App Login..!")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in VALID_USERS and VALID_USERS[username] == password:
            st.session_state.logged_in = True
            st.success("Login successful. Reloading...")
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

def run_signal_engine(candles):
    results = []
    total = wins = losses = 0

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

    win_rate = (wins / total) * 100 if total else 0
    return results, total, wins, losses, win_rate

# Streamlit UI
st.set_page_config(page_title="Forex Signal Engine", layout="wide")

# --- Login Check ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login()
    st.stop()

# --- Logout Button ---
with st.sidebar:
    if st.button("🔓 Logout"):
        st.session_state.logged_in = False
        st.success("Logged out successfully.")
        st.rerun()

st.title("📈 Forex Signal Engine")

symbols = st.multiselect("Currency Pairs", AVAILABLE_PAIRS, default=["EUR/USD"])
mode = st.selectbox("Mode", ["Backtest", "Live"])
date_input = st.date_input("Select Date", datetime.now())

# --- Start/Stop Toggle ---
if "app_running" not in st.session_state:
    st.session_state.app_running = False

col1, col2 = st.columns([1, 2])
with col1:
    if st.button("▶ Start App"):
        st.session_state.app_running = True
    if st.button("⏹ Stop App"):
        st.session_state.app_running = False

# --- Auto-refresh Logic ---
if st.session_state.app_running:
    st_autorefresh(interval=REFRESH_INTERVAL_SEC * 1000, limit=None, key="autorefresh")

    for symbol in symbols:
        candles, is_healthy = fetch_data(symbol, date_input.strftime("%Y-%m-%d"))
        status_text = "🟢 API Running" if is_healthy else "🔴 Problem Occurred"
        status_color = "green" if is_healthy else "red"

        with st.expander(f"🔍 {symbol} - {status_text}"):
            if is_healthy and candles:
                with st.spinner("Running signal engine..."):
                    results, total, wins, losses, win_rate = run_signal_engine(candles)

                    if results:
                        df = pd.DataFrame(results)
                        st.dataframe(df, use_container_width=True)
                        st.success(f"Total Signals: {total}, Wins: {wins}, Losses: {losses}, Win Rate: {win_rate:.2f}%")
                    else:
                        st.info("No strong signals at the moment.")
            else:
                st.error("Could not fetch data from API.")
else:
    st.warning("App is stopped. Click ▶ Start App to begin.")
        
