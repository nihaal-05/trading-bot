import requests
import time
import datetime
import os

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
active_trade = None

# ---------------- TELEGRAM ----------------
def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": CHAT_ID, "text": msg})
        print(msg)
    except:
        print("Telegram error")

# ---------------- SESSION ----------------
session = requests.Session()
headers = {"User-Agent": "Mozilla/5.0"}

def fetch(symbol):
    try:
        session.get("https://www.nseindia.com", headers=headers)
        time.sleep(1)
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        res = session.get(url, headers=headers)
        if res.status_code == 200:
            return res.json()
    except:
        return None

# ---------------- MARKET ----------------
def market_open():
    now = datetime.datetime.now()
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

# ---------------- HYBRID TRADE FINDER ----------------
def find_trade(symbol, data):
    spot = data["records"]["underlyingValue"]
    trend = get_trend(spot)

    best = None

    for item in data["records"]["data"]:
        strike = item["strikePrice"]

        # Near ATM filter
        if abs(strike - spot) > 100:
            continue

        for opt in ["CE", "PE"]:
            if item.get(opt):

                price = item[opt]["lastPrice"]
                ath = item[opt]["highPrice"]
                vol = item[opt].get("totalTradedVolume", 0)

                # -------- YOUR LEVELS --------
                l1 = ath * 0.1
                l2 = ath * 0.05
                l3 = ath * 0.01

                near_l1 = abs(price - l1) < 2
                near_l2 = abs(price - l2) < 1
                near_l3 = abs(price - l3) < 0.5

                near_level = near_l1 or near_l2 or near_l3

                if not near_level:
                    continue

                # -------- SAFETY FILTERS --------
                if vol < 100000:
                    continue

                if near_l3 and vol < 200000:
                    continue

                # -------- TREND FILTER --------
                if trend == "up" and opt != "CE":
                    continue
                if trend == "down" and opt != "PE":
                    continue

                score = vol + (ath - price)

                if best is None or score > best["score"]:
                    best = {
                        "symbol": symbol,
                        "type": opt,
                        "strike": strike,
                        "entry": round(price, 2),
                        "target": round(price * 2, 2),
                        "stop": round(l2, 2),
                        "level": "L1" if near_l1 else "L2" if near_l2 else "L3",
                        "score": score
                    }

    return best

# ---------------- TRACK TRADE ----------------
def track_trade(trade):
    global active_trade, capital, wins, losses, total_trades

    if active_trade is None:
        active_trade = trade
        send(f"✅ ENTRY ({trade['level']}) at ₹{trade['entry']}")
        return

    current = trade["entry"]

    if current >= trade["target"]:
        capital += 1000
        wins += 1
        total_trades += 1
        send("🎯 TARGET HIT")
        active_trade = None

    elif current <= trade["stop"]:
        capital -= 500
        losses += 1
        total_trades += 1
        send("🛑 STOPLOSS HIT")
        active_trade = None

# ---------------- DASHBOARD ----------------
def dashboard():
    duration = datetime.datetime.now() - start_time
    winrate = (wins / total_trades * 100) if total_trades else 0

    return f"""
📊 FINAL DASHBOARD

💰 Capital: ₹{capital}
📈 Trades: {total_trades}
✅ Wins: {wins}
❌ Losses: {losses}

📊 Win Rate: {round(winrate,2)}%
💸 P&L: ₹{capital - INITIAL_CAPITAL}

⏱ {str(duration).split('.')[0]}
"""

# ---------------- MAIN ----------------
send("🚀 FINAL HYBRID BOT STARTED")

while True:
    try:
        if not market_open():
            print("Market closed")
            time.sleep(300)
            continue

        print("Scanning...")

        data_n = fetch("NIFTY")
        data_b = fetch("BANKNIFTY")

        trade = None

        if data_n:
            trade = find_trade("NIFTY", data_n)

        if not trade and data_b:
            trade = find_trade("BANKNIFTY", data_b)

        if trade:
            msg = f"""
🔥 TRADE ({trade['level']})

{trade['symbol']} {trade['type']}
Strike: {trade['strike']}

Entry: ₹{trade['entry']}
Target: ₹{trade['target']}
Stop: ₹{trade['stop']}
"""
            send(msg)
            track_trade(trade)
            send(dashboard())

        else:
            print("No high quality trade")

        time.sleep(60)

    except Exception as e:
        print("Error:", e)
        time.sleep(10)
