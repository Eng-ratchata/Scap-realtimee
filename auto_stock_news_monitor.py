import time
import re
import pandas as pd
import yfinance as yf
from selenium import webdriver
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
from datetime import datetime

# ---------- CONFIG ----------
MARKETS = {
    "US": "https://www.tradingview.com/markets/stocks-usa/market-movers-large-cap/",
    "TH": "https://www.tradingview.com/markets/stocks-thailand/market-movers-large-cap/",
    "HK": "https://www.tradingview.com/markets/stocks-hong-kong/market-movers-large-cap/"
}
DATABASE_FILE = "stock_database.xlsx"
UNKNOWN_LOG_FILE = "unknown_names_log.txt"
REFRESH_INTERVAL = 300  # วินาที (5 นาที)
# ----------------------------

# ---------- STEP 1: สร้างฐานข้อมูลหุ้น ----------
def simplify_name(name):
    return name.split(" ")[0].strip(",.()")

def fetch_symbols_from_market(market_name, url):
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    data = []

    with uc.Chrome(options=options) as driver:
        try:
            driver.get(url)
            time.sleep(5)

            rows = driver.find_elements(By.CSS_SELECTOR, 'tbody tr')
            for row in rows:
                try:
                    symbol = row.find_element(By.CSS_SELECTOR, 'td:nth-child(1) a').text.strip()
                    name = row.find_element(By.CSS_SELECTOR, 'td:nth-child(2)').text.strip()
                    alt_name = simplify_name(name)
                    data.append({"symbol": symbol, "name": name, "alt_names": alt_name, "market": market_name})
                except:
                    continue
        except Exception as e:
            print(f"❌ Error fetching from {market_name}: {e}")

    return data

def generate_stock_database():
    all_data = []
    for market, url in MARKETS.items():
        print(f"📥 Fetching from {market} ...")
        market_data = fetch_symbols_from_market(market, url)
        all_data.extend(market_data)

    df = pd.DataFrame(all_data)
    df.drop_duplicates(subset=["symbol"], inplace=True)
    df.to_excel(DATABASE_FILE, index=False)
    print(f"✅ Stock database saved to {DATABASE_FILE}")

# ---------- STEP 2: โหลดฐานข้อมูลและเตรียมชื่อ ----------
def load_stock_database():
    df = pd.read_excel(DATABASE_FILE)
    df["alt_names"] = df["alt_names"].fillna("").astype(str)
    all_names = set(df["name"].str.lower())

    for alt in df["alt_names"]:
        for name in alt.split(","):
            all_names.add(name.strip().lower())

    return df, all_names

def extract_potential_names(text):
    matches = re.findall(r'\b[A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})?\b', text)
    return set(matches)

def log_unknown_names(potential_names, known_names):
    unknowns = [name for name in potential_names if name.lower() not in known_names]
    if unknowns:
        with open(UNKNOWN_LOG_FILE, "a", encoding="utf-8") as f:
            for name in unknowns:
                f.write(name + "\n")
        print(f"🚨 พบชื่อใหม่ {len(unknowns)} ชื่อ → บันทึกลง {UNKNOWN_LOG_FILE}")
    else:
        print("✅ ไม่มีชื่อใหม่ในข่าว")

# ---------- STEP 3: ตรวจชื่อในข่าวและดึงราคาหุ้น ----------
def find_matching_stocks(news_text, stock_df):
    matched = []
    news_lower = news_text.lower()

    for _, row in stock_df.iterrows():
        name_list = [row["name"]]
        if row["alt_names"]:
            name_list += [n.strip() for n in str(row["alt_names"]).split(",")]

        for name in name_list:
            if name.lower() in news_lower:
                matched.append(row)
                break

    return matched

def fetch_price_change(ticker):
    try:
        data = yf.Ticker(ticker).history(period="2d")
        if len(data) >= 2:
            prev_close = data.iloc[-2]["Close"]
            latest_close = data.iloc[-1]["Close"]
            change_pct = ((latest_close - prev_close) / prev_close) * 100
            return latest_close, change_pct
    except Exception as e:
        print(f"❌ Error fetching price for {ticker}: {e}")
    return None, None

def process_news(news_text):
    stock_df, known_names = load_stock_database()
    potential_names = extract_potential_names(news_text)
    log_unknown_names(potential_names, known_names)

    matches = find_matching_stocks(news_text, stock_df)
    if not matches:
        print("🔍 ไม่พบชื่อหุ้นในข่าว")
        return

    print("\n📊 สรุปผลหุ้นจากข่าว:")
    for row in matches:
        latest_price, change = fetch_price_change(row["symbol"])
        if latest_price:
            print(f"• {row['name']} ({row['symbol']}, {row['market']}) → {latest_price:.2f} บาท ({change:+.2f}%)")
        else:
            print(f"⚠️ ไม่สามารถดึงราคาของ {row['symbol']} ได้")

# ---------- MAIN LOOP ----------
if __name__ == "__main__":
    while True:
        print(f"\n🕒 เริ่มรอบใหม่: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        generate_stock_database()

        # ข่าวตัวอย่าง
        sample_news = """
        บริษัท PTT รายงานผลประกอบการไตรมาสแรกเพิ่มขึ้น 15% ขณะที่ Apple และ Tencent ประกาศยอดขายลดลงในตลาดจีน
        """

        process_news(sample_news)

        print(f"⌛ รอ {REFRESH_INTERVAL} วินาที...\n")
        time.sleep(REFRESH_INTERVAL)
