import pandas as pd
import numpy as np

def calculate_rsi(df, periods=14):
    close_delta = df['Close'].diff()
    up = close_delta.clip(lower=0)
    down = -1 * close_delta.clip(upper=0)
    
    ma_up = up.rolling(window=periods, min_periods=1).mean()
    ma_down = down.rolling(window=periods, min_periods=1).mean()
    
    rsi = ma_up / ma_down
    rsi = 100 - (100 / (1 + rsi))
    return rsi

def apply_inverse_strategy(df):
    """
    코스피 지수(KS11) 데이터를 받아 인버스(114800) 매수 시그널을 계산합니다.
    """
    df = df.copy()
    
    # 1. 보조지표 계산
    df['RSI'] = calculate_rsi(df, 14)
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    
    # 2. 전일 종가 데이터
    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev_RSI'] = df['RSI'].shift(1)
    
    # 3. 매수(인버스 진입) 시그널 로직
    # 조건 A: 극과매수(RSI 75 이상) 상태에서 음봉 또는 하락 마감하며 꺾일 때 (고점 징후)
    cond_overbought_reversal = (df['Prev_RSI'] >= 75) & (df['Close'] < df['Prev_Close'])
    
    # 조건 B: 강력한 지지선인 60일선(수급선)을 갭 하락 또는 장대음봉으로 하향 이탈할 때 (추세 붕괴)
    cond_trend_breakdown = (df['Prev_Close'] > df['MA60']) & (df['Close'] < df['MA60'])
    
    # 조건 C: 20일선(생명선) 데드크로스 발생 시
    cond_20ma_breakdown = (df['Prev_Close'] > df['MA20']) & (df['Close'] < df['MA20'])
    
    df['Inverse_Buy_Signal'] = cond_overbought_reversal | cond_trend_breakdown | cond_20ma_breakdown
    
    return df
