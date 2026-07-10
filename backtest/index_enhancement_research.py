"""
index_enhancement_research.py — 지수 코어 개선안 검증

현 코어(index_trend_strategy)의 약점과 개선 가설:
  결함1 박스장 휩쏘: 단일 200일선+고정밴드가 횡보장에서 반복 손절.
  결함2 방어현금 0%: RISK_OFF 80% 현금이 무수익 → 한국 단기금리(~2.75%) 버림.
  결함3 단일 파라미터 취약성: 200MA 하나에 전략이 걸림.

개선안:
  A. 방어 현금 → 단기채 수익(연 2.75% 근사)로 캐리 확보.
  B. 다중 이평 앙상블: 120/150/200일선 각각의 밴드상태 평균 → 노출 0.2~1.0 연속화
     (단일 파라미터 취약성·휩쏘 완화, 노출을 부드럽게).

정직성: ETF 비용(거래세 면제, 편도 0.115%) · 훈련(~2019)/검증(2020~) 분리 ·
B&H와 현 코어(V0) 대비. 실행: cd backtest && python index_enhancement_research.py
"""
import io
import sys

import numpy as np
import pandas as pd
import FinanceDataReader as fdr

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", line_buffering=True)

ONE_WAY_COST = 0.00015 + 0.001         # ETF 편도(수수료+슬리피지, 거래세 면제)
RF_ANNUAL = 0.0275                     # 방어 현금 단기채 수익 근사(연)
RF_DAILY = (1 + RF_ANNUAL) ** (1 / 252) - 1
TRAIN_END = "2019-12-31"
BAND = 0.02
W_OFF = 0.2
CODE = "069500"


def band_state(close, sma, band=BAND):
    """±밴드 히스테리시스 상태(1=강세/0=약세) 시계열."""
    c, s = close.to_numpy(), sma.to_numpy()
    out = np.full(len(c), np.nan)
    st = None
    for i in range(len(c)):
        if np.isnan(s[i]):
            continue
        if st is None:
            st = c[i] > s[i]
        if c[i] > s[i] * (1 + band):
            st = True
        elif c[i] < s[i] * (1 - band):
            st = False
        out[i] = 1.0 if st else 0.0
    return out


def weights_single(close):
    sma = close.rolling(200).mean()
    st = band_state(close, sma)
    return np.where(np.isnan(st), np.nan, np.where(st == 1, 1.0, W_OFF))


def weights_ensemble(close, lookbacks=(120, 150, 200)):
    states = []
    for lb in lookbacks:
        states.append(band_state(close, close.rolling(lb).mean()))
    frac = np.nanmean(np.vstack(states), axis=0)     # 강세 이평 비율 0~1
    return W_OFF + (1 - W_OFF) * frac                # 0.2~1.0 연속 노출


def simulate(eq_ret, weights, bond=False):
    valid = ~np.isnan(weights)
    r, w = eq_ret[valid], weights[valid]
    w_prev = np.concatenate([[w[0]], w[:-1]])
    turn = np.abs(w - w_prev)
    cash_ret = RF_DAILY if bond else 0.0
    port = w_prev * r + (1 - w_prev) * cash_ret - turn * ONE_WAY_COST
    return np.cumprod(1 + np.nan_to_num(port)), valid


def metrics(nav):
    yrs = len(nav) / 252
    cagr = (nav[-1] / nav[0]) ** (1 / yrs) - 1
    peak = np.maximum.accumulate(nav)
    mdd = (nav / peak - 1).min()
    return cagr * 100, mdd * 100, (cagr / abs(mdd) if mdd < 0 else float("inf"))


def run():
    close = fdr.DataReader(CODE)["Close"].dropna()
    eq_ret = close.pct_change().to_numpy()

    variants = [
        ("B&H (기준선)", np.ones(len(close)), False),
        ("V0 현코어: 단일200MA, 현금0%", weights_single(close), False),
        ("A  + 방어현금 단기채", weights_single(close), True),
        ("B  앙상블120/150/200, 현금0%", weights_ensemble(close), False),
        ("A+B 앙상블 + 단기채", weights_ensemble(close), True),
    ]

    print(f"KODEX 200 {close.index[0].date()}~{close.index[-1].date()} | "
          f"방어현금 연{RF_ANNUAL:.2%} 가정\n")
    hdr = f"{'설계':<30}{'훈련CAGR':>9}{'훈련MDD':>9}{'훈련Cal':>8} |{'검증CAGR':>9}{'검증MDD':>9}{'검증Cal':>8}"
    print(hdr); print("-" * len(hdr))
    for name, w, bond in variants:
        nav, valid = simulate(eq_ret, w, bond)
        idx = close.index[valid]
        tr = np.asarray(idx <= TRAIN_END)
        c_tr, m_tr, cal_tr = metrics(nav[tr])
        c_te, m_te, cal_te = metrics(nav[~tr])
        print(f"{name:<30}{c_tr:>8.1f}%{m_tr:>8.1f}%{cal_tr:>8.2f} |"
              f"{c_te:>8.1f}%{m_te:>8.1f}%{cal_te:>8.2f}")

    print("\n판정: 개선안이 훈련·검증 '양 구간'에서 V0 대비 Calmar를 높이면 채택.")


if __name__ == "__main__":
    run()
