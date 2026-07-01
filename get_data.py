import requests
import time
import json
import os
import re
import pandas as pd
from datetime import datetime, timedelta, timezone
import pytz
import yfinance as yf
from bs4 import BeautifulSoup

# ===== CONFIG =====

BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAHGp0wEAAAAACSnnZ2lgi8BaMCsyZQQ24O0ni2A%3DChXhFirBumjH0ds4gRAKftXrOwGA22kIXGQLAVZYCLnYqlP2rm"
TELEGRAM_TOKEN = "7597463823:AAG_jeNnBUUyDtjsk53CbUV37bWgb-OSbsw"
TELEGRAM_CHAT_ID = "6678778888"

TWITTER_USERS = {
    "kaohoon": "149817617"
}

TICKER_MAPPING_PATH = "listedCompanies.xlsx"
LOG_PATH = "sent_log.json"
REFRESH_INTERVAL = 300
MAX_TWEETS = 5
MAX_AGE_MINUTES = 120
bangkok_tz = pytz.timezone("Asia/Bangkok")


# ===== HELPER FUNCTIONS =====

def escape_markdown(text):
    escape_chars = r"_*[]()~`>#+-=|{}.!\\"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

def load_log():
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"twitter": {}, "tradingview": []}

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
    print("🔽 โหลดชื่อหุ้นจาก Excel...")
    if not os.path.exists(TICKER_MAPPING_PATH):
        raise FileNotFoundError(f"ไม่พบไฟล์ {TICKER_MAPPING_PATH}")
    df = pd.read_excel(TICKER_MAPPING_PATH)
    if not all(col in df.columns for col in ["Symbol", "Company"]):
        raise ValueError("Excel ต้องมีคอลัมน์ 'Symbol' และ 'Company'")
    mapping = {}
    for _, row in df.iterrows():
        symbol = str(row["Symbol"]).strip().upper()
        company = str(row["Company"]).strip().upper()
        if symbol and symbol != "nan":
            mapping[symbol] = symbol
        if company and company != "nan":
            mapping[company] = symbol
    print("✅ โหลดชื่อหุ้นสำเร็จ")
    return mapping

def get_latest_tweets(user_id, max_results=5):
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
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
            print(f"Error fetching tweets: {response.text}")
            return []
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        print(f"Exception fetching tweets: {e}")
        return []

def find_stocks_in_text(text, mapping):
    text_upper = re.sub(r"[^\w\s]", " ", text.upper())  # remove punctuation
    words = set(text_upper.split())
    found = []
    for key in mapping:
        if key.upper() in words:
            found.append(mapping[key])
    return list(set(found))

def fetch_stock_changes(symbols):
    changes = []
    for symbol in symbols:
        try:
            for suffix in [".BK", ""]:
                ticker = symbol + suffix
                data = yf.download(ticker, period="2d", progress=False, auto_adjust=False)

                # เช็กว่าได้ข้อมูล และมีคอลัมน์ Close
                if data is None or data.empty or "Close" not in data.columns:
                    continue

                close_series = data["Close"].dropna()

                # ต้องมีอย่างน้อย 2 ค่า
                if len(close_series) < 2:
                    continue

                prev_close = close_series.iloc[-2]
                latest_close = close_series.iloc[-1]

                # ป้องกันหารศูนย์
                if pd.notna(prev_close) and pd.notna(latest_close) and prev_close != 0:
                    pct_change = ((latest_close - prev_close) / prev_close) * 100
                    emoji = "🔼" if pct_change >= 0 else "🔽"
                    changes.append(f"{symbol}: {emoji} {pct_change:.2f}%")

                break  # ถ้าโหลดสำเร็จจาก suffix นี้แล้ว ไม่ต้องลองต่อ
        except Exception as e:
            print(f"Yahoo error {symbol}: {e}")
    return changes



