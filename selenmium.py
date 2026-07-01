import requests
import time
import json
import os
import re
import pandas as pd
from datetime import datetime, timezone
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
MAX_TWEETS = 2
MAX_AGE_MINUTES = 180
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
        except Exception as e:
            print(f"Telegram error: {e}")
        time.sleep(2)
    return False

def load_ticker_mapping():
    print("🔽 โหลดชื่อหุ้นจาก Excel...")
    df = pd.read_excel(TICKER_MAPPING_PATH)
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
    params = {"max_results": max(5, min(max_results, 100)), "tweet.fields": "created_at,text"}
    url = f"https://api.twitter.com/2/users/{user_id}/tweets"
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 429:
            return "RATE_LIMIT"
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        print(f"❌ Error fetching tweets: {e}")
        return []

def find_stocks_in_text(text, mapping):
    text_upper = re.sub(r"[^\w\s]", " ", text.upper())
    words = set(text_upper.split())
    return list({mapping[k] for k in mapping if k.upper() in words})

def fetch_stock_changes(symbols):
    changes = []
    for symbol in symbols:
        found_data = False
        for suffix in [".BK", ""]:
            try:
                ticker = symbol + suffix
                data = yf.download(ticker, period="2d", progress=False, auto_adjust=False)

                if data.empty or len(data) < 2 or "Close" not in data.columns:
                    continue

                close = data["Close"].dropna()
                if len(close) < 2:
                    continue

                prev_close = close.iloc[-2]
                latest_close = close.iloc[-1]

                if pd.notna(prev_close) and pd.notna(latest_close) and prev_close != 0:
                    pct = ((latest_close - prev_close) / prev_close) * 100
                    emoji = "🔼" if pct >= 0 else "🔽"
                    changes.append(f"{symbol}{suffix}: {emoji} {pct:.2f}%")
                    found_data = True
                    break  # พบข้อมูลแล้ว ออกจาก loop suffix
            except Exception as e:
                error_message = str(e)
                if "No data found, symbol may be delisted" in error_message or "404 Client Error" in error_message:
                    print(f"Yahoo error สำหรับ {symbol}{suffix}: ไม่พบข้อมูลหรืออาจถูกเพิกถอน")
                    changes.append(f"{symbol}: ❓ ไม่พบข้อมูลราคา")
                else:
                    print(f"Yahoo error {symbol}{suffix}: {e}")
        if not found_data and symbol not in [c.split(':')[0] for c in changes]:
            changes.append(f"{symbol}: ❓ ไม่มีข้อมูลราคา")
    return changes


def get_tradingview_news():
    try:
        url = "https://www.tradingview.com/markets/stocks-thailand/news/"
        html = requests.get(url, timeout=10).text
        soup = BeautifulSoup(html, "html.parser")
        articles = soup.select("div.tv-widget-news__item")
        news_list = []
        for a in articles:
            headline_element = a.select_one("span.tv-widget-news__headline")
            title_link_element = a.select_one("a.tv-widget-news__item-title")
            if headline_element and title_link_element and "href" in title_link_element.attrs:
                title = headline_element.text.strip()
                link = "https://www.tradingview.com" + title_link_element["href"]
                news_list.append((title, link))
            # else:
            #     print("⚠️ พบโครงสร้างข่าว TradingView ที่ไม่คาดคิด:", a.prettify()) # เพิ่มการตรวจสอบโครงสร้าง
        return news_list
    except Exception as e:
        print(f"❌ TradingView error: {e}")
        return []

# ===== MAIN LOOP =====
if __name__ == "__main__":
    ticker_mapping = load_ticker_mapping()
    log = load_log()
    log.setdefault("twitter", {})
    log.setdefault("tradingview", [])
    rate_limit_wait = 0   # ตัวแปรสำหรับหน่วงเวลาเมื่อติด Rate Limit

    while True:
        print(f"\n[] เริ่มเช็ก Twitter เวลา {time.strftime('%H:%M:%S')}")
        if rate_limit_wait > 0:
            print(f"⏳ กำลังรอเนื่องจาก Rate Limit ({rate_limit_wait} วินาที)...")
            time.sleep(rate_limit_wait)
            rate_limit_wait = 0

        for username, user_id in TWITTER_USERS.items():
            tweets = get_latest_tweets(user_id, MAX_TWEETS)
            if tweets == "RATE_LIMIT":
                print(f"❗ Rate limit reached for {username}. ข้ามและรอ...")
                rate_limit_wait = 600   # รอ 10 นาทีเมื่อติด Rate Limit
                continue

            print(f" @{username} ได้รับทวีต {len(tweets)} รายการ")
            log["twitter"].setdefault(username, [])
            new_tweets = []
            now = datetime.now(timezone.utc)

            for tweet in tweets:
                text = tweet["text"]
                created_at = datetime.strptime(tweet["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
                if (now - created_at).total_seconds() > MAX_AGE_MINUTES * 60: # เปลี่ยน MAX_AGE_MINUTES เป็น 60 เพื่อให้สอดคล้องกับการรอ Rate Limit
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
                    changes = fetch_stock_changes(stocks)
                    lines = [f"🆕 อัปเดตจาก @{username}:", f"🕒 {t['time']}", escape_markdown(t["text"])]
                    price_changes = [c for c in changes if "❓" not in c]
                    no_data_stocks = [c for c in changes if "❓" in c]

                    if price_changes:
                        lines.append("\n📊 ราคาเคลื่อนไหว:")
                        lines += [escape_markdown(c) for c in price_changes]
                    if no_data_stocks:
                        lines.append("\n⚠️ ไม่พบข้อมูลราคาสำหรับ:")
                        lines += [escape_markdown(c.split(':')[0]) for c in no_data_stocks]

                    if lines[-1].startswith("\n⚠️ ไม่พบข้อมูลราคาสำหรับ:") and len(lines) == 3:
                        print("ℹ️ พบหุ้น แต่ไม่มีข้อมูลราคา ส่ง Telegram.")
                    elif lines[-1].startswith("\n📊 ราคาเคลื่อนไหว:") or lines[-1].startswith("\n⚠️ ไม่พบข้อมูลราคาสำหรับ:"):
                        print("✅ พบการเปลี่ยนแปลงราคา/ไม่พบข้อมูล ส่ง Telegram.")
                    else:
                        print("ℹ️ ไม่มีการเปลี่ยนแปลงราคา/ไม่พบข้อมูล ส่ง Telegram.")

                    if send_telegram_alert("\n\n".join(lines)):
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
                changes = fetch_stock_changes(stocks)
                lines = [f"📰 TradingView:", escape_markdown(title), escape_markdown(link)]
                if changes:
                    price_changes = [c for c in changes if "❓" not in c]
                    no_data_stocks = [c for c in changes if "❓" in c]
                    if price_changes:
                        lines.append("\n📊 ราคาเคลื่อนไหว:")
                        lines += [escape_markdown(c) for c in price_changes]
                    if no_data_stocks:
                        lines.append("\n⚠️ ไม่พบข้อมูลราคาสำหรับ:")
                        lines += [escape_markdown(c.split(':')[0]) for c in no_data_stocks]
                if send_telegram_alert("\n\n".join(lines)):
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