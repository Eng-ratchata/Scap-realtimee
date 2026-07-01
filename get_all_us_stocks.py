import requests
import pandas as pd
import time

def get_all_tradingview_stocks(base_url="https://scanner.tradingview.com/"):
    """
    ดึงข้อมูลหุ้นทั้งหมด (Ticker, Company Name, Country) จากตลาดหลักๆ ทั่วโลก
    โดยใช้ TradingView Scanner API. จะพยายามดึงชื่อเต็มและหลีกเลี่ยงหุ้นซ้ำ.
    เนื่องจาก API จำกัดการดึงที่ 5000 รายการต่อคำขอต่อตลาด จึงต้องวนลูปหลายตลาด.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": "https://www.tradingview.com/",
        "Origin": "https://www.tradingview.com"
    }

    payload_template = {
        "symbols": {
            "query": {"hl": True},
            "tickers": []
        },
        "columns": [
            "name",            # ชื่อย่อหรือชื่อสั้น
            "description",     # ชื่อเต็มบริษัท (น่าจะอยู่ในนี้)
            "country",         # ประเทศ
            "logoid",
            "exchange",
            "industry",
            "market_cap_basic", # สำหรับการเรียงลำดับและข้อมูลเพิ่มเติม
            "volume",
            "change",
            "change_abs",
            "sector",
            "type", # ใช้สำหรับกรองหุ้น (stock/share)
            "P_E" # ลองใส่กลับมา บางตลาดอาจมี
        ],
        "options": {
            "lang": "en"
        },
        "range": [0, 5000],  # ดึง 5000 รายการแรกต่อคำขอ (API limit)
        "sort": {
            "sortBy": "market_cap_basic", # เรียงตาม Market Cap เพื่อให้ได้หุ้นใหญ่ก่อน
            "sortOrder": "desc"
        }
    }

    # รายการภูมิภาค/ตลาดหลักที่ TradingView รองรับใน Scanner API
    # ได้เพิ่มประเทศที่คุณระบุมาแล้ว: brazil, canada, china, france, germany, japan, russia, saudi, singapore, south_korea, spain, sweden, switzerland, turkey
    markets_to_scan = [
        "america", "europe", "asia", "africa", "australia", "india", "mena", "uk",
        "brazil", "canada", "china", "france", "germany", "japan", "russia", "saudi",
        "singapore", "south_korea", "spain", "sweden", "switzerland", "turkey"
    ]
    
    all_stocks_collected = []
    processed_tickers = set() # ใช้ set เพื่อติดตาม Ticker ที่ถูกประมวลผลแล้ว (ป้องกันซ้ำข้ามตลาด)

    print("--- กำลังเริ่มต้นดึงข้อมูลหุ้นจากตลาดต่างๆ ทั่วโลก ---")
    total_stocks_count = 0

    for market in markets_to_scan:
        print(f"\n[ตลาด: {market.upper()}] กำลังดึงข้อมูลหุ้น...")
        current_payload = payload_template.copy()
        current_payload["markets"] = [market] # กำหนดตลาดสำหรับ payload นี้
        
        try:
            full_url = f"{base_url}{market}/scan" # สร้าง URL สำหรับแต่ละตลาด
            print(f"  Sending request to: {full_url} with range: {current_payload['range']}")
            response = requests.post(full_url, headers=headers, json=current_payload, timeout=60) # เพิ่ม timeout
            response.raise_for_status() # ตรวจสอบ HTTP errors (เช่น 4xx, 5xx)
            data = response.json()

            current_market_data_count = len(data.get('data', []))
            print(f"  ได้รับข้อมูล {current_market_data_count} รายการในตลาด '{market}'.")

            if not data or current_market_data_count == 0:
                print(f"  [ตลาด: {market.upper()}] ไม่มีข้อมูลหุ้นที่ได้รับ.")
                time.sleep(1) # หน่วงเวลาก่อนไปตลาดถัดไป
                continue

            for item in data['data']:
                pro_info = item.get('s', '').split(':')
                # Ticker อยู่ใน index 1 ถ้ามี exchange (เช่น NASDAQ:AAPL) หรือ index 0 ถ้าไม่มี
                ticker = pro_info[1] if len(pro_info) > 1 else pro_info[0]

                # ข้ามหุ้นที่ซ้ำกัน
                if ticker in processed_tickers:
                    continue 

                company_name = "N/A"
                country = "N/A"
                market_cap = None
                
                # ดึง Company Name: ลองจาก 'description' ก่อน ถ้าไม่ใช่ค่อย 'name'
                try:
                    desc_index = current_payload['columns'].index('description')
                    company_name_from_desc = item['d'][desc_index]
                    # ตรวจสอบว่าชื่อที่ได้จาก description ไม่ใช่ Ticker เอง
                    if company_name_from_desc and company_name_from_desc.upper() != ticker.upper():
                        company_name = company_name_from_desc
                    else:
                        # ถ้า description เหมือน ticker หรือว่าง ให้ลองจาก name
                        name_index = current_payload['columns'].index('name')
                        company_name = item['d'][name_index]
                except (ValueError, IndexError):
                    # ถ้าไม่มี description ให้ลองจาก name
                    try:
                        name_index = current_payload['columns'].index('name')
                        company_name = item['d'][name_index]
                    except (ValueError, IndexError):
                        company_name = "N/A"

                # ดึง Country
                try:
                    country_index = current_payload['columns'].index('country')
                    country = item['d'][country_index]
                except (ValueError, IndexError):
                    country = "N/A" # ถ้าไม่พบ ให้เป็น N/A

                # ดึง Market Cap
                try:
                    market_cap_index = current_payload['columns'].index('market_cap_basic')
                    market_cap = item['d'][market_cap_index]
                except (ValueError, IndexError):
                    market_cap = None # ถ้าไม่พบ ให้เป็น None
                
                # ดึง P/E (ถ้ามีและตลาดรองรับ)
                p_e = None
                try:
                    p_e_index = current_payload['columns'].index('P_E')
                    p_e = item['d'][p_e_index]
                except (ValueError, IndexError):
                    p_e = None


                # กรองเฉพาะหุ้น (type == 'stock' หรือ 'share') หากมีข้อมูล type
                try:
                    type_index = current_payload['columns'].index('type')
                    asset_type = item['d'][type_index]
                    if asset_type not in ['stock', 'share']: 
                        continue # ข้ามถ้าไม่ใช่หุ้น
                except (ValueError, IndexError):
                    pass # ถ้าไม่มีข้อมูล type ก็ไม่ต้องกรอง


                all_stocks_collected.append({
                    "Ticker": ticker,
                    "Company Name": company_name,
                    "Country": country,
                    "Market Cap (Basic)": market_cap,
                    "P/E Ratio": p_e, # เพิ่ม P/E เข้ามา
                    "Market": market # เพื่อให้รู้ว่ามาจากตลาดไหน
                })
                processed_tickers.add(ticker) # เพิ่ม Ticker ที่ประมวลผลแล้ว
                total_stocks_count += 1

            print(f"  [ตลาด: {market.upper()}] จำนวนหุ้นที่ดึงได้ (ไม่ซ้ำ): {len(processed_tickers)}")
            time.sleep(2) # หน่วงเวลาเล็กน้อยระหว่างการดึงแต่ละตลาด

        except requests.exceptions.HTTPError as e:
            error_message = e.response.text if e.response else "No response text"
            print(f"  [ตลาด: {market.upper()}] เกิดข้อผิดพลาด HTTP ({e.response.status_code}): {error_message}")
            if e.response.status_code == 400 and "Unknown field" in error_message:
                print(f"  *** ERROR: มีฟิลด์ที่ไม่รู้จักในตลาดนี้ ({market}). กรุณาตรวจสอบ 'columns' ในโค้ด และลบฟิลด์นั้นออกหากยังพบข้อผิดพลาด. ***")
            print(f"  กำลังข้ามตลาด '{market}' ไป...")
            time.sleep(5) # หน่วงนานขึ้นหากมี error
        except requests.exceptions.RequestException as e:
            print(f"  [ตลาด: {market.upper()}] เกิดข้อผิดพลาดในการร้องขอ: {e}")
            print(f"  กำลังข้ามตลาด '{market}' ไป...")
            time.sleep(5)
        except ValueError as e:
            print(f"  [ตลาด: {market.upper()}] เกิดข้อผิดพลาดในการแปลง JSON: {e}")
            print(f"  โครงสร้างข้อมูลที่ได้รับอาจเปลี่ยนแปลงไปในตลาดนี้.")
            print(f"  กำลังข้ามตลาด '{market}' ไป...")
            time.sleep(5)
        except Exception as e: # จับข้อผิดพลาดทั่วไป
            print(f"  [ตลาด: {market.upper()}] เกิดข้อผิดพลาดที่ไม่คาดคิด: {e}")
            print(f"  กำลังข้ามตลาด '{market}' ไป...")
            time.sleep(5)

    print("\n--- ดึงข้อมูลหุ้นจากทุกตลาดเสร็จสิ้น ---")
    print(f"รวมหุ้นที่ดึงได้ทั้งหมด (ไม่ซ้ำ): {len(processed_tickers)} รายการ")
    return all_stocks_collected

if __name__ == "__main__":
    stocks_data = get_all_tradingview_stocks()

    if stocks_data:
        df = pd.DataFrame(stocks_data)
        # ลบรายการที่ซ้ำกันอีกครั้งใน DataFrame สุดท้าย
        # และจัดเรียงตาม Market Cap จากมากไปน้อย
        df_final = df.drop_duplicates(subset=['Ticker']).sort_values(by='Market Cap (Basic)', ascending=False).reset_index(drop=True)
        
        output_file = "tradingview_all_worlds_stocks.xlsx"
        df_final.to_excel(output_file, index=False)
        print(f"\nบันทึกข้อมูลหุ้นทั้งหมด {len(df_final)} รายการ ลงในไฟล์ '{output_file}' เรียบร้อยแล้ว.")
    else:
        print("\nไม่พบข้อมูลหุ้นที่จะบันทึก.")