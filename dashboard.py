import requests
import time
import json
import os
import re
import pandas as pd
from datetime import datetime, timedelta, timezone
import pytz
import yfinance as yf

# CONFIG

BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAMHn0wEAAAAAhlLyAxt2jg4ZBzaB%2BpCo1xA%2FvfY%3DFDEhAHlo5rWj7UsOoa8xnl9qCRXJrJyStjHq2f0xTCDB29L3au"
TELEGRAM_TOKEN = "7597463823:AAG_jeNnBUUyDtjsk53CbUV37bWgb-OSbsw"
TELEGRAM_CHAT_ID = "6678778888"

TWITTER_USERS = {
    "kaohoon": "149817617",
    "ElonMuskAOC": "11563153135",
    "BillGates": "548631313",
}

TICKER_MAPPING_PATH = "listedCompanies.xlsx"  # ไฟล์ชื่อหุ้น
LOG_PATH = "sent_log.json"
REFRESH_INTERVAL = 180
MAX_TWEETS = 5
MAX_AGE_MINUTES = 120
bangkok_tz = pytz.timezone("Asia/Bangkok")

#  HELPER FUNCTIONS
def escape_markdown(text):
    escape_chars = r"_*[]()~`>#+-=|{}.!\\"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

def load_log():
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_log(log):
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def send_telegram_alert(message, retries=3):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    for _ in range(retries):
        try:
            res = requests.post(url, data=payload, timeout=10)
            if res.status_code == 200:
                return True
            print(f"Telegram error {res.status_code}: {res.text}")
        except Exception as e:
            print(f"Telegram exception: {e}")
        time.sleep(2)
    return False

def load_ticker_mapping():
    print("🔽 กำลังโหลดรายชื่อหุ้นทั้งหมดจากไฟล์...")
    if not os.path.exists(TICKER_MAPPING_PATH):
        raise FileNotFoundError(f"ไม่พบไฟล์ {TICKER_MAPPING_PATH}")

    df = pd.read_excel(TICKER_MAPPING_PATH)
    if not all(col in df.columns for col in ["Symbol", "Company"]):
        raise ValueError("Excel ไม่มีคอลัมน์ 'Symbol' หรือ 'Company'")

    mapping = {}
    for _, row in df.iterrows():
        symbol = str(row['Symbol']).strip().upper()
        company = str(row['Company']).strip().upper()
        if symbol and symbol != "nan":
            mapping[symbol] = symbol
        if company and company != "nan":
            mapping[company] = symbol
    print("✅ โหลดรายชื่อหุ้นเรียบร้อย")
    return mapping

def get_latest_tweets(user_id, max_results=5):
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}"
    }
    params = {
        "max_results": max(5, min(max_results, 100)),
        "tweet.fields": "created_at,text"
    }
    url = f"https://api.twitter.com/2/users/{user_id}/tweets"
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 429:
            return "RATE_LIMIT"
        if response.status_code != 200:
            print(f"Error fetching tweets for {user_id}: {response.text}")
            return []
        data = response.json()
        if "data" not in data:
            print(f"No data in response for {user_id}: {data}")
            return []
        return data["data"]
    except Exception as e:
        print(f"Exception fetching tweets for {user_id}: {e}")
        return []

def find_stocks_in_text(text, ticker_mapping):
    found = []
    text_upper = text.upper()
    for name in ticker_mapping.keys():
        if name in text_upper:
            found.append(ticker_mapping[name])
    return list(set(found))  # ไม่ซ้ำกัน

def fetch_stock_changes(symbols):
    changes = []
    for symbol in symbols:
        try:
            for suffix in [".BK", ""]:
                ticker = symbol + suffix
                data = yf.download(ticker, period="2d", progress=False, auto_adjust=False)

                # ตรวจสอบว่าข้อมูลไม่ว่าง และมีอย่างน้อย 2 แถว
                if data is not None and not data.empty and "Close" in data.columns:
                    close_series = data["Close"].dropna()
                    if len(close_series) >= 2:
                        prev_close = close_series.iloc[-2]
                        latest_close = close_series.iloc[-1]

                        if pd.notna(prev_close) and pd.notna(latest_close) and prev_close != 0:
                            pct_change = ((latest_close - prev_close) / prev_close) * 100
                            emoji = "🔼" if pct_change >= 0 else "🔽"
                            changes.append(f"{symbol}: {emoji} {pct_change:.2f}%")
                        else:
                            changes.append(f"{symbol}: ข้อมูลไม่เพียงพอ")
                    else:
                        continue
                    break  # หากโหลดสำเร็จแล้ว ไม่ต้องลอง suffix ถัดไป
        except Exception as e:
            print(f"Error fetching data for {symbol} from Yahoo Finance: {e}")
            changes.append(f"{symbol}: Error fetching data")
    return changes


# ===== MAIN PROGRAM =====
if __name__ == "__main__":
    ticker_mapping = load_ticker_mapping()
    log = load_log()

    while True:
        print(f"\n[] เริ่มเช็ก Twitter เวลา {time.strftime('%H:%M:%S')}")
        for username, user_id in TWITTER_USERS.items():
            try:
                tweets = get_latest_tweets(user_id, MAX_TWEETS)
                if tweets == "RATE_LIMIT":
                    print(f"❗ Rate limit reached for {user_id}. ข้าม user นี้ไป...")
                    continue

                print(f" @{username} ได้รับทวีต {len(tweets)} รายการ")
                if username not in log:
                    log[username] = []

                now = datetime.now(timezone.utc)
                new_tweets = []

                for tweet in tweets:
                    tweet_text = tweet["text"]
                    created_at = datetime.strptime(tweet["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
                    age = now - created_at

                    if age.total_seconds() > MAX_AGE_MINUTES * 60:
                        continue

                    if tweet_text not in log[username]:
                        local_time = created_at.astimezone(bangkok_tz).strftime("%d/%m/%Y %H:%M")
                        new_tweets.append({
                            "text": tweet_text,
                            "time": local_time
                        })
                        log[username].append(tweet_text)

                if new_tweets:
                    for t in new_tweets:
                        stocks = find_stocks_in_text(t['text'], ticker_mapping)
                        stock_changes = fetch_stock_changes(stocks) if stocks else []

                        lines = [f"อัปเดตจาก @{username}", f"🕒 {t['time']}", escape_markdown(t['text'])]
                        if stock_changes:
                            lines.append("\n📊 ราคาเคลื่อนไหว:")
                            for change in stock_changes:
                                lines.append(escape_markdown(change))

                        message = "\n\n".join(lines)
                        if send_telegram_alert(message):
                            print(f"✅ ส่ง Telegram สำเร็จ")
                        else:
                            print(f"❌ ส่ง Telegram ล้มเหลว")
                else:
                    print(f"ℹ️ ไม่มีโพสต์ใหม่จาก @{username}")

                log[username] = log[username][-100:]

            except Exception as e:
                print(f"เกิดข้อผิดพลาดกับ @{username}: {e}")

        save_log(log)
        print(f"⏳ รอ {REFRESH_INTERVAL} วินาที...\n")
        time.sleep(REFRESH_INTERVAL)
