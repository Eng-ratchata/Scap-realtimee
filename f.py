import requests
import pandas as pd
import time

def fetch_us_stocks_with_full_name(url="https://scanner.tradingview.com/america/scan"):
    """
    ดึงข้อมูลหุ้นในตลาดอเมริกา พร้อม Ticker, ชื่อเต็ม (Company Name), และประเทศ.
    พยายามดึงชื่อเต็มจากฟิลด์ 'description' หรือ 'name' ที่เหมาะสม.
    จะดึงได้สูงสุดประมาณ 5000 รายการต่อการเรียกใช้ API นี้ (ไม่รองรับ offset จริงจัง).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": "https://www.tradingview.com/",
        "Origin": "https://www.tradingview.com"
    }

    # เพิ่ม 'description' และ 'name' เข้าไปใน columns
    # 'description' มักจะเป็นชื่อเต็ม ในขณะที่ 'name' อาจเป็นชื่อย่อหรือชื่อเต็มสั้นๆ
    # เราจะลองดึง 'description' ก่อน
    payload = {
        "symbols": {
            "query": {"hl":True},
            "tickers": []
        },
        "columns": [
            "name",            # ชื่อย่อหรือชื่อสั้น
            "description",     # ชื่อเต็มบริษัท (น่าจะอยู่ในนี้)
            "country",         # ประเทศ
            "logoid",
            "exchange",
            "industry",
            "market_cap_basic",
            "volume",
            "change",
            "change_abs",
            "sector",
            "type",
        ],
        "options": {
            "lang": "en"
        },
        "range": [0, 5000],  # ดึง 5000 รายการแรกต่อครั้ง
        "sort": {
            "sortBy": "market_cap_basic",
            "sortOrder": "desc"
        },
        "markets": ["america"]
    }

    all_stocks = []
    # เราจะลองดึงเพียงครั้งเดียวสำหรับ "america" เนื่องจาก API ไม่รองรับ offset ได้ดีนัก
    # ถ้าต้องการมากกว่า 5000 ต้องใช้เทคนิคอื่น (เช่นเปลี่ยน markets หรือ filters)

    try:
        print(f"  กำลังดึงข้อมูลหุ้นในตลาดอเมริกา (ครั้งเดียว สูงสุด {payload['range'][1]} รายการ)...")
        response = requests.post(url, headers=headers, json=payload, timeout=60) # เพิ่ม timeout
        response.raise_for_status()
        data = response.json()

        if not data or not data.get('data'):
            print("  ไม่มีข้อมูลหุ้นที่ได้รับ.")
            return []

        for item in data['data']:
            pro_info = item.get('s', '').split(':')
            ticker = pro_info[1] if len(pro_info) > 1 else pro_info[0] # แยก ticker
            
            company_name = None
            country = None

            # พยายามดึงชื่อเต็มจาก 'description' ก่อน
            try:
                desc_index = payload['columns'].index('description')
                company_name = item['d'][desc_index]
                # ตรวจสอบว่าชื่อที่ได้ไม่ใช่ Ticker เอง (เช่น AAPL)
                if company_name and company_name.upper() == ticker.upper():
                    company_name = None # ถ้าเหมือน Ticker ให้ลองหาจาก name แทน
            except (ValueError, IndexError):
                company_name = None # ถ้าไม่มี description

            # ถ้า description ไม่ได้ชื่อเต็มที่ต้องการ หรือไม่มี ให้ลองจาก 'name'
            if not company_name or company_name == "N/A":
                try:
                    name_index = payload['columns'].index('name')
                    company_name = item['d'][name_index]
                except (ValueError, IndexError):
                    company_name = "N/A" # ถ้าหาไม่เจอจริงๆ

            # ดึงประเทศ
            try:
                country_index = payload['columns'].index('country')
                country = item['d'][country_index]
            except (ValueError, IndexError):
                country = "USA" # สมมติว่าเป็น USA สำหรับตลาด America หากไม่พบข้อมูลประเทศ

            all_stocks.append({
                "Ticker": ticker,
                "Company Name": company_name,
                "Country": country
            })
        
        print(f"  ดึงข้อมูลได้ {len(all_stocks)} รายการ.")
        return all_stocks

    except requests.exceptions.HTTPError as e:
        print(f"  เกิดข้อผิดพลาด HTTP ({e.response.status_code}): {e.response.text}")
        print("  โปรดตรวจสอบ URL และ Payload หรือลองอีกครั้งในภายหลัง.")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  เกิดข้อผิดพลาดในการร้องขอ: {e}")
        print("  โปรดตรวจสอบการเชื่อมต่ออินเทอร์เน็ต.")
        return []
    except ValueError as e:
        print(f"  เกิดข้อผิดพลาดในการแปลง JSON: {e}")
        print("  โครงสร้างข้อมูลที่ได้รับอาจเปลี่ยนแปลงไป.")
        return []

if __name__ == "__main__":
    print("กำลังเริ่มต้นดึงข้อมูลหุ้นจาก TradingView Scanner API...")
    stocks_data = fetch_us_stocks_with_full_name()

    if stocks_data:
        df = pd.DataFrame(stocks_data)
        output_file = "tradingview_us_stocks_with_full_name.xlsx"
        df.to_excel(output_file, index=False)
        print(f"\nบันทึกข้อมูลหุ้นทั้งหมด {len(df)} รายการ ลงในไฟล์ '{output_file}' เรียบร้อยแล้ว")
    else:
        print("\nไม่พบข้อมูลหุ้นที่จะบันทึก.")