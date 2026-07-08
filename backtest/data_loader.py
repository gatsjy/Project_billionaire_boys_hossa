import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os

def get_kosdaq_list():
    """코스닥 상장 종목 리스트를 반환합니다."""
    df_kosdaq = fdr.StockListing('KOSDAQ')
    return df_kosdaq

def get_theme_stocks(is_backtest=False):
    """
    themes 폴더 내의 CSV 파일에서 종목 리스트를 반환합니다.
    - is_backtest=False: radar_alert.py용. 오직 dynamic_universe.csv만 읽음.
    - is_backtest=True: 기존 백테스트용. 모든 테마 CSV + KRX-DELISTING 추가.
    """
    theme_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'themes')
    all_stocks = []
    
    if not os.path.exists(theme_dir):
        return pd.DataFrame()
        
    for file in os.listdir(theme_dir):
        if not file.endswith('.csv'):
            continue
            
        # 라이브 봇은 dynamic_universe.csv만 읽음
        if not is_backtest and file != 'dynamic_universe.csv':
            continue
            
        theme_name = file.replace('.csv', '').capitalize()
        df = pd.read_csv(os.path.join(theme_dir, file), dtype={'Code': str})
        df['Code'] = df['Code'].apply(lambda x: str(x).zfill(6))
        df['Theme'] = theme_name
        all_stocks.append(df)
        
    # 백테스트 시 상장폐지 종목 강제 편입 (생존자 편향 제거)
    if is_backtest:
        try:
            print("상장폐지 종목(KRX-DELISTING) 50개 무작위 샘플링 편입 중 (생존자 편향 제거)...")
            df_delisted = fdr.StockListing('KRX-DELISTING')
            df_delisted = df_delisted[['Symbol', 'Name']].rename(columns={'Symbol': 'Code'})
            df_delisted['Code'] = df_delisted['Code'].apply(lambda x: str(x).zfill(6))
            df_delisted['Theme'] = 'Delisted_Bias_Free'
            # 전체를 다 돌리면 너무 오래 걸리므로 50개만 무작위 샘플링
            df_delisted = df_delisted.sample(n=50, random_state=42)
            all_stocks.append(df_delisted)
        except Exception as e:
            print(f"상장폐지 종목 편입 실패: {e}")
            
    if all_stocks:
        combined = pd.concat(all_stocks, ignore_index=True)
        # 중복 종목 제거
        return combined.drop_duplicates(subset=['Code'])
    
    return pd.DataFrame()

def get_daily_data(stock_code, start_date, end_date):
    """특정 종목의 일봉 데이터를 가져옵니다."""
    stock_code = str(stock_code).zfill(6)
    try:
        df = fdr.DataReader(stock_code, start_date, end_date)
        return df
    except Exception as e:
        # 야후 파이낸스에 없거나 404 에러가 나는 경우
        return pd.DataFrame()
