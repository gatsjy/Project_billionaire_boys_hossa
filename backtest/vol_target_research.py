"""
vol_target_research.py — T1-1 변동성 타겟팅 검증 (todo.md)

가설: KODEX200 노출을 실현변동성 역비례로 조절하면 위험조정수익(Sharpe/Calmar)이 개선된다.
근거: 자매 프로젝트 wallstreet 연구에서 변동성 타겟팅이 고정노출 대비 Calmar 최상(0.20 vs 0.14).

설계(index_enhancement_research 컨벤션 계승):
  - 실현변동성 = 20일(또는 60일) 일간수익 표준편차 × √252. **shift 없이 t까지 정보로 t 비중 →
    simulate가 w_prev로 1일 지연 적용 → 미래참조 없음**(기존 프레임과 동일).
  - 변동성 타겟 비중 = target_vol / 실현변동성, [0, 1] 클램프.
  - 결합안: 앙상블(추세 '얼마나 강세')을 변동성 타겟으로 '캡'(min) → 난기류에 노출 축소.
  - 방어분(1-비중)은 단기채 캐리(연 2.75%). 편도비용 0.115%. 훈련~2019/검증2020~.

판정: 결합안이 훈련·검증 '양 구간'에서 현행(A+B) 대비 Sharpe·Calmar를 높이면 채택.
실행: cd backtest && python vol_target_research.py
"""
import io
import sys

import numpy as np
import pandas as pd
import FinanceDataReader as fdr

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", line_buffering=True)

ONE_WAY_COST = 0.00015 + 0.001
RF_ANNUAL = 0.0275
RF_DAILY = (1 + RF_ANNUAL) ** (1 / 252) - 1
TRAIN_END = "2019-12-31"
BAND = 0.02
W_OFF = 0.2
CODE = "069500"


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


def weights_ensemble(close, lookbacks=(120, 150, 200)):
    states = [band_state(close, close.rolling(lb).mean()) for lb in lookbacks]
    frac = np.nanmean(np.vstack(states), axis=0)
    return W_OFF + (1 - W_OFF) * frac


def realized_vol(eq_ret, lookback=20):
    return (pd.Series(eq_ret).rolling(lookback).std() * np.sqrt(252)).to_numpy()


def weights_voltarget(eq_ret, target=0.12, lookback=20, cap=1.0):
    rv = realized_vol(eq_ret, lookback)
    with np.errstate(divide="ignore", invalid="ignore"):
        w = np.where(rv > 0, target / rv, np.nan)
    return np.clip(w, 0.0, cap)


def simulate(eq_ret, weights, bond=True):
    valid = ~np.isnan(weights)
    r, w = eq_ret[valid], weights[valid]
    w_prev = np.concatenate([[w[0]], w[:-1]])
    turn = np.abs(w - w_prev)
    cash_ret = RF_DAILY if bond else 0.0
    port = w_prev * r + (1 - w_prev) * cash_ret - turn * ONE_WAY_COST
    return port, valid


def metrics(port):
    """port: 일간 포트 수익률. → CAGR/MDD/Calmar/Sharpe/평균노출은 별도."""
    nav = np.cumprod(1 + np.nan_to_num(port))
    yrs = len(nav) / 252
    cagr = (nav[-1] / nav[0]) ** (1 / yrs) - 1
    peak = np.maximum.accumulate(nav)
    mdd = (nav / peak - 1).min()
    cal = cagr / abs(mdd) if mdd < 0 else float("inf")
    ex = port - RF_DAILY
    sharpe = (np.nanmean(ex) / np.nanstd(ex) * np.sqrt(252)) if np.nanstd(ex) > 0 else 0.0
    return cagr * 100, mdd * 100, cal, sharpe


def run():
    close = fdr.DataReader(CODE)["Close"].dropna()
    eq_ret = close.pct_change().to_numpy()
    ens = weights_ensemble(close)

    def combo(target, lb):
        vt = weights_voltarget(eq_ret, target=target, lookback=lb)
        return np.minimum(ens, vt)          # 추세강세를 변동성 타겟으로 캡

    variants = [
        ("B&H (기준선)", np.ones(len(close))),
        ("A+B 현행: 앙상블+단기채", ens),
        ("VT 순수 목표12% (20일)", weights_voltarget(eq_ret, 0.12, 20)),
        ("VT 순수 목표15% (20일)", weights_voltarget(eq_ret, 0.15, 20)),
        ("결합 앙상블×VT 12%(20일)", combo(0.12, 20)),
        ("결합 앙상블×VT 15%(20일)", combo(0.15, 20)),
        ("결합 앙상블×VT 12%(60일)", combo(0.12, 60)),
    ]

    print(f"KODEX 200 {close.index[0].date()}~{close.index[-1].date()} | 방어현금 연{RF_ANNUAL:.2%}\n")
    hdr = (f"{'설계':<28}{'훈CAGR':>7}{'훈MDD':>7}{'훈Cal':>6}{'훈Shp':>6} |"
           f"{'검CAGR':>7}{'검MDD':>7}{'검Cal':>6}{'검Shp':>6}{'평노출':>6}")
    print(hdr); print("-" * len(hdr))
    for name, w in variants:
        port, valid = simulate(eq_ret, w)
        idx = close.index[valid]
        tr = np.asarray(idx <= TRAIN_END)
        c_tr, m_tr, cal_tr, s_tr = metrics(port[tr])
        c_te, m_te, cal_te, s_te = metrics(port[~tr])
        avg_expo = np.nanmean(w[valid]) * 100
        print(f"{name:<28}{c_tr:>6.1f}%{m_tr:>6.1f}%{cal_tr:>6.2f}{s_tr:>6.2f} |"
              f"{c_te:>6.1f}%{m_te:>6.1f}%{cal_te:>6.2f}{s_te:>6.2f}{avg_expo:>5.0f}%")

    print("\n판정: 결합안이 훈련·검증 양 구간에서 A+B 대비 Sharpe·Calmar 개선하면 채택. "
          "회전율↑(비용)·평균노출↓(수익 희생) 트레이드오프 확인.")


if __name__ == "__main__":
    run()
