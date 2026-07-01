# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta, timezone

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta, timezone
from deep_translator import GoogleTranslator
import time
import os
import requests
import html
import pandas as pd
import re

# --- CONFIG ---
CHROME_PROFILE_PATH = r"C:\ChromeProfileBot"

TELEGRAM_TOKEN = "7597463823:AAG_jeNnBUUyDtjsk53CbUV37bWgb-OSbsw"
TELEGRAM_CHAT_ID = "6678778888"

STOCK_DATA_FILE = r"C:\Users\Eng\Desktop\Scap-realtime\us_stocks_full_name.xlsx"
TRADINGVIEW_URL = "https://www.tradingview.com/news-flow/"
LAST_TIMESTAMP_FILE = "last_timestamp.txt"
SENT_LOG_FILE = "sent_news_log.txt"

MAX_NEWS_FULL_TEXT_LENGTH = 1500

# **ปรับปรุง:** รายการคำที่ควรหลีกเลี่ยงการตรวจจับว่าเป็นหุ้น (common English words)
# ขยายรายการให้ครอบคลุมคำที่พบบ่อยในข่าวการเงินแต่ไม่ใช่หุ้น
COMMON_WORDS_TO_EXCLUDE = {
    "A", "AN", "THE", "IN", "ON", "AT", "BY", "FOR", "WITH", "OF", "TO", "IS", "ARE", "WAS", "WERE",
    "BE", "HAS", "HAD", "HAVE", "DO", "DOES", "DID", "NOT", "BUT", "OR", "AND", "AS", "IF", "IT",
    "FROM", "OUT", "UP", "DOWN", "NEW", "OLD", "GOOD", "BAD", "GREAT", "MORE", "LESS", "MUCH", "MANY",
    "SOME", "ANY", "NO", "YES", "ME", "YOU", "HE", "SHE", "IT", "WE", "THEY", "MY", "YOUR", "HIS",
    "HER", "ITS", "OUR", "THEIR", "THIS", "THAT", "THESE", "THOSE", "WHAT", "WHERE", "WHEN", "WHY",
    "HOW", "WHO", "WHICH", "WILL", "WOULD", "CAN", "COULD", "SHALL", "SHOULD", "MAY", "MIGHT", "MUST",
    "KNOW", "SEE", "MAKE", "GET", "GO", "COME", "TAKE", "GIVE", "FIND", "TELL", "ASK", "WORK", "SEEM",
    "FEEL", "TRY", "LEAVE", "CALL", "USE", "FORM", "CASH", "UNIT", "REG", "ALL", "KEY", "FIVE", "COST", "LOW",
    "WELL", "BASE", "COST", "FORM", "UNIT", "TIGHT", "HIGH", "HELD", "DATA", "SAID", "FROM", "NOTE",
    "WEDNESDAY", "RATE", "FED", "BANK", "MARKET", "PRICES", "GROWTH", "EARNINGS", "PROFIT", "LOSS",
    "SALES", "REVENUE", "REPORT", "GUIDANCE", "OUTLOOK", "DEAL", "ACQUISITION", "MERGER", "PARTNERSHIP",
    "INVESTMENT", "DEBT", "LOAN", "BONDS", "SHARES", "STOCK", "DIVIDEND", "ANALYST", "TARGET", "PRICE",
    "UPDATE", "COMPANY", "GROUP", "CORP", "INC", "LTD", "PLC", "HOLDINGS", "CAPITAL", "GLOBAL", "NATIONAL",
    "INTERNATIONAL", "TECHNOLOGY", "HEALTHCARE", "FINANCIAL", "ENERGY", "MANUFACTURING", "SERVICES",
    # เพิ่มคำที่พบบ่อยในข่าวของคุณที่มักถูกจับผิด
    "RIG", "AIR", "SITE", "TWO", "CORE", "GOLD", "COPPER", "TREND", "PROJECT", "NEW", "SOUTH", "WALES",
    "TARGET", "AREA", "ANOMALY", "DRILLING", "PROGRAM", "MINERALIZED", "HOST", "ROCKS", "PATHFINDER",
    "GEOCHEMICAL", "RELATED", "METAL", "CIRCULATION", "REVERSE", "BEGUN", "RECENT", "TRADING", "THURSDAY",
    "JUMPED", "PERCENT", "PERFORMANCE", "STRONG", "WEAK", "EXPECTATIONS", "RESULT", "OUTLOOK", "PLAN",
    "STRATEGY", "DEVELOPMENT", "BUSINESS", "INDUSTRY", "ECONOMY", "GOVERNMENT", "POLICY", "REGULATION",
    "AGREEMENT", "RESOLUTION", "STATEMENT", "RELEASE", "ANNOUNCEMENT", "FORECAST", "ESTIMATE", "PREDICTION",
    "CONSENSUS", "OPINION", "VIEW", "COMMENT", "RESPONSE", "ACTION", "INITIATIVE", "MEASURE", "FUND",
    "COMMITTEE", "BOARD", "EXECUTIVE", "MANAGEMENT", "LEADER", "OFFICIAL", "SOURCE", "REPORTED", "ACCORDING",
    "FILED", "ISSUED", "PUBLISHED", "PROVIDED", "UPDATED", "CONFIRMED", "DENIED", "PROJECTED", "ANTICIPATED",
    "EXPECTED", "CONTINUED", "LIMITED", "MAJOR", "MINOR", "CRITICAL", "IMPORTANT", "SIGNIFICANT", "SMALL",
    "LARGE", "HIGH", "LOW", "LONG", "SHORT", "PUBLIC", "PRIVATE", "DOMESTIC", "FOREIGN", "NATIONAL",
    "REGIONAL", "LOCAL", "GLOBAL", "WORLD", "US", "UNITED", "STATES", "AMERICAN", "EUROPEAN", "ASIAN",
    "CHINESE", "JAPANESE", "INDIAN", "AUSTRALIAN", "CANADIAN", "MEXICAN", "BRAZILIAN", "RUSSIAN", "BRITISH",
    "GERMAN", "FRENCH", "ITALIAN", "SPANISH", "ARAB", "MIDDLE", "EASTERN", "AFRICAN"
}

# **ใหม่:** Keywords สำหรับการระบุ sentiment (ขึ้นหรือลง)
POSITIVE_KEYWORDS = {
    "RISE", "INCREASE", "GROWTH", "GAIN", "UP", "BOOST", "EXPAND", "STRONG", "POSITIVE", "PROFIT",
    "ACCELERATE", "OUTPERFORM", "SUCCESS", "IMPROVE", "SURGE", "RALLY", "BREAKTHROUGH", "WIN",
    "BEAT", "EXCEED", "ADVANCE", "LIFT", "SUPPORT", "EXPECTATIONS", "OPTIMISTIC", "JUMPED", "JUMP",
    "INCREASED", "ROSE", "GAINED", "UPWARD", "HIGHER"
}

NEGATIVE_KEYWORDS = {
    "FALL", "DECREASE", "DROP", "LOSE", "DOWN", "CUT", "REDUCE", "WEAK", "NEGATIVE", "LOSS",
    "DECLINE", "UNDERPERFORM", "FAIL", "DIP", "SLUMP", "WORRY", "CONCERN", "RISK", "CHALLENGE",
    "MISS", "BELOW", "WARNING", "PRESSURE", "VOLATILITY", "RECESSION", "SLOWDOWN", "TURMOIL",
    "FALLEN", "DROPPED", "DECREASED", "LOWER", "DOWNWARD"
}


# --- โหลดชื่อหุ้นจาก Excel ---
def load_stock_names():
    stock_map = {}
    try:
        print(f"กำลังโหลดชื่อหุ้นจากไฟล์ Excel: {STOCK_DATA_FILE}...")
        df = pd.read_excel(STOCK_DATA_FILE)
        print(f"✅ โหลดชื่อหุ้นสำเร็จจาก {STOCK_DATA_FILE}")
    except FileNotFoundError:
        print(f"❌ ไม่พบไฟล์: {STOCK_DATA_FILE}")
        return {}
    except Exception as e:
        print(f"❌ โหลดไฟล์ Excel ล้มเหลว: {e}")
        return {}

    try:
        if 'Ticker' not in df.columns or 'Company Name' not in df.columns:
            print(f"❌ ไฟล์ Excel ไม่มีคอลัมน์ 'Ticker' หรือ 'Company Name' กรุณาตรวจสอบไฟล์")
            print(f"คอลัมน์ที่พบ: {df.columns.tolist()}")
            return {}

        for _, row in df.iterrows():
            ticker = str(row['Ticker']).strip().upper()
            company_name = str(row['Company Name']).strip().upper()
            
            # **เพิ่ม:** กรอง Ticker และ Company Name ที่อยู่ใน COMMON_WORDS_TO_EXCLUDE
            # เราเก็บใน map โดยใช้ชื่อบริษัท/ticker เป็น key และ ticker เป็น value
            # ถ้าเป็น ticker ที่สั้นมาก ให้ตรวจสอบละเอียดขึ้นใน detect_stock_names
            if ticker and ticker not in COMMON_WORDS_TO_EXCLUDE:
                stock_map[ticker] = ticker
            if company_name and company_name not in COMMON_WORDS_TO_EXCLUDE:
                stock_map[company_name] = ticker
        print(f"✅ โหลดชื่อหุ้นทั้งหมด {len(stock_map)} รายการจาก {STOCK_DATA_FILE}")
    except KeyError as e:
        print(f"❌ ไม่พบคอลัมน์ที่คาดหวังในไฟล์ Excel: {e}. ตรวจสอบชื่อคอลัมน์ในไฟล์.")
        print(f"คอลัมน์ที่พบ: {df.columns.tolist()}")
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดขณะประมวลผลข้อมูลใน DataFrame: {e}")
    return stock_map

STOCK_NAMES_MAP = load_stock_names()

# --- ระบบตรวจจับชื่อหุ้น (detect_stock_names) ---
def detect_stock_names(text):
    found_tickers = set()
    text_upper = text.upper()
    
    if not STOCK_NAMES_MAP:
        return []
        
    words = re.findall(r'\b[A-Z0-9]+\b', text_upper) # จับเฉพาะคำที่เป็นตัวพิมพ์ใหญ่และตัวเลขติดกัน
    
    # เพิ่มคำที่จะช่วยยืนยันว่าเป็นหุ้น (Contextual keywords)
    # เช่น "AAPL stock", "MSFT shares", "GOOGL Inc."
    context_keywords = ["STOCK", "SHARES", "CORP", "INC", "LTD", "PLC", "HOLDINGS", "GROUP", "COMPANY"]

    for word in words:
        # กรองคำสั้นๆ ที่อาจเป็นคำทั่วไป
        if len(word) < 2 or word in COMMON_WORDS_TO_EXCLUDE:
            continue
        
        # ตรวจสอบว่าเป็น Ticker ที่รู้จัก
        if word in STOCK_NAMES_MAP:
            # เพิ่มการตรวจสอบบริบทสำหรับ Ticker ที่สั้นมาก (เช่น Ticker 2-3 ตัวอักษร)
            # เพื่อลด False Positive กับคำทั่วไปที่บังเอิญตรงกับ Ticker สั้นๆ
            if len(word) <= 3 and word not in COMMON_WORDS_TO_EXCLUDE: # Ticker สั้นๆ
                # ตรวจสอบว่าคำนี้ถูกตามด้วยคำที่บ่งชี้ว่าเป็นหุ้นหรือไม่
                pattern_with_context = r'\b' + re.escape(word) + r'\s+(?:' + '|'.join(context_keywords) + r')\b'
                # ตรวจสอบว่าคำนี้เป็นตัวพิมพ์ใหญ่ทั้งหมด (มักจะเป็น Ticker)
                # หรือถ้าไม่เป็นตัวพิมพ์ใหญ่ทั้งหมด ต้องมีบริบทที่ชัดเจน
                if re.search(pattern_with_context, text_upper) or word.isupper():
                    found_tickers.add(STOCK_NAMES_MAP[word])
            else: # Ticker ที่ยาวกว่า หรือเป็น Company Name ที่มาจาก Excel
                found_tickers.add(STOCK_NAMES_MAP[word])
        
    # ตรวจจับชื่อบริษัท (อาจจะไม่ได้เป็นตัวพิมพ์ใหญ่ทั้งหมดเสมอไปในข่าว)
    # แต่เราจะเน้นการตรวจจับจาก Ticker ที่เป็นตัวพิมพ์ใหญ่เป็นหลักก่อน
    # ส่วนชื่อบริษัท ให้ใช้การค้นหาแบบไม่สนใจ Case แต่ต้องเป็นคำเต็ม
    for company_name, ticker in STOCK_NAMES_MAP.items():
        if len(company_name) > 3 and company_name not in COMMON_WORDS_TO_EXCLUDE: # ตรวจสอบชื่อบริษัทที่ยาวกว่า 3 ตัวอักษร
            # ใช้ re.search เพื่อหาคำเต็ม ไม่สนใจตัวพิมพ์ใหญ่-เล็ก (flags=re.IGNORECASE)
            if re.search(r'\b' + re.escape(company_name) + r'\b', text, flags=re.IGNORECASE):
                found_tickers.add(ticker)
    
    # กรองผลลัพธ์สุดท้ายอีกครั้ง เพื่อให้แน่ใจว่าไม่มี Ticker ที่เป็นคำทั่วไป
    final_tickers = [t for t in list(found_tickers) if t not in COMMON_WORDS_TO_EXCLUDE]
    
    return final_tickers

