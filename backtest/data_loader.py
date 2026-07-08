import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta

def get_kosdaq_list():
    """코스닥 상장 종목 리스트를 반환합니다."""
    # FinanceDataReader를 사용하여 한국 거래소 코스닥 종목 리스트 수집
    df_kosdaq = fdr.StockListing('KOSDAQ')
    return df_kosdaq

def get_daily_data(stock_code, start_date, end_date):
    """특정 종목의 일봉 데이터를 가져옵니다."""
    # 종목코드가 6자리가 되도록 패딩
    stock_code = str(stock_code).zfill(6)
    df = fdr.DataReader(stock_code, start_date, end_date)
    return df
