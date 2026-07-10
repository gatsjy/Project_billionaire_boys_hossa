"""
kr_trend_research.py — 한국판 코어 전략 검증: KODEX 200/레버리지 × 200일선 추세추종

배경:
  hold_research.py 로 테마주 돌파 진입 계열이 청산 설계와 무관하게 음(-)의 우위임을
  확정했다(분출 고점 매수). 남는 질문은 "그럼 코어를 무엇으로 두는가".
  미국(QLD) 연구에서 훈련/검증 양쪽을 유일하게 통과한 설계가 200일선 ±2% 밴드
  추세추종이었다. 같은 원리가 한국 지수에도 성립하는지 동일한 정직성 기준으로 검증한다.

설계:
  - 대상: KODEX 200 (069500), KODEX 레버리지 (122630)
  - 규칙: 종가 > 200MA×1.02 → 비중 1.0 / 종가 < 200MA×0.98 → 비중 w_off / 밴드 내 유지
  - 비용: 편도 0.115% (ETF 거래세 면제, 수수료 0.015% + 슬리피지 0.1%)
  - 분리: 훈련 ~2019-12-31 / 검증 2020-01-01~ (코로나·2022약세장·2024~는 검증쪽)
  - 지표: CAGR / MDD / Calmar, 기준선은 Buy & Hold

실행: cd backtest && python kr_trend_research.py
"""

import io
import sys

import numpy as np
import pandas as pd
import FinanceDataReader as fdr

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", line_buffering=True)

ONE_WAY_COST = 0.00015 + 0.001   # ETF: 수수료 + 슬리피지 (거래세 면제)
BAND = 0.02
TRAIN_END = "2019-12-31"
TRADING_DAYS = 252

TICKERS = {
    "KODEX 200 (069500)": "069500",
    "KODEX 레버리지 (122630)": "122630",
}


def trend_weights(close: pd.Series, w_off: float, band: float = BAND) -> np.ndarray:
    sma = close.rolling(200).mean()
    w = np.full(len(close), np.nan)
    state = None
    c, s = close.to_numpy(), sma.to_numpy()
    for i in range(len(c)):
        if np.isnan(s[i]):
            continue
        if state is None:
            state = c[i] > s[i]
        if c[i] > s[i] * (1 + band):
            state = True
        elif c[i] < s[i] * (1 - band):
            state = False
        w[i] = 1.0 if state else w_off
    return w


def metrics(nav: np.ndarray) -> dict:
    years = len(nav) / TRADING_DAYS
    cagr = (nav[-1] / nav[0]) ** (1 / years) - 1
    peak = np.maximum.accumulate(nav)
    mdd = ((nav / peak) - 1).min()
    return {"cagr": cagr * 100, "mdd": mdd * 100,
            "calmar": (cagr / abs(mdd)) if mdd < 0 else float("inf")}


def simulate(ret: np.ndarray, weights: np.ndarray) -> np.ndarray:
    w_prev = np.concatenate([[weights[0]], weights[:-1]])
    turnover = np.abs(weights - w_prev)
    port = w_prev * ret - turnover * ONE_WAY_COST
    return np.cumprod(1 + np.nan_to_num(port))


def run():
    for name, code in TICKERS.items():
        df = fdr.DataReader(code)
        close = df["Close"].dropna()
        ret_full = close.pct_change().to_numpy()

        for w_off, label in [(0.0, "하락시 0% (완전현금)"), (0.2, "하락시 20%")]:
            w = trend_weights(close, w_off)
            valid = ~np.isnan(w)
            ret, wgt = ret_full[valid], w[valid]
            idx = close.index[valid]
            is_train = np.asarray(idx <= TRAIN_END)

            nav = simulate(ret, wgt)
            bh = simulate(ret, np.ones(len(ret)))

            m_tr, m_te = metrics(nav[is_train]), metrics(nav[~is_train])
            b_tr, b_te = metrics(bh[is_train]), metrics(bh[~is_train])

            if w_off == 0.0:
                print(f"\n=== {name}  ({idx[0].date()} ~ {idx[-1].date()}) ===")
                print(f"  [B&H 기준선] 훈련 CAGR {b_tr['cagr']:5.1f}% MDD {b_tr['mdd']:6.1f}% Cal {b_tr['calmar']:4.2f}"
                      f" | 검증 CAGR {b_te['cagr']:5.1f}% MDD {b_te['mdd']:6.1f}% Cal {b_te['calmar']:4.2f}")
            print(f"  [추세 {label:<14}] 훈련 CAGR {m_tr['cagr']:5.1f}% MDD {m_tr['mdd']:6.1f}% Cal {m_tr['calmar']:4.2f}"
                  f" | 검증 CAGR {m_te['cagr']:5.1f}% MDD {m_te['mdd']:6.1f}% Cal {m_te['calmar']:4.2f}")


if __name__ == "__main__":
    run()