# **ใหม่:** ฟังก์ชันสำหรับวิเคราะห์ sentiment เบื้องต้น
def analyze_sentiment(text):
    text_upper = text.upper()
    positive_score = sum(1 for keyword in POSITIVE_KEYWORDS if keyword in text_upper)
    negative_score = sum(1 for keyword in NEGATIVE_KEYWORDS if keyword in text_upper)

    if positive_score > negative_score:
        return "📈 แนวโน้มขึ้น"
    elif negative_score > positive_score:
        return "📉 แนวโน้มลง"
    else:
        return "↔️ ไม่ชัดเจน"

# **เพิ่ม:** ฟังก์ชันสำหรับเน้นชื่อหุ้นในข้อความ
def highlight_stocks_in_text(text, detected_tickers):
    if not detected_tickers or not text:
        return text

    # สร้าง Regular Expression pattern สำหรับแต่ละ Ticker
    # เรียงจาก Ticker ที่ยาวที่สุดก่อน เพื่อป้องกันการจับคู่ส่วนหนึ่งของ Ticker ที่ยาวกว่า
    sorted_tickers = sorted(detected_tickers, key=len, reverse=True)
    
    # สร้าง pattern ที่จะจับคู่คำเต็มของ Ticker โดยไม่สนใจตัวพิมพ์เล็ก-ใหญ่
    # และใช้ non-capturing group (?:...) กับ '|' สำหรับ OR
    # ใช้ re.escape เพื่อจัดการ Ticker ที่มีอักขระพิเศษ
    pattern = r'\b(' + '|'.join(re.escape(t) for t in sorted_tickers) + r')\b'
    
    # ฟังก์ชันสำหรับแทนที่: match.group(0) คือคำที่ถูกจับคู่
    # re.sub(pattern, replacement_function, text, flags=re.IGNORECASE)
    def replacer(match):
        # ตรวจสอบว่าเป็น Ticker ที่เรารู้จักจริงหรือไม่ (เพื่อป้องกันการเน้นคำทั่วไปที่บังเอิญตรงกัน)
        matched_word = match.group(0).upper()
        if matched_word in STOCK_NAMES_MAP and matched_word not in COMMON_WORDS_TO_EXCLUDE:
            return f"<b>{match.group(0)}</b>" # เน้นด้วย bold
        return match.group(0) # ถ้าไม่ใช่หุ้นที่เราต้องการเน้น ก็คืนคำเดิมไป

    # ใช้ re.IGNORECASE เพื่อให้จับคู่ได้ทั้งตัวพิมพ์เล็กและตัวพิมพ์ใหญ่
    highlighted_text = re.sub(pattern, replacer, text, flags=re.IGNORECASE)
    
    return highlighted_text

