import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

def scrape_naver_finance(url, theme_name):
    res = requests.get(url)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    stocks = []
    # 네이버 금융 거래상위 테이블
    for row in soup.select('table.type_2 tr'):
        a_tag = row.select_one('a.tltle')
        if a_tag:
            name = a_tag.text.strip()
            href = a_tag['href']
            code = href.split('code=')[-1].zfill(6)
            
            # KODEX, TIGER 등 ETF 제외 (순수 주식만 스캔)
            if 'KODEX' in name or 'TIGER' in name or 'KBSTAR' in name or 'ETN' in name or 'KOSEF' in name or 'RISE' in name:
                continue
            if '인버스' in name or '레버리지' in name:
                continue
                
            stocks.append({'Name': name, 'Code': code, 'Theme': theme_name})
            if len(stocks) >= 100:
                break
    return stocks

def update_dynamic_universe():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 동적 유니버스 생성 시작...")
    
    # 1. KOSPI 거래상위
    url_kospi_vol = "https://finance.naver.com/sise/sise_quant.naver"
    kospi_vol = scrape_naver_finance(url_kospi_vol, 'Dynamic_KOSPI_Vol')
    
    # 2. KOSDAQ 거래상위
    url_kosdaq_vol = "https://finance.naver.com/sise/sise_quant.naver?sosok=1"
    kosdaq_vol = scrape_naver_finance(url_kosdaq_vol, 'Dynamic_KOSDAQ_Vol')
    
    # 3. KOSPI 거래량 급증
    url_kospi_surge = "https://finance.naver.com/sise/sise_quant_high.naver"
    kospi_surge = scrape_naver_finance(url_kospi_surge, 'Dynamic_KOSPI_Surge')
    
    # 4. KOSDAQ 거래량 급증
    url_kosdaq_surge = "https://finance.naver.com/sise/sise_quant_high.naver?sosok=1"
    kosdaq_surge = scrape_naver_finance(url_kosdaq_surge, 'Dynamic_KOSDAQ_Surge')
    
    all_stocks = kospi_vol + kosdaq_vol + kospi_surge + kosdaq_surge
    
    df = pd.DataFrame(all_stocks)
    if not df.empty:
        # 중복 제거
        df = df.drop_duplicates(subset=['Code'], keep='first')
        
        # 파일 저장
        theme_dir = os.path.join(os.path.dirname(__file__), 'themes')
        os.makedirs(theme_dir, exist_ok=True)
        save_path = os.path.join(theme_dir, 'dynamic_universe.csv')
        df.to_csv(save_path, index=False, encoding='utf-8')
        
        print(f"동적 유니버스 생성 완료! 총 {len(df)}개 종목이 감시 대상입니다.")
        print(f"저장 위치: {save_path}")
    else:
        print("유니버스 생성 실패: 크롤링된 데이터가 없습니다.")

if __name__ == "__main__":
    update_dynamic_universe()
