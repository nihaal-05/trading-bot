import requests
import time
import datetime
import os
import pytz

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

INITIAL_CAPITAL = 20000
capital = INITIAL_CAPITAL

wins = 0
losses = 0
total_trades = 0
start_time = datetime.datetime.now()

last_spot = None

# ---------------- TELEGRAM ----------------
def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": CHAT_ID, "text": msg})
        print("📩", msg)
    except Exception as e:
        print("Telegram error:", e)

# ---------------- SESSION ----------------
session = requests.Session()
headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.nseindia.com/"
}

def fetch(symbol):
    try:
        session.get("https://www.nseindia.com", headers=headers)
        time.sleep(1)
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        res = session.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(symbol, "fetch error:", e)
    return None

# ---------------- MARKET (IST) ----------------
def market_open():
    india = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(india)

    print("🕒 IST:", now.strftime("%H:%M:%S"))

    if now.weekday() >= 5:
        return False
    if now.hour < 9 or now.hour > 15:
        return False
    if now.hour == 9 and now.minute < 15:
        return False
    if now.hour == 15 and now.minute > 30:
        return False

    return True

# ---------------- TREND ----------------
def get_trend(current):
    global last_spot
    if last_spot is None:
        last_spot = current
        return "side"

    trend = "up" if current > last_spot else "down"
    last_spot = current
    return trend

# ---------------- SMART FINDER ----------------
def find_trades(symbol, data):
    try:
        spot = data["records"]["underlyingValue"]
        trend = get_trend(spot)

        trades = []
        near_miss = []

        for item in data["records"]["data"]:
            strike = item["strikePrice"]

            if abs(strike - spot) > 200:
                continue

            for opt in ["CE", "PE"]:
                if not item.get(opt):
                    continue

                price = item[opt]["lastPrice"]
                ath = item[opt]["highPrice"]
                vol = item[opt].get("totalTradedVolume", 0)

                if price == 0 or ath == 0:
                    continue

                l1 = ath * 0.1
                l2 = ath * 0.05
                l3 = ath * 0.01

                near_l1 = abs(price - l1) < 5
                near_l2 = abs(price - l2) < 3
                near_l3 = abs(price - l3) < 1

                near_level = near_l1 or near_l2 or near_l3

                if not near_level:
                    near_miss.append(f"{strike}{opt} ❌ level miss")
                    continue

                if vol < 30000:
                    near_miss.append(f"{strike}{opt} ❌ low vol")
                    continue

                if near_l3 and vol < 100000:
                    continue

                if trend == "up" and opt != "CE":
                    continue
                if trend == "down" and opt != "PE":
                    continue

                score = vol + (ath - price)

                trade = {
                    "symbol": symbol,
                    "type": opt,
                    "strike": strike,
                    "entry": round(price, 2),
                    "target": round(price * 2, 2),
                    "stop": round(l2, 2),
                    "level": "L1" if near_l1 else "L2" if near_l2 else "L3",
                    "score": int(score)
                }

                trades.append(trade)

        trades = sorted(trades, key=lambda x: x["score"], reverse=True)

        return trades[:3], near_miss[:5]

    except Exception as e:
        print("Find error:", e)
        return [], []

# ---------------- DASHBOARD ----------------
def dashboard():
    duration = datetime.datetime.now() - start_time
    winrate = (wins / total_trades * 100) if total_trades else 0

    return f"""
📊 DASHBOARD

💰 Capital: ₹{capital}
📈 Trades: {total_trades}
📊 Win Rate: {round(winrate,2)}%
⏱ {str(duration).split('.')[0]}
"""

# ---------------- START ----------------
send("🚀 SMART BOT STARTED")

# ---------------- MAIN LOOP ----------------
while True:
    try:
        if not market_open():
            print("❌ Market Closed")
            time.sleep(300)
            continue

        print("🔍 Scanning...")

        data_n = fetch("NIFTY")
        data_b = fetch("BANKNIFTY")

        all_trades = []
        near_miss = []

        if data_n:
            t, nm = find_trades("NIFTY", data_n)
            all_trades += t
            near_miss += nm

        if data_b:
            t, nm = find_trades("BANKNIFTY", data_b)
            all_trades += t
            near_miss += nm

        if all_trades:
            msg = "🔥 TOP TRADES\n\n"
            for t in all_trades[:3]:
                msg += f"""
{t['symbol']} {t['type']} {t['strike']}
Level: {t['level']}
Entry: ₹{t['entry']}
Target: ₹{t['target']}
Stop: ₹{t['stop']}
Score: {t['score']}
--------------------
"""
            send(msg)
        else:
            msg = "⚠️ No trades\n\nNear Miss:\n"
            msg += "\n".join(near_miss[:5])
            send(msg)

        send(dashboard())

        time.sleep(60)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(10)
