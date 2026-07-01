# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
import time
import os
import requests
import gspread
import telebot
import schedule
import threading
import yfinance as yf

# ====== CONFIG ======
TELEGRAM_TOKEN = "7597463823:AAG_jeNnBUUyDtjsk53CbUV37bWgb-OSbsw"
TELEGRAM_CHAT_ID = "6678778888"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1ZfXEsNMBvynGErQa7JvsQtD6dQojaUECRvTU6CqiSls"
CREDENTIALS_FILE = "credentials.json"
# =====================

def get_price_change(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d")
        if len(hist) < 2:
            print(f"{symbol}: No price data found, period=2d returned less than 2 entries.")
            return None
        prev = hist["Close"].iloc[-2]
        latest = hist["Close"].iloc[-1]
        pct_change = ((latest - prev) / prev) * 100
        return f"{latest:.2f} ({pct_change:+.2f}%)"
    except Exception as e:
        print(f"Failed to get ticker '{symbol}' price change: {e}")
        return None

def get_earnings_by_country(driver, country_name, url, scroll_pause=1.0, max_scrolls=25):
    print(f"\U0001F4C5 กำลังดึงข้อมูลงบจาก {country_name}...")
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tr"))
        )
        last_height = driver.execute_script("return document.body.scrollHeight")
        scrolls = 0

        while scrolls < max_scrolls:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            scrolls += 1

        print(f"\U0001F4C9 เลื่อนหน้าจอทั้งหมด {scrolls} ครั้ง")

        rows = driver.find_elements(By.CSS_SELECTOR, "table tr")
        earnings_data = []
        skip_symbols = {"I", "A", "D", "—"}

        for row in rows[1:]:
            try:
                cells = row.find_elements(By.CSS_SELECTOR, "td")
                if len(cells) >= 6:
                    raw_symbol_text = cells[0].text.strip()
                    original_symbol = raw_symbol_text.split('\n')[0].split(' ')[0]
                    if original_symbol in skip_symbols and len(original_symbol) <= 1:
                        continue
                    if not original_symbol:
                        continue

                    display_symbol = original_symbol
                    if display_symbol.endswith('D') and len(display_symbol) > 1:
                        display_symbol = display_symbol[:-1]

                    name = cells[1].text.strip().replace(" D", "").replace(" D)", ")")
                    eps_estimate = cells[3].text.strip()
                    eps_reported = cells[4].text.strip()
                    eps_surprise = cells[5].text.strip()

                    if original_symbol and name:
                        earnings_data.append((original_symbol, display_symbol, name, eps_estimate, eps_reported, eps_surprise))
            except Exception as e:
                print(f"Error processing row: {e} for row text: {row.text[:100]}")
                continue

        print(f"✅ ดึง {country_name}: พบ {len(earnings_data)} ตัว")
        return earnings_data
    except Exception as e:
        print(f"❌ ดึงข้อมูลล้มเหลว ({country_name}): {e}")
        return []

def send_telegram_message(msg):
    max_length = 4096
    parts = [msg[i:i+max_length] for i in range(0, len(msg), max_length)]
    for part in parts:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": part, "parse_mode": "HTML"}
        )
        print(f"\U0001F4E8 ส่ง Telegram: {response.status_code} {response.text}")
        time.sleep(1)

def log_to_sheet(msg):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SPREADSHEET_URL).sheet1

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        sheet.append_row(["หุ้นประกาศงบย้อนหลัง", date_str, time_str, msg])
        print("✅ บันทึกลง Google Sheet")
    except Exception as e:
        print(f"❌ บันทึก Google Sheet ล้มเหลว: {e}")

def fetch_and_send_earnings():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    earnings_urls = {
        "\U0001F1F9\U0001F1ED ไทย": "https://www.tradingview.com/markets/stocks-thailand/earnings/",
        "\U0001F1FA\U0001F1F8 อเมริกา": "https://www.tradingview.com/markets/stocks-usa/earnings/",
        "\U0001F1ED\U0001F1F0 ฮ่องกง": "https://www.tradingview.com/markets/stocks-hong-kong/earnings/",
    }

    all_earnings = {}
    for country, url in earnings_urls.items():
        symbols_data = get_earnings_by_country(driver, country, url)
        if symbols_data:
            all_earnings[country] = symbols_data

    driver.quit()

    if not any(all_earnings.values()):
        print("ℹ️ ไม่พบข้อมูลหุ้นประกาศงบในวันนี้สำหรับประเทศใดๆ")
        return

    msg_header = "\U0001F4C3 <b>หุ้นประกาศงบวันนี้</b>"
    full_msg = msg_header
    all_text_log = ""

    for country, items in all_earnings.items():
        if not items:
            continue
        msg_section = f"\n\n{country}\n"
        for original_sym, display_sym, name, est, reported, surprise in items:
            price_info = get_price_change(original_sym)
            price_text = f"\n• ราคา: {price_info}" if price_info else ""
            entry_for_telegram = (
                f"\n<b>{display_sym}</b> - {name}"
                f"\nคาดการณ์ EPS: <code>{est}</code>"
                f"\nรายงาน EPS: <code>{reported}</code>"
                f"\nต่างจากที่คาด: <code>{surprise}</code>"
                f"{price_text}"
            )
            msg_section += entry_for_telegram
            entry_for_log = f"{original_sym} {name}, EPS คาด: {est}, รายงาน: {reported}, ต่าง: {surprise} | ราคา: {price_info or '-'}\n"
            all_text_log += entry_for_log

        if len(full_msg + msg_section) >= 4000:
            send_telegram_message(full_msg)
            full_msg = msg_header + msg_section
        else:
            full_msg += msg_section

    if full_msg.strip() != msg_header.strip():
        send_telegram_message(full_msg)
    if all_text_log:
        log_to_sheet(all_text_log.strip())

# ===== Telegram Bot Setup =====
bot = telebot.TeleBot(TELEGRAM_TOKEN)

@bot.message_handler(commands=['search'])
def search_command(message):
    keyword = message.text.replace('/search', '').strip().lower()
    if not keyword:
        bot.reply_to(message, "กรุณาพิมพ์ชื่อหุ้นหรือคำที่ต้องการค้นหา เช่น\n`/search SCB` หรือ `/search น้ำมัน`", parse_mode="Markdown")
        return
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SPREADSHEET_URL).sheet1
        data = sheet.get_all_values()[1:]

        matched = []
        for row in reversed(data):
            if len(row) >= 4:
                _, date, time_sent, text = row
                combined = f"{date} {time_sent} {text}".lower()
                if keyword in combined:
                    matched.append(f"{date} {time_sent}\n{text}")
                if len(matched) >= 5:
                    break

        if matched:
            bot.reply_to(message, "\n\n".join(matched))
        else:
            bot.reply_to(message, "\U0001F50D ไม่พบข้อมูลที่ค้นหา")
    except Exception as e:
        bot.reply_to(message, f"❌ เกิดข้อผิดพลาด: {e}")

def run_bot():
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error during polling: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred during polling: {e}. Retrying in 5 seconds...")
            time.sleep(5)

def run_scheduler():
    schedule.every().day.at("08:00").do(fetch_and_send_earnings)
    schedule.every().day.at("18:00").do(fetch_and_send_earnings)
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    fetch_and_send_earnings()
    threading.Thread(target=run_scheduler).start()
    run_bot()
