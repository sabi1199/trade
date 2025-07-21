import streamlit as st
import requests
import datetime
import time

# === App Config ===
st.set_page_config(page_title="DigitalZone Signal Scanner", layout="centered")
st.title("📡 Signal Scanner by DigitalZone")

# === Constants ===
API_KEY = "1c0686209a514fb69f984c5e5e0ea722"
INTERVAL = "5min"
RSI_PERIOD = 3
THRESHOLD_LOW = 5
THRESHOLD_HIGH = 95
PAIRS = [
    "AUD/CAD", "AUD/CHF", "AUD/JPY", "AUD/NZD", "AUD/USD",
    "CAD/CHF", "CAD/JPY", "CHF/JPY", "EUR/AUD", "EUR/CAD",
    "EUR/CHF", "EUR/GBP", "EUR/JPY", "EUR/NZD", "EUR/USD",
    "GBP/AUD", "GBP/CAD", "GBP/CHF", "GBP/JPY", "GBP/NZD",
    "GBP/USD", "NZD/CAD", "NZD/CHF", "NZD/JPY", "NZD/USD",
    "USD/CAD", "USD/CHF", "USD/JPY", "BTC/USD"
]


# === Function to fetch RSI ===
def fetch_rsi(symbol):
    url = f"https://api.twelvedata.com/rsi?symbol={symbol}&interval={INTERVAL}&time_period={RSI_PERIOD}&apikey={API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        if "values" in data:
            return [float(v["rsi"]) for v in data["values"][:2]]
        else:
            return []
    except:
        return []

# === Function to scan symbols ===
def scan_pairs():
    results = []
    for pair in PAIRS:
        rsi = fetch_rsi(pair)
        signal = "NEUTRAL"
        if len(rsi) >= 2:
            prev, curr = rsi[1], rsi[0]
            if prev <= THRESHOLD_LOW < curr:
                signal = "CALL"
            elif prev >= THRESHOLD_HIGH > curr:
                signal = "PUT"
            results.append({
                "Pair": pair,
                "Prev RSI": round(prev, 2),
                "Curr RSI": round(curr, 2),
                "Signal": signal,
                "Time": datetime.datetime.now().strftime("%H:%M:%S")
            })
        else:
            results.append({
                "Pair": pair,
                "Prev RSI": "-",
                "Curr RSI": "-",
                "Signal": "Error",
                "Time": datetime.datetime.now().strftime("%H:%M:%S")
            })
        time.sleep(0.1)  # avoid API rate limit
    return results


# === Streamlit Interface ===
if st.button("🔍 Scan Now"):
    with st.spinner("Scanning for signals..."):
        scan_data = scan_pairs()
        st.success("Scan complete!")

        st.dataframe(scan_data, use_container_width=True)
else:
    st.info("Click the **Scan Now** button to check signals.")
  