def get_tradingview_news():
    try:
        url = "https://www.tradingview.com/markets/stocks-thailand/news/"
        html = requests.get(url, timeout=10).text
        soup = BeautifulSoup(html, "html.parser")
        articles = soup.select("div.tv-widget-news__item")
        news = []
        for a in articles:
            title_elem = a.select_one("span.tv-widget-news__headline")
            link_elem = a.select_one("a.tv-widget-news__item-title")
            if title_elem and link_elem:
                title = title_elem.text.strip()
                link = "https://www.tradingview.com" + link_elem["href"]
                news.append((title, link))
        return news
    except Exception as e:
        print(f"❌ TradingView error: {e}")
        return []

# ===== MAIN LOOP =====

if __name__ == "__main__":
    ticker_mapping = load_ticker_mapping()
    log = load_log()
    if "twitter" not in log: log["twitter"] = {}
    if "tradingview" not in log: log["tradingview"] = []

    while True:
        print(f"\n[] เริ่มเช็ก Twitter เวลา {time.strftime('%H:%M:%S')}")
        for username, user_id in TWITTER_USERS.items():
            tweets = get_latest_tweets(user_id, MAX_TWEETS)
            if tweets == "RATE_LIMIT":
                print(f"❗ Rate limit reached for {user_id}. ข้าม...")
                continue

            print(f" @{username} ได้รับทวีต {len(tweets)} รายการ")
            if username not in log["twitter"]:
                log["twitter"][username] = []

            new_tweets = []
            now = datetime.now(timezone.utc)

            for tweet in tweets:
                text = tweet["text"]
                created_at = datetime.strptime(tweet["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
                if (now - created_at).total_seconds() > MAX_AGE_MINUTES * 60:
                    continue
                if text in log["twitter"][username]:
                    print("❌ ไม่ได้ส่งเพราะมีใน log แล้ว")
                    continue
                local_time = created_at.astimezone(bangkok_tz).strftime("%d/%m/%Y %H:%M")
                new_tweets.append({"text": text, "time": local_time})
                log["twitter"][username].append(text)

            if new_tweets:
                for t in new_tweets:
                    stocks = find_stocks_in_text(t["text"], ticker_mapping)
                    stock_changes = fetch_stock_changes(stocks)
                    lines = [f"อัปเดตจาก @{username}", f"🕒 {t['time']}", escape_markdown(t["text"])]
                    if stock_changes:
                        lines.append("📊 ราคาเคลื่อนไหว:")
                        for chg in stock_changes:
                            lines.append(escape_markdown(chg))
                    message = "\n\n".join(lines)
                    if send_telegram_alert(message):
                        print("✅ ส่ง Telegram สำเร็จ")
                    else:
                        print("❌ ส่ง Telegram ล้มเหลว")
            else:
                print("ℹ️ ไม่พบข่าวใหม่")

            log["twitter"][username] = log["twitter"][username][-100:]

        print("[] ตรวจสอบข่าวจาก TradingView...")
        news_items = get_tradingview_news()
        new_items = [n for n in news_items if n[1] not in log["tradingview"]]

        if new_items:
            for title, link in new_items:
                print("🆕 พบข่าวใหม่จาก TradingView:", title)
                stocks = find_stocks_in_text(title, ticker_mapping)
                stock_changes = fetch_stock_changes(stocks)
                lines = [f"📰 TradingView:", escape_markdown(title), escape_markdown(link)]
                if stock_changes:
                    lines.append("📊 ราคาเคลื่อนไหว:")
                    for chg in stock_changes:
                        lines.append(escape_markdown(chg))
                message = "\n\n".join(lines)
                if send_telegram_alert(message):
                    print("✅ ส่งข่าว TradingView สำเร็จ")
                else:
                    print("❌ ส่ง TradingView ไม่สำเร็จ")
                log["tradingview"].append(link)
        else:
            print("ℹ️ ไม่พบข่าวใหม่จาก TradingView")

        log["tradingview"] = log["tradingview"][-100:]
        save_log(log)
        print(f"⏳ รอ {REFRESH_INTERVAL} วินาที...\n")
        time.sleep(REFRESH_INTERVAL)