# --- ระบบแปลภาษา ---
def translate_text(text):
    try:
        if len(text) > MAX_NEWS_FULL_TEXT_LENGTH * 2:
            text = text[:MAX_NEWS_FULL_TEXT_LENGTH * 2] + "..."
            print(f"⚠️ ข้อความยาวเกินไป ถูกตัดก่อนแปล. ความยาว: {len(text)} ตัวอักษร")
        return GoogleTranslator(source='auto', target='th').translate(text)
    except Exception as e:
        print(f"⚠️ แปลล้มเหลว: {e}")
        return "(แปลไม่ได้)"

# --- ส่งข้อความ Telegram ---
def send_telegram(title, summary, full_text, post_time):
    formatted_time = post_time.astimezone(timezone(timedelta(hours=7))) \
        .strftime("%Y-%m-%d %H:%M:%S") + " (GMT+7)"

    original_full_text = full_text
    if len(original_full_text) > MAX_NEWS_FULL_TEXT_LENGTH:
        full_text_truncated = original_full_text[:MAX_NEWS_FULL_TEXT_LENGTH] + "\n\n(อ่านต่อ...)"
        print(f"📝 เนื้อหาข่าวเต็มถูกตัดทอน (ต้นฉบับ: {len(original_full_text)}, ตัดเหลือ: {len(full_text_truncated)})")
    else:
        full_text_truncated = original_full_text

    # ตรวจจับหุ้นจากข้อความต้นฉบับเต็ม (Title + Summary + Full Text)
    # เพราะข่าวอาจจะพูดถึงหุ้นในส่วนไหนก็ได้
    detected_stocks = detect_stock_names(f"{title} {summary} {original_full_text}") 
    
    # **ใหม่:** วิเคราะห์ Sentiment จากเนื้อหาข่าว
    overall_sentiment = analyze_sentiment(f"{title} {summary} {original_full_text}")

    # **เพิ่ม:** เน้นชื่อหุ้นในข้อความภาษาอังกฤษ
    title_highlighted = highlight_stocks_in_text(title, detected_stocks)
    summary_highlighted = highlight_stocks_in_text(summary, detected_stocks)
    full_text_highlighted = highlight_stocks_in_text(full_text_truncated, detected_stocks)

    # แปลข้อความที่ "ยังไม่ได้" เน้น (เพื่อไม่ให้ tag HTML ไปรบกวนการแปล)
    title_th = translate_text(title)
    summary_th = translate_text(summary)
    full_text_th = translate_text(full_text_truncated) # ใช้ข้อความที่ตัดทอนแล้วมาแปล

    # **เพิ่ม:** เน้นชื่อหุ้นในข้อความภาษาไทย (ใช้ Ticker เดิมที่ตรวจพบ)
    title_th_highlighted = highlight_stocks_in_text(title_th, detected_stocks)
    summary_th_highlighted = highlight_stocks_in_text(summary_th, detected_stocks)
    full_text_th_highlighted = highlight_stocks_in_text(full_text_th, detected_stocks)


    title_escaped = html.escape(title_highlighted)
    summary_escaped = html.escape(summary_highlighted)
    full_text_escaped = html.escape(full_text_highlighted)
    title_th_escaped = html.escape(title_th_highlighted)
    summary_th_escaped = html.escape(summary_th_highlighted)
    full_text_th_escaped = html.escape(full_text_th_highlighted)

    # **ปรับปรุง:** สร้าง block สรุปหุ้น
    stock_info_block = ""
    if detected_stocks:
        stock_info_block += "📊 **หุ้นที่เกี่ยวข้อง:**\n"
        stock_info_block += "```\n"
        for ticker in detected_stocks:
            stock_info_block += f"- {ticker} ({overall_sentiment})\n"
        stock_info_block += "```\n\n"
    else:
        stock_info_block = "<i>ไม่พบหุ้นที่เกี่ยวข้องในข่าวนี้</i>\n\n"

    message = (
        f"{stock_info_block}"
        f"🕒 <b>{formatted_time}</b>\n"
        f"📰 <b>{title_escaped}</b>\n"
        f"📝 <i>{summary_escaped}</i>\n\n"
        f"{full_text_escaped}\n\n"
        f"🌐 <b>แปลไทย</b> 🇹🇭\n"
        f"<b>{title_th_escaped}</b>\n"
        f"<i>{summary_th_escaped}</i>\n\n"
        f"{full_text_th_escaped}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print(f"✅ ส่งข้อความ Telegram สำเร็จสำหรับ: {title}")
    except requests.exceptions.RequestException as e:
        print(f"❌ ส่งข้อความ Telegram ล้มเหลวสำหรับ '{title}': {e}")
        if response and response.status_code == 400:
            print(f"Telegram API response: {response.text}")


# --- ระบบช่วยอื่น ๆ ---
def load_last_timestamp():
    if os.path.exists(LAST_TIMESTAMP_FILE):
        with open(LAST_TIMESTAMP_FILE, "r") as f:
            try:
                return datetime.fromisoformat(f.read().strip())
            except ValueError:
                return datetime.min.replace(tzinfo=timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)

def save_last_timestamp(ts):
    with open(LAST_TIMESTAMP_FILE, "w") as f:
        f.write(ts.isoformat())

def already_sent(title, post_time):
    if not os.path.exists(SENT_LOG_FILE):
        return False
    key = f"{title}::{post_time.isoformat()}"
    with open(SENT_LOG_FILE, "r", encoding="utf-        8") as f:
        return key in f.read()

def mark_as_sent(title, post_time):
    key = f"{title}::{post_time.isoformat()}"
    with open(SENT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(key + "\n")

def setup_driver():
    options = Options()
    options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
    options.add_argument("--profile-directory=Default")
    # options.add_argument("--headless") # ยังไม่แนะนำให้เปิดถ้ายังแก้ปัญหาได้ไม่ครบ
    options.add_experimental_option("detach", False) # ทำให้ Chrome ปิดเองหลังจบ script
    return webdriver.Chrome(options=options)

# --- ดึงรายละเอียดข่าว ---
def extract_article_details(driver, article_element):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='splitViewBodyTypography']"))
        )

        title_elem = article_element.find_element(By.CSS_SELECTOR, "div[class*='title']")
        title = title_elem.text.strip()

        time_elem = article_element.find_element(By.TAG_NAME, "relative-time")
        raw_time = time_elem.get_attribute("event-time")
        post_time = datetime.strptime(raw_time, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)

        content_blocks = driver.find_elements(By.CSS_SELECTOR, "div[class*='splitViewBodyTypography'] p")
        paragraphs = [p.text.strip() for p in content_blocks if p.text.strip()]
        summary = paragraphs[0] if paragraphs else "(ไม่มีเนื้อหาย่อหน้าแรก)"
        full_text = "\n\n".join(paragraphs) if paragraphs else "(ไม่มีเนื้อหาข่าว)"

        return title, post_time, summary, full_text

    except Exception as e:
        print(f"❌ ดึงข้อมูลข่าวล้มเหลว: {e}")
        return None, None, None, None

