import requests
import time
import datetime
import os

# ---------------- CONFIG ----------------

BOT_TOKEN = os.getenv("8693950578:AAF9BMa8KJfzADOweHNG8BncxjMgOTwM6NA")
CHAT_ID = os.getenv("8039697310")

INITIAL_CAPITAL = 20000
capital = INITIAL_CAPITAL

total_trades = 0
wins = 0
losses = 0
start_time = datetime.datetime.now()

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

def refresh_session():
    try:
        session.get("https://www.nseindia.com", headers=headers)
        time.sleep(2)
        print("Session refreshed")
    except:
        print("Session error")

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

# ---------------- FETCH ----------------
def fetch(symbol):
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=" + symbol

    for i in range(3):  # retry 3 times
        try:
            session.get("https://www.nseindia.com/option-chain", headers=headers)
            time.sleep(1)

            res = session.get(url, headers=headers, timeout=5)

            if res.status_code == 200:
                return res.json()

        except:
            pass

        print(f"{symbol} retry {i+1}")

    return None

# ---------------- TRADE FINDER ----------------
def find_trade(symbol, data):
    spot = data["records"]["underlyingValue"]

    for item in data["records"]["data"]:
        for opt in ["CE", "PE"]:
            if item.get(opt):

                price = item[opt]["lastPrice"]
                ath = item[opt]["highPrice"]

                if 2 <= price <= 20 and ath >= 10:

                    l1 = round(ath * 0.1, 2)

                    return {
                        "symbol": symbol,
                        "type": opt,
                        "strike": item["strikePrice"],
                        "price": price,
                        "target": price * 2,
                        "stop": l1
                    }

    return None

# ---------------- SIMULATE RESULT ----------------
def execute_trade(trade):
    global total_trades, wins, losses, capital

    total_trades += 1

    risk = 500  # fixed risk per trade

    import random
    win = random.choice([True, False])

    if win:
        profit = risk * 2
        capital += profit
        wins += 1
        result = "WIN ✅"
    else:
        capital -= risk
        losses += 1
        result = "LOSS ❌"

    return result, capital

# ---------------- DASHBOARD ----------------
def dashboard():
    duration = datetime.datetime.now() - start_time

    winrate = (wins / total_trades * 100) if total_trades > 0 else 0

    return f"""
📊 DASHBOARD

💰 Capital: ₹{capital}
📈 Trades: {total_trades}
✅ Wins: {wins}
❌ Losses: {losses}

📊 Win Rate: {round(winrate,2)}%
💸 P&L: ₹{capital - INITIAL_CAPITAL}

⏱ Running: {str(duration).split('.')[0]}
"""

# ---------------- MAIN ----------------
print("🚀 BOT STARTED")

refresh_session()

send("🤖 Bot started with ₹20,000 capital")

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
🔥 TRADE

{trade['symbol']} {trade['type']}
Strike: {trade['strike']}

Entry: ₹{trade['price']}
Target: ₹{trade['target']}
Stop: ₹{trade['stop']}
"""

            send(msg)

            result, cap = execute_trade(trade)

            send(f"Result: {result}")

            send(dashboard())

        else:
            print("No trade")

        time.sleep(60)

    except Exception as e:
        print("Error:", e)
        time.sleep(10)
