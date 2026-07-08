import pandas as pd


def _atr(df, period=14):
    """ATR(평균 실질 변동폭). 변동성 기반 손절/포지션 사이징의 근거."""
    prev_close = df['Close'].shift(1)
    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - prev_close).abs(),
        (df['Low'] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def apply_strategy_v1(df, use_trend_filter=True):
    """
    테마주 돌파 매매 전략 v1.2

    v1.1 → v1.2 변경점 (실전 수익 개선 목적):
      1. [추세 필터 신설] 거래량이 터져도 '하락 추세'면 진입하지 않는다.
         전일 종가가 20일선 위에 있을 때만 매수 → '떨어지는 칼날에 물량 실린' 시그널 제거.
         이것이 -1~-2% 손절이 무의미하게 연속으로 터지던 근본 원인을 줄인다.
      2. [ATR 노출] 종목별 변동성(ATR%)을 계산해 컬럼으로 제공.
         고정 -1% 손절은 종목 노이즈보다 좁아 필연적으로 털린다. 변동성 기반 손절의 근거.
      3. 기존 look-ahead 없음 유지: 시그널은 '전일까지' 정보로만 판단하고 '당일 시가'에 매수.

    주의: 필터/파라미터는 optimizer.py 의 walk-forward(표본외) 검증을 통과해야 실전에 쓴다.
    """
    if len(df) < 21:
        return pd.DataFrame()

    df = df.copy()

    # 20일 평균 거래량
    df['Volume_MA20'] = df['Volume'].rolling(window=20).mean()

    # 이동평균 / 변동성
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['ATR'] = _atr(df, 14)
    df['ATR_Pct'] = df['ATR'] / df['Close'] * 100   # 변동성(%) — 손절폭 산정 근거

    # 1. 거래량 급등: 전일 거래량이 (전일 기준) 20일 평균의 3배 이상
    df['Prev_Volume'] = df['Volume'].shift(1)
    df['Prev_Volume_MA20'] = df['Volume_MA20'].shift(1)
    df['Volume_Spike'] = df['Prev_Volume'] >= (df['Prev_Volume_MA20'] * 3)

    # 2. 갭 필터: 오늘 시가 vs 어제 종가가 -2% ~ +5% (추격/이탈 방지)
    df['Prev_Close'] = df['Close'].shift(1)
    df['Gap_Pct'] = (df['Open'] - df['Prev_Close']) / df['Prev_Close'] * 100
    df['Gap_Filter'] = (df['Gap_Pct'] >= -2) & (df['Gap_Pct'] <= 5)

    # 3. 추세 필터(신설): 전일 종가가 20일선 위 = 상승/눌림 구간에서만 진입
    if use_trend_filter:
        df['Trend_OK'] = df['Prev_Close'] >= df['MA20'].shift(1)
    else:
        df['Trend_OK'] = True

    # 매수 시그널 (당일 시가 매수)
    df['Buy_Signal'] = df['Volume_Spike'] & df['Gap_Filter'] & df['Trend_OK']

    return df
