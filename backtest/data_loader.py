import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os

def get_kosdaq_list():
    """코스닥 상장 종목 리스트를 반환합니다."""
    df_kosdaq = fdr.StockListing('KOSDAQ')
    return df_kosdaq

def get_theme_stocks():
    """themes 폴더 내의 모든 CSV 파일에서 종목 리스트를 통합하여 반환합니다."""
    theme_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'themes')
    all_stocks = []
    
    if not os.path.exists(theme_dir):
        return pd.DataFrame()
        
    for file in os.listdir(theme_dir):
        if file.endswith('.csv'):
            df = pd.read_csv(os.path.join(theme_dir, file), dtype={'Code': str})
            df['Code'] = df['Code'].apply(lambda x: str(x).zfill(6))
            all_stocks.append(df)
            
    if all_stocks:
        combined = pd.concat(all_stocks, ignore_index=True)
        # 중복 종목 제거 (테마 간 교집합이 있을 수 있음)
        return combined.drop_duplicates(subset=['Code'])
    
    return pd.DataFrame()

def get_daily_data(stock_code, start_date, end_date):
    """특정 종목의 일봉 데이터를 가져옵니다."""
    stock_code = str(stock_code).zfill(6)
    df = fdr.DataReader(stock_code, start_date, end_date)
    return df
