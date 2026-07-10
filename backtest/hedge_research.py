"""
hedge_research.py — 방어 슬리브 헷지 자산 검증

배경: 현행 방어 슬리브는 단기채(현금성) — 폭락에서 '쉬지만' 벌지는 못한다. 증시 과열 구간에서
진짜 폭락이 오면 '오르는' 헷지를 방어에 두면 낙폭을 더 줄이고 수익까지 얻을 수 있다.
질문: 한국 증시 폭락 때 실제로 오르는 안전자산은 무엇이며, 방어 슬리브로 채택하면 개선되는가.

방법:
  - 주식 비중 = 이평 앙상블(120/150/200) 밴드 (현행 코어와 동일).
  - 방어 슬리브(1-주식비중)를 후보 자산으로 교체해 전략 전체를 비용반영 백테스트.
  - 후보: 단기채(기준)·미국달러선물·인버스·금선물(H)·국고채10년·(달러50+단기채50 블렌드).
  - 훈련/검증 분리 + '폭락 패널'(KOSPI 최악 20일 각 자산 수익)로 위기 성과 직접 확인.
  * 공통기간이 달러ETF(2016-12~)에 맞춰지므로 훈련창이 짧다(2017~2019). 2020코로나·2022약세는 검증창.

실행: cd backtest && python hedge_research.py
"""
import io
import sys

import numpy as np
import pandas as pd
import FinanceDataReader as fdr

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", line_buffering=True)

ONE_WAY_COST = 0.00015 + 0.001
BAND, W_OFF = 0.02, 0.2
LOOKBACKS = (120, 150, 200)
TRAIN_END = "2019-12-31"

EQ = "069500"
HEDGES = {
    "단기채(기준)": "153130",
    "미국달러선물": "261240",
    "인버스": "114800",
    "금선물(H)": "132030",
    "국고채10년": "148070",
}


def band_state(close, sma, band=BAND):
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


def ensemble_weight(close):
    states = [band_state(close, close.rolling(lb).mean()) for lb in LOOKBACKS]
    frac = np.nanmean(np.vstack(states), axis=0)
    return W_OFF + (1 - W_OFF) * frac


def metrics(nav):
    yrs = len(nav) / 252
    cagr = (nav[-1] / nav[0]) ** (1 / yrs) - 1
    peak = np.maximum.accumulate(nav)
    mdd = (nav / peak - 1).min()
    dr = np.diff(nav) / nav[:-1]
    sharpe = dr.mean() / dr.std() * np.sqrt(252) if dr.std() > 0 else 0
    return cagr * 100, mdd * 100, (cagr / abs(mdd) if mdd < 0 else float("inf")), sharpe


def run():
    eq_close = fdr.DataReader(EQ)["Close"].dropna()
    hedge_close = {n: fdr.DataReader(c)["Close"].dropna() for n, c in HEDGES.items()}

    # 공통 인덱스
    idx = eq_close.index
    for s in hedge_close.values():
        idx = idx.intersection(s.index)
    eq = eq_close.reindex(idx)
    eq_ret = eq.pct_change().to_numpy()
    w = ensemble_weight(eq)  # 주식 비중
    hedge_ret = {n: s.reindex(idx).pct_change().to_numpy() for n, s in hedge_close.items()}

    valid = ~np.isnan(w)
    idx_v = idx[valid]
    is_tr = np.asarray(idx_v <= TRAIN_END)
    print(f"공통기간 {idx_v[0].date()} ~ {idx_v[-1].date()} | 훈련 {is_tr.sum()}일 / 검증 {(~is_tr).sum()}일\n")

    def sim(defensive_ret, blend=None):
        wv = w[valid]
        er = eq_ret[valid]
        if blend is None:
            dr = defensive_ret[valid]
        else:  # 두 자산 50/50 블렌드
            dr = 0.5 * defensive_ret[valid] + 0.5 * blend[valid]
        w_prev = np.concatenate([[wv[0]], wv[:-1]])
        turn = np.abs(wv - w_prev)
        port = w_prev * er + (1 - w_prev) * np.nan_to_num(dr) - turn * ONE_WAY_COST
        return np.cumprod(1 + np.nan_to_num(port))

    print(f"{'방어 슬리브':<22}{'훈련CAGR':>8}{'훈련MDD':>8}{'훈련Cal':>7} |"
          f"{'검증CAGR':>8}{'검증MDD':>8}{'검증Cal':>7}{'검증Shrp':>8}")
    print("-" * 84)
    rows = []
    for name, r in hedge_ret.items():
        nav = sim(r)
        c_tr, m_tr, cal_tr, _ = metrics(nav[is_tr])
        c_te, m_te, cal_te, sh_te = metrics(nav[~is_tr])
        rows.append((name, m_te, cal_te))
        print(f"{name:<22}{c_tr:>7.1f}%{m_tr:>7.1f}%{cal_tr:>7.2f} |"
              f"{c_te:>7.1f}%{m_te:>7.1f}%{cal_te:>7.2f}{sh_te:>8.2f}")
    # 블렌드: 달러50 + 단기채50
    nav = sim(hedge_ret["미국달러선물"], blend=hedge_ret["단기채(기준)"])
    c_tr, m_tr, cal_tr, _ = metrics(nav[is_tr])
    c_te, m_te, cal_te, sh_te = metrics(nav[~is_tr])
    print(f"{'달러50+단기채50':<22}{c_tr:>7.1f}%{m_tr:>7.1f}%{cal_tr:>7.2f} |"
          f"{c_te:>7.1f}%{m_te:>7.1f}%{cal_te:>7.2f}{sh_te:>8.2f}")

    # 폭락 패널: KOSPI 최악 20일에 각 방어자산 수익
    print("\n[폭락 패널] KOSPI 200 최악 20일 당일 각 자산 평균수익")
    worst = pd.Series(eq_ret, index=idx).nsmallest(20).index
    print(f"   KODEX 200 (기준)   : {pd.Series(eq_ret, index=idx).loc[worst].mean()*100:+.2f}%")
    for name, s in hedge_close.items():
        r = s.reindex(idx).pct_change()
        print(f"   {name:<18}: {r.loc[worst].mean()*100:+.2f}%")

    print("\n판정: 검증 MDD를 기준(단기채) 대비 낮추고 Calmar/Sharpe를 높이면 헷지 채택 가치.")


if __name__ == "__main__":
    run()
