"""
index_trend_strategy.py — 지수 추세추종 (200일선 ±2% 히스테리시스 밴드)

[Phase 14 채택 근거 — progress.md §9~13]
개별주 전략(테마 돌파·인버스·스윙 반전)이 정직한 검증에서 전부 지수에 패배했다.
유일하게 '절반이라도 통과 + 약세장 방어'가 된 것은 지수 추세추종(kr_trend_research.py):
  KODEX 200 하락시20%: 검증 CAGR 26.4% / MDD -24.9% / Calmar 1.06 (B&H 0.80 대비 낙폭 방어).
이를 라이브 코어로 승격한다.

규칙:
  RISK_ON  : 종가 > 200일선 × (1+BAND)  →  목표비중 W_ON  (기본 100%)
  RISK_OFF : 종가 < 200일선 × (1-BAND)  →  목표비중 W_OFF (기본 20%, 현금 방어)
  밴드 내부: 직전 상태 유지(휩쏘 방지)

상태는 저장하지 않고 매 실행 시 과거 시계열 전체에 히스테리시스를 재생(replay)해 복원 —
결정론적·멱등(재실행해도 같은 답). 파라미터는 params.py 단일소스만 참조.
"""

import pandas as pd
import FinanceDataReader as fdr

try:
    from params import (INDEX_CODE, INDEX_NAME, INDEX_BAND, INDEX_W_ON,
                        INDEX_W_OFF, INDEX_MAX_STALE_DAYS)
except ImportError:
    from backtest.params import (INDEX_CODE, INDEX_NAME, INDEX_BAND, INDEX_W_ON,
                                 INDEX_W_OFF, INDEX_MAX_STALE_DAYS)


def replay_trend_state(close: pd.Series, sma: pd.Series, band: float = INDEX_BAND) -> bool:
    """시계열 전체에 ±밴드 히스테리시스를 재생해 현재 추세 상태를 복원. True=RISK_ON."""
    valid = sma.notna()
    close, sma = close[valid], sma[valid]
    if close.empty:
        raise ValueError("200일선 계산에 필요한 데이터가 부족합니다.")
    state = bool(close.iloc[0] > sma.iloc[0])
    for c, s in zip(close, sma):
        if c > s * (1 + band):
            state = True
        elif c < s * (1 - band):
            state = False
    return state


def _validate(df: pd.DataFrame):
    last_date = df.index[-1]
    stale = (pd.Timestamp.now().normalize() - pd.Timestamp(last_date).normalize()).days
    if stale > INDEX_MAX_STALE_DAYS:
        raise ValueError(f"시세가 {stale}일 전({pd.Timestamp(last_date).date()})에서 멈춰 있습니다.")
    last_close = float(df["Close"].iloc[-1])
    if not (100 < last_close < 1_000_000):
        raise ValueError(f"지수 ETF 종가 이상치: {last_close}")


def get_index_status(code: str = INDEX_CODE):
    """최신 시세로 추세 상태·목표비중·참고지표를 반환. (200일선 재생 위해 2년치 사용)"""
    df = fdr.DataReader(code)  # fdr 는 전체 이력 반환 → 200일선 재생에 충분
    if df.empty or len(df) < 210:
        raise ValueError(f"{code} 데이터 부족(len={len(df)}).")

    df = df.copy()
    df["SMA_200"] = df["Close"].rolling(200).mean()
    _validate(df)

    last_close = float(df["Close"].iloc[-1])
    last_sma = float(df["SMA_200"].iloc[-1])
    disparity = (last_close - last_sma) / last_sma * 100
    risk_on = replay_trend_state(df["Close"], df["SMA_200"])

    if risk_on:
        action, target = "RISK_ON", INDEX_W_ON
        reason = (f"상승 추세 (종가 {last_close:,.0f} > 200일선 {last_sma:,.0f} 밴드 상단). "
                  f"{INDEX_NAME} 비중 {INDEX_W_ON:.0%} 유지.")
    else:
        action, target = "RISK_OFF", INDEX_W_OFF
        reason = (f"하락 추세 (종가 {last_close:,.0f} < 200일선 {last_sma:,.0f} 밴드 하단). "
                  f"{INDEX_NAME} 비중 {INDEX_W_OFF:.0%}로 축소, 현금 방어.")

    return {
        "code": code, "name": INDEX_NAME,
        "price": last_close, "sma_200": last_sma, "disparity": disparity,
        "action": action, "target_weight": target, "reason": reason,
    }


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")
    s = get_index_status()
    for k, v in s.items():
        print(f"  {k}: {v}")
