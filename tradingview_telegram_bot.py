from selenium import webdriver
from selenium.webdriver.common.by import By
from telegram import Bot
import undetected_chromedriver as uc
from datetime import datetime
import pytz
import time

# ======= CONFIG =======

TELEGRAM_TOKEN = "7597463823:AAG_jeNnBUUyDtjsk53CbUV37bWgb-OSbsw"
TELEGRAM_CHAT_ID = "6678778888"

# ======= TELEGRAM UTILS =======
def send_telegram_message(message: str):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='HTML')
    except Exception as e:
        print(f"❗ ส่ง Telegram ล้มเหลว: {e}")

# ======= SCRAPER =======
def setup_driver():
    options = uc.ChromeOptions()
    options.headless = True
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return uc.Chrome(options=options)

def parse_datetime(raw_time):
    try:
        dt = datetime.strptime(raw_time, '%b %d, %Y, %H:%M GMT+7')
        return dt.replace(tzinfo=pytz.timezone('Asia/Bangkok')).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return raw_time

def scrape_news():
    driver = setup_driver()
    driver.get("https://www.tradingview.com/news/")
    time.sleep(5)

    news_data = []
    articles = driver.find_elements(By.CSS_SELECTOR, "a.tv-widget-news__item")

    for i in range(len(articles)):
        try:
            # รีเฟรช element ทุกครั้งเพื่อหลีกเลี่ยง stale element
            articles = driver.find_elements(By.CSS_SELECTOR, "a.tv-widget-news__item")
            article = articles[i]

            title = article.find_element(By.CSS_SELECTOR, ".tv-widget-news__title").text
            url = article.get_attribute("href")
            time_text = article.find_element(By.CSS_SELECTOR, ".tv-widget-news__time").text
            logo = article.find_element(By.CSS_SELECTOR, ".tv-widget-news__icon img").get_attribute("src")
            source = article.find_element(By.CSS_SELECTOR, ".tv-widget-news__source").text

            news_data.append({
                "title": title,
                "url": url,
                "time": parse_datetime(time_text),
                "logo": logo,
                "source": source
            })

        except Exception as e:
            print(f"⏩ ข้ามข่าว {i+1} เนื่องจากปัญหา: {e}")
            continue

    driver.quit()
    return news_data

# ======= MAIN RUN =======
if __name__ == "__main__":
    try:
        all_news = scrape_news()
        print(f"🔍 พบข่าวทั้งหมด {len(all_news)} รายการ\n")

        for idx, news in enumerate(all_news, 1):
            message = (
                f"📰 ข่าว {idx}\n"
                f"🧾 หัวข้อ: {news['title']}\n"
                f"🌐 ลิงก์: {news['url']}\n"
                f"🕒 เวลา: {news['time']}\n"
                f"📡 แหล่งข่าว: {news['source']}\n"
                f"🖼️ โลโก้: {news['logo']}"
            )
            print(message + "\n")
            send_telegram_message(message)
            time.sleep(1)  # เพื่อไม่ให้โดนบล็อกจาก Telegram spam protection

    except Exception as e:
        print(f"❗ เกิดข้อผิดพลาด: {e}")
        send_telegram_message(f"❗เกิดข้อผิดพลาด: {e}")
