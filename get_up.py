import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import requests_cache # เพิ่ม library นี้

# เปิดใช้งาน cache สำหรับ requests
# จะเก็บผลลลัพธ์ของ HTTP requests ไว้ในไฟล์ 'yfinance_cache.sqlite'
# และจะหมดอายุหลังจาก 1 ชั่วโมง (3600 วินาที)
# การใช้ cache ช่วยลดการเรียก API ซ้ำๆ และลดโอกาสเจอ Rate Limit
requests_cache.install_cache('yfinance_cache', expire_after=3600) 

def get_sp500_tickers():
    """
    ดึงรายชื่อ Ticker Symbols ของบริษัทในดัชนี S&P 500 จาก Wikipedia.
    ปรับปรุงเพื่อดึง Ticker จากคอลัมน์ 'Symbol' และกรองข้อมูลที่ไม่ใช่ Ticker.
    """
    print("กำลังดึงรายชื่อ Ticker S&P 500 จาก Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        table = soup.find('table', {'class': 'wikitable sortable'}) 
        
        tickers = []
        if table:
            headers = [th.text.strip() for th in table.find_all('th')]
            symbol_col_index = -1
            try:
                # พยายามหาคอลัมน์ที่มีหัวข้อเป็น 'Symbol' หรือ 'Ticker'
                symbol_col_index = headers.index('Symbol')
            except ValueError:
                try:
                    symbol_col_index = headers.index('Ticker')
                except ValueError:
                    print("  คำเตือน: ไม่พบคอลัมน์ 'Symbol' หรือ 'Ticker' ในตาราง. จะพยายามใช้คอลัมน์แรก.")
                    symbol_col_index = 0 # Fallback to first column

            rows = table.find_all('tr')[1:] # ข้ามแถว header
            for i, row in enumerate(rows):
                cols = row.find_all('td')
                if len(cols) > symbol_col_index:
                    ticker = cols[symbol_col_index].text.strip()
                    # กรอง Ticker ที่ไม่ถูกต้อง: ต้องเป็นตัวอักษรพิมพ์ใหญ่, ไม่มีช่องว่าง
                    # และไม่เป็นวันที่หรือตัวเลขล้วนๆ
                    if ticker and all(char.isalnum() or char in ['.', '-', '_'] for char in ticker) and \
                       not ticker.isdigit() and not (len(ticker) > 4 and ticker[0].isdigit()): # กรองวันที่/ตัวเลขยาวๆ
                        
                        # แปลง Ticker สำหรับ yfinance (เช่น BRK.B -> BRK-B)
                        ticker = ticker.replace('.', '-')
                        tickers.append(ticker)
                    else:
                        print(f"    คำเตือน: ข้ามแถวที่ {i+1} เพราะ Ticker '{ticker}' ดูไม่ถูกต้อง.")
        
        print(f"  ดึงได้ {len(tickers)} Ticker จาก S&P 500.")
        return tickers
    except requests.exceptions.RequestException as e:
        print(f"  เกิดข้อผิดพลาดในการดึง Ticker จาก Wikipedia: {e}")
        return []
    except Exception as e:
        print(f"  เกิดข้อผิดพลาดที่ไม่คาดคิดในการ Scraping Ticker: {e}")
        return []

def get_stock_info_yfinance(tickers):
    """
    ดึงข้อมูลหุ้น (ชื่อบริษัท, ประเทศ) จาก Yahoo Finance โดยใช้ yfinance.
    ปรับปรุงการหน่วงเวลาและจัดการข้อผิดพลาด 429.
    """
    all_stocks_data = []
    processed_tickers = set() # ใช้ set เพื่อหลีกเลี่ยงหุ้นซ้ำ
    print("\n--- กำลังดึงข้อมูลหุ้นจาก Yahoo Finance ---")
    
    # yfinance สามารถดึงข้อมูลหลาย Ticker พร้อมกันได้ แต่ถ้ามีมากไปอาจมีปัญหา
    # เราจะแบ่งเป็น batch เล็กๆ เพื่อจัดการข้อจำกัด
    batch_size = 20 # ลด batch size ลงอีก
    
    for i in range(0, len(tickers), batch_size):
        batch_tickers = tickers[i:i + batch_size]
        # กรอง Ticker ว่างเปล่าหรือที่ซ้ำใน batch ออกก่อนส่งให้ yfinance
        batch_tickers = [t for t in batch_tickers if t and t not in processed_tickers]

        if not batch_tickers:
            continue # ข้าม batch ว่างเปล่า

        print(f"  กำลังดึงข้อมูลสำหรับ Batch: {batch_tickers[0]} to {batch_tickers[-1]} (Tickers: {len(batch_tickers)})...")
        
        for ticker_symbol in batch_tickers:
            if ticker_symbol in processed_tickers:
                continue # ข้าม ticker ที่เคยประมวลผลแล้ว (ป้องกันซ้ำภายในรอบ for)
            
            try:
                stock = yf.Ticker(ticker_symbol)
                # ดึง info โดยตรง
                info = stock.info
                
                company_name = info.get('longName', info.get('shortName', 'N/A'))
                country = info.get('country', 'N/A')
                market_cap = info.get('marketCap')
                pe_ratio = info.get('trailingPE')
                
                all_stocks_data.append({
                    "Ticker": ticker_symbol,
                    "Company Name": company_name,
                    "Country": country,
                    "Market Cap (USD)": market_cap,
                    "P/E Ratio": pe_ratio
                })
                processed_tickers.add(ticker_symbol)
                print(f"    ดึงข้อมูล {ticker_symbol} สำเร็จ.")
                time.sleep(0.1) # หน่วงเวลาเล็กน้อยระหว่างแต่ละ Ticker ใน batch
                                 # (เพิ่มเป็น 0.1 จาก 0.05)

            except Exception as e:
                # ตรวจสอบว่าเป็น 429 หรือไม่
                if "429 Client Error" in str(e) or "failed with url" in str(e): # yfinance error messages can vary
                    print(f"    [429 RATE LIMIT] หยุดชั่วคราว 90 วินาที... (Ticker: {ticker_symbol})")
                    time.sleep(90) # หน่วงนานขึ้น (90 วินาที) เมื่อเจอ 429
                    # ลองดึง Ticker นี้อีกครั้ง
                    try:
                        stock = yf.Ticker(ticker_symbol)
                        info = stock.info
                        company_name = info.get('longName', info.get('shortName', 'N/A'))
                        country = info.get('country', 'N/A')
                        market_cap = info.get('marketCap')
                        pe_ratio = info.get('trailingPE')
                        all_stocks_data.append({
                            "Ticker": ticker_symbol,
                            "Company Name": company_name,
                            "Country": country,
                            "Market Cap (USD)": market_cap,
                            "P/E Ratio": pe_ratio
                        })
                        processed_tickers.add(ticker_symbol)
                        print(f"    ดึงข้อมูล {ticker_symbol} สำเร็จ (หลังรอ).")
                        time.sleep(0.1) # หน่วงอีกครั้งหลังดึงสำเร็จ
                    except Exception as e_retry:
                        print(f"    [RETRY FAILED] ข้อผิดพลาดในการดึงข้อมูล {ticker_symbol} แม้จะรอแล้ว: {e_retry}")
                        all_stocks_data.append({
                            "Ticker": ticker_symbol,
                            "Company Name": "ERROR (Retry Failed)",
                            "Country": "ERROR",
                            "Market Cap (USD)": None,
                            "P/E Ratio": None
                        })
                else:
                    print(f"    ข้อผิดพลาดในการดึงข้อมูล {ticker_symbol}: {e}")
                    all_stocks_data.append({
                        "Ticker": ticker_symbol,
                        "Company Name": "ERROR",
                        "Country": "ERROR",
                        "Market Cap (USD)": None,
                        "P/E Ratio": None
                    })
        
        time.sleep(10) # หน่วงเวลาระหว่าง batch ให้มากขึ้น (10 วินาที)

    return all_stocks_data

if __name__ == "__main__":
    sp500_tickers = get_sp500_tickers()

    if sp500_tickers:
        stocks_info = get_stock_info_yfinance(sp500_tickers)

        if stocks_info:
            df = pd.DataFrame(stocks_info)
            df_final = df.drop_duplicates(subset=['Ticker']).reset_index(drop=True)
            
            df_final['Market Cap (USD)'] = pd.to_numeric(df_final['Market Cap (USD)'], errors='coerce')
            df_final = df_final.sort_values(by='Market Cap (USD)', ascending=False).reset_index(drop=True)
            
            output_file = "yahoo_finance_sp500_stocks.xlsx"
            df_final.to_excel(output_file, index=False)
            print(f"\nบันทึกข้อมูลหุ้นทั้งหมด {len(df_final)} รายการ ลงในไฟล์ '{output_file}' เรียบร้อยแล้ว.")
        else:
            print("\nไม่พบข้อมูลหุ้นที่จะบันทึกหลังจากดึงจาก Yahoo Finance.")
    else:
        print("\nไม่สามารถดึงรายชื่อ Ticker S&P 500 ได้. ไม่สามารถดำเนินการต่อได้.")