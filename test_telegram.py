import requests

TELEGRAM_TOKEN = "7597463823:AAG_jeNnBUUyDtjsk53CbUV37bWgb-OSbsw"
TELEGRAM_CHAT_ID = "6678778888"

def send_test_message():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    message = "ทดสอบระบบแจ้งเตือน!"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, data=payload)
        print(f"📡 Status code: {response.status_code}")
        print(f"📨 Response: {response.json()}")
    except Exception as e:
        print(f"เกิดข้อผิดพลาด: {e}")

send_test_message()
