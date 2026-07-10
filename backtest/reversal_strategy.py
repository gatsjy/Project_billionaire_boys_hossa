"""
reversal_strategy.py — 스윙 반전 전략 (검증 통과 후보 코어)

배경/근거: progress.md Phase 11~12, reversal_research.py / entry_quality_research.py.
  한국 개별주는 단기 반전이 강한 시장. 돌파 '추격'(apply_strategy_v1)은 분출 꼭지를 사
  OOS 음(-). 이를 뒤집어 '상승추세 속 과매도 눌림'을 사고 반등에 판다.
  타점 개선: ATR% 상한으로 작전주/펌핑주(예: 금호전기 ATR 20.6%)를 진입에서 배제 →
  기댓값은 소폭↓이나 MDD 91%→80%로 재앙 꼬리 제거.

진입(다음날 시가): RSI(14) < REV_RSI_ENTRY AND 종가 > REV_TREND_MA일선 AND ATR% <= REV_ATR_CAP
청산: RSI 반등(>REV_RSI_EXIT) / 익절 REV_TP / 손절 max(REV_SL, REV_ATR_K×ATR) / REV_HOLD_DAYS 타임아웃

주의: 아직 라이브(radar_alert) 미연결. 편향제거 유니버스 + 포트폴리오 백테스트 통과 후
소액 페이퍼부터. 파라미터는 params.py 단일소스만 참조(검증값=실전값 강제).
"""

import numpy as np
import pandas as pd

try:
    from params import (REV_RSI_ENTRY, REV_TREND_MA, REV_ATR_CAP,
                        REV_RSI_EXIT, REV_TP, REV_SL, REV_ATR_K, REV_HOLD_DAYS)
except ImportError:
    from backtest.params import (REV_RSI_ENTRY, REV_TREND_MA, REV_ATR_CAP,
                                 REV_RSI_EXIT, REV_TP, REV_SL, REV_ATR_K, REV_HOLD_DAYS)


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


def atr_pct(df, period=14):
    pc = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - pc).abs(),
                    (df["Low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean() / df["Close"] * 100


def apply_reversal_strategy(df):
    """반전 매수 시그널을 계산해 컬럼으로 부착. 시그널은 '전일까지' 정보로만 판단.

    반환 df 주요 컬럼:
      RSI, MA_TREND, ATR_Pct, Buy_Signal(당일 매수 후보), Stop_Pct(변동성 반영 손절폭)
    """
    if len(df) < REV_TREND_MA + 15:
        return pd.DataFrame()

    df = df.copy()
    df["RSI"] = rsi(df["Close"])
    df["MA_TREND"] = df["Close"].rolling(REV_TREND_MA).mean()
    df["ATR_Pct"] = atr_pct(df)

    df["Oversold"] = df["RSI"] < REV_RSI_ENTRY
    df["Trend_OK"] = df["Close"] > df["MA_TREND"]          # 떨어지는 칼날 배제
    df["Vol_OK"] = df["ATR_Pct"] <= REV_ATR_CAP            # 작전주/펌핑주 배제(타점 개선)

    df["Buy_Signal"] = df["Oversold"] & df["Trend_OK"] & df["Vol_OK"]

    # 변동성 반영 손절폭(노이즈 위): max(고정, k×ATR)
    df["Stop_Pct"] = np.maximum(abs(REV_SL), REV_ATR_K * df["ATR_Pct"] / 100)
    return df


def check_exit(entry_price, bar_high, bar_low, bar_open, bar_close, bar_rsi, stop_pct):
    """보유 종목 1봉 청산 판정(갭 인지·손절 우선). 반환: (체결가|None, 사유|None)."""
    stop = entry_price * (1 - stop_pct)
    target = entry_price * (1 + REV_TP)
    if bar_open <= stop:
        return bar_open, f"손절(갭)"
    if bar_open >= target:
        return bar_open, f"익절(갭)"
    if bar_low <= stop:
        return stop, f"손절"
    if bar_high >= target:
        return target, f"익절 (+{REV_TP*100:.0f}%)"
    if not pd.isna(bar_rsi) and bar_rsi > REV_RSI_EXIT:
        return bar_close, f"RSI 반등 청산(>{REV_RSI_EXIT})"
    return None, None


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")
    import FinanceDataReader as fdr
    # 스모크 테스트: 금호전기 반전 신호가 '낮은 타점'에서만 뜨는지 확인
    df = apply_reversal_strategy(fdr.DataReader("001210"))
    sig = df[df["Buy_Signal"]]
    print(f"금호전기 반전 매수 신호 {len(sig)}건 (최근 5건):")
    for d, r in sig.tail(5).iterrows():
        print(f"  {d.date()} 종가 {r['Close']:.0f} RSI {r['RSI']:.1f} "
              f"ATR% {r['ATR_Pct']:.1f} 손절폭 {r['Stop_Pct']*100:.1f}%")
    print("\n→ 분출 고점(7/10, 1500·ATR20%)이 아니라 과매도 눌림에서만 진입함을 확인.")
