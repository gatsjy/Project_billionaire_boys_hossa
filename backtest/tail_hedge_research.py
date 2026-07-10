"""
tail_hedge_research.py — 상시(permanent) tail hedge 검증

문제: 현행 헷지(달러)는 방어 슬리브로만 → 추세가 200일선 아래로 '깨진 뒤'에 켜진다.
      급락 초기(아직 RISK_ON 100%인 구간)의 갭락은 못 막는다.
가설: 추세와 무관하게 '항상' 소액 달러를 들고 있으면 초기 급락을 쿠션한다.
반론: 강세장에서 그 상시 달러가 주식 상승을 못 따라가 CAGR을 갉아먹는다(드래그).
      → 초기 크래시 방어 이득 vs 강세장 드래그, 어느 쪽이 큰가를 실측한다.

비중 설계 (합=1):
  base = 1 - perm            # 상시 헷지 뗀 나머지
  주식  = ensemble * base
  방어  = (1-ensemble) * base 를 달러(cond_frac):단기채로 분할
  헷지  = perm(상시) + cond_frac*방어
변형:
  V1 추세+단기채(헷지 없음)          perm=0,   cond=0
  V2 조건부 달러(현행)               perm=0,   cond=0.5
  V3 상시5% + 조건부                 perm=0.05,cond=0.5
  V4 상시10% + 조건부                perm=0.10,cond=0.5
  V5 상시15% + 조건부                perm=0.15,cond=0.5
  V6 상시10%만(조건부 없음)          perm=0.10,cond=0

정직성: ETF 비용 · 훈련(~2019)/검증(2020~) 분리 · '코로나 급락창(2020-02~04)' 낙폭 별도 측정.
실행: cd backtest && python tail_hedge_research.py
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
EQ, USD, BOND = "069500", "261240", "153130"


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


def ensemble(close):
    states = [band_state(close, close.rolling(lb).mean()) for lb in LOOKBACKS]
    return W_OFF + (1 - W_OFF) * np.nanmean(np.vstack(states), axis=0)


def metrics(nav):
    yrs = len(nav) / 252
    cagr = (nav[-1] / nav[0]) ** (1 / yrs) - 1
    mdd = (nav / np.maximum.accumulate(nav) - 1).min()
    dr = np.diff(nav) / nav[:-1]
    sharpe = dr.mean() / dr.std() * np.sqrt(252) if dr.std() > 0 else 0
    return cagr * 100, mdd * 100, (cagr / abs(mdd) if mdd < 0 else float("inf")), sharpe


def run():
    eqc = fdr.DataReader(EQ)["Close"].dropna()
    usdc = fdr.DataReader(USD)["Close"].dropna()
    bondc = fdr.DataReader(BOND)["Close"].dropna()
    idx = eqc.index.intersection(usdc.index).intersection(bondc.index)
    eqc, usdc, bondc = eqc.reindex(idx), usdc.reindex(idx), bondc.reindex(idx)

    ens = ensemble(eqc)
    er, ur, br = eqc.pct_change().to_numpy(), usdc.pct_change().to_numpy(), bondc.pct_change().to_numpy()
    valid = ~np.isnan(ens)
    idxv = idx[valid]
    ens, er, ur, br = ens[valid], er[valid], ur[valid], br[valid]
    is_tr = np.asarray(idxv <= TRAIN_END)

    def sim(perm, cond):
        base = 1 - perm
        w_eq = ens * base
        w_def = (1 - ens) * base
        w_hedge = perm + cond * w_def
        w_bond = (1 - cond) * w_def
        # 전일 비중으로 수익, 회전율 비용
        nav = [1.0]
        pe = pb = ph = None
        for i in range(len(ens)):
            if i > 0:
                r = (w_eq[i-1]*er[i] + w_hedge[i-1]*ur[i] + w_bond[i-1]*br[i])
                turn = abs(w_eq[i]-w_eq[i-1]) + abs(w_hedge[i]-w_hedge[i-1]) + abs(w_bond[i]-w_bond[i-1])
                nav.append(nav[-1] * (1 + np.nan_to_num(r) - turn*ONE_WAY_COST))
        return np.array(nav)

    variants = [
        ("V1 추세+단기채(헷지X)", 0.0, 0.0),
        ("V2 조건부 달러(현행)", 0.0, 0.5),
        ("V3 상시5% + 조건부", 0.05, 0.5),
        ("V4 상시10% + 조건부", 0.10, 0.5),
        ("V5 상시15% + 조건부", 0.15, 0.5),
        ("V6 상시10%만", 0.10, 0.0),
    ]
    # 코로나 급락창
    covid = (idxv >= "2020-02-01") & (idxv <= "2020-04-30")

    print(f"공통 {idxv[0].date()}~{idxv[-1].date()} | 훈련 {is_tr.sum()} / 검증 {(~is_tr).sum()}\n")
    hdr = (f"{'설계':<22}{'훈련CAGR':>8}{'훈련MDD':>8}{'훈련Cal':>7} |"
           f"{'검증CAGR':>8}{'검증MDD':>8}{'검증Cal':>7}{'검증Shrp':>7}{'코로나낙폭':>9}")
    print(hdr); print("-" * len(hdr))
    for name, perm, cond in variants:
        nav = sim(perm, cond)
        c_tr, m_tr, cal_tr, _ = metrics(nav[is_tr])
        c_te, m_te, cal_te, sh = metrics(nav[~is_tr])
        cov = (lambda n: (n / np.maximum.accumulate(n) - 1).min()*100)(nav[covid])
        print(f"{name:<22}{c_tr:>7.1f}%{m_tr:>7.1f}%{cal_tr:>7.2f} |"
              f"{c_te:>7.1f}%{m_te:>7.1f}%{cal_te:>7.2f}{sh:>7.2f}{cov:>8.1f}%")

    print("\n판정: 상시 tail hedge가 '코로나 급락 낙폭'을 줄이면서 검증 Calmar/Sharpe를 "
          "현행(V2) 이상으로 유지하면 채택. CAGR 드래그가 크면 기각.")


if __name__ == "__main__":
    run()
