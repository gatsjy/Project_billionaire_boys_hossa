import pandas as pd

def apply_strategy_v1(df):
    """
    테마주 돌파 매매 전략 v1.1
    1. 가격 필터 삭제: 대형주/우량주가 포함된 테마이므로 가격 무관
    2. 거래량 급등: 전일 거래량이 과거 20일 평균 거래량 대비 3배 이상 급등
    3. 모멘텀: 전일 대비 시가 갭이 -2% ~ +5% 사이
    """
    if len(df) < 21:
        return pd.DataFrame()

    # 20일 평균 거래량 계산
    df['Volume_MA20'] = df['Volume'].rolling(window=20).mean()
    
    # 1. 거래량 급등 (어제 거래량이 어제 기준 20일 평균 거래량의 3배 이상인지)
    df['Prev_Volume'] = df['Volume'].shift(1)
    df['Prev_Volume_MA20'] = df['Volume_MA20'].shift(1)
    df['Volume_Spike'] = df['Prev_Volume'] >= (df['Prev_Volume_MA20'] * 3)

    # 2. 가격 필터 (조건 삭제 -> 모두 True)
    df['Prev_Close'] = df['Close'].shift(1)
    df['Price_Filter'] = True

    # 3. 갭 필터 (오늘 시가 vs 어제 종가)
    df['Gap_Pct'] = (df['Open'] - df['Prev_Close']) / df['Prev_Close'] * 100
    df['Gap_Filter'] = (df['Gap_Pct'] >= -2) & (df['Gap_Pct'] <= 5)

    # 매수 시그널 (오늘 시가에 매수)
    df['Buy_Signal'] = df['Volume_Spike'] & df['Price_Filter'] & df['Gap_Filter']

    return df