# --- MAIN LOOP ---
def main():
    last_timestamp = load_last_timestamp()
    print("\n🔄 เริ่มรอบใหม่")
    print(f"⏱️ last_timestamp ปัจจุบัน: {last_timestamp.isoformat()}")

    driver = setup_driver()
    driver.get(TRADINGVIEW_URL)

    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article[class^='article-']"))
        )

        articles = driver.find_elements(By.CSS_SELECTOR, "article[class^='article-']")
        print(f"📋 พบข่าวทั้งหมด {len(articles)} รายการบนหน้าเว็บ")

        articles_to_process = []
        
        # วนลูปจากข่าวที่ใหม่ที่สุด (อยู่ด้านบนสุดของหน้า)
        for article_element in articles:
            try:
                title_elem = article_element.find_element(By.CSS_SELECTOR, "div[class*='title']")
                time_elem = article_element.find_element(By.TAG_NAME, "relative-time")
                raw_time = time_elem.get_attribute("event-time")
                post_time = datetime.strptime(raw_time, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
                title = title_elem.text.strip()

                if post_time > last_timestamp and not already_sent(title, post_time):
                    articles_to_process.append((article_element, title, post_time))
                else:
                    # ถ้าเจอข่าวที่เก่ากว่า last_timestamp หรือข่าวที่ส่งไปแล้ว
                    print(f"⏩ เจอข่าวเก่าหรือส่งแล้ว: {title} ({post_time.isoformat()})")
                    break # หยุดการประมวลผลข่าวที่เหลือในหน้า
            except Exception as e:
                print(f"⚠️ ข้ามข่าวเนื่องจาก metadata ผิดพลาด: {e}")
                continue
        
        print(f"🧠 เตรียมเปิดข่าวใหม่ทั้งหมด {len(articles_to_process)} รายการ")
        new_latest_ts = last_timestamp

        for article_element, title_from_list, post_time_from_list in articles_to_process:
            try:
                # การหา element ซ้ำและคลิกเพื่อให้มั่นใจว่าจะคลิกถูกตัว
                # เนื่องจาก DOM อาจจะมีการเปลี่ยนแปลงหลังจากที่เราได้ elements มาครั้งแรก
                current_articles = driver.find_elements(By.CSS_SELECTOR, "article[class^='article-']")
                found_and_clicked = False
                for current_art in current_articles:
                    current_title_elem = current_art.find_element(By.CSS_SELECTOR, "div[class*='title']")
                    current_time_elem = current_art.find_element(By.TAG_NAME, "relative-time")
                    current_raw_time = current_time_elem.get_attribute("event-time")
                    current_post_time = datetime.strptime(current_raw_time, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)

                    if current_title_elem.text.strip() == title_from_list and current_post_time == post_time_from_list:
                        current_art.click()
                        found_and_clicked = True
                        break
                
                if not found_and_clicked:
                    print(f"⚠️ ไม่พบข่าว '{title_from_list}' บนหน้าเว็บอีกครั้งหลังจากโหลดใหม่ อาจถูกเลื่อนไป")
                    continue

                time.sleep(2) # ให้เวลาโหลด split view

                title, post_time, summary, full_text = extract_article_details(driver, article_element)
                
                if title and post_time:
                    send_telegram(title, summary, full_text, post_time)
                    mark_as_sent(title, post_time)

                    if post_time > new_latest_ts:
                        new_latest_ts = post_time
                else:
                    print(f"❌ ไม่สามารถดึงรายละเอียดข่าวสำหรับ '{title_from_list}' ได้")

            except Exception as e:
                print(f"❌ เปิดข่าว '{title_from_list}' หรือประมวลผลล้มเหลว: {e}")

        save_last_timestamp(new_latest_ts)
        print(f"✅ อัปเดต last_timestamp เป็น: {new_latest_ts.isoformat()}")

    finally:
        driver.quit()

# --- รันอัตโนมัติทุก 1 นาที ---
if __name__ == "__main__":
    while True:
        main()
        print("\n⏳ รอรอบถัดไป (1 นาที)...")
        time.sleep(60) # เปลี่ยนเป็น 60 วินาที (1 นาที)