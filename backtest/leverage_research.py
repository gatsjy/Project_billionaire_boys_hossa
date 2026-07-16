"""
leverage_research.py — T1-2 조건부 레버리지 코어 검증 (todo.md)

가설: 강추세 + 저변동 구간에서만 KODEX 레버리지(122630, 실측 1.99x)로 노출을 키우면,
  레버리지 감쇠를 추세필터로 관리하며 강세장 수익을 증폭할 수 있다.
근거: wallstreet 연구 — 레버리지는 '추세필터가 있어야만' 값어치, 없으면 감쇠로 독.
  또 Phase 21에서 '1x엔 수확할 감쇠가 작다'를 확인 → 2x로 올렸을 때의 손익을 본다.

실데이터: 122630(2x)·069500(1x) 모두 2014~ 존재(합성 불필요). 회귀 배율 1.99x·상관 0.998.

전략(앙상블 추세 위에서 레버리지 스위치):
  - 강세(앙상블 frac ≥ hi) AND 저변동(실현변동성 ≤ vol_cap) → 2x ETF 100%
  - 중립(frac 중간) → 1x ETF (비중은 frac)
  - 약세(frac 낮음) → 방어(단기채 캐리)
  비교군: ①항상 1x 현행(앙상블+단기채) ②항상 2x 존버 ③조건부 레버리지.
  비용 편도 0.115%, 방어 단기채 연 2.75%, 훈련~2019/검증2020~. 레버리지 전환도 회전비용.

판정: 조건부가 훈련·검증 양 구간에서 현행 대비 **CAGR을 올리면서 Calmar를 유지/개선**하면 채택.
  (레버리지는 수익 증폭이 목적이므로 Calmar 유지 + CAGR↑가 성공 기준. Calmar 훼손은 폐기.)
실행: cd backtest && python leverage_research.py
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
BASE, LEV = "069500", "122630"


def band_state(close, sma, band=BAND):
    c, s = close.to_numpy(), sma.to_numpy()
    out = np.full(len(c), np.nan); st = None
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


def ensemble_frac(close, lookbacks=(120, 150, 200)):
    states = [band_state(close, close.rolling(lb).mean()) for lb in lookbacks]
    return np.nanmean(np.vstack(states), axis=0)      # 0~1 강세 이평 비율


def realized_vol(ret, lookback=20):
    return (pd.Series(ret).rolling(lookback).std() * np.sqrt(252)).to_numpy()


def metrics(port):
    nav = np.cumprod(1 + np.nan_to_num(port))
    yrs = len(nav) / 252
    cagr = (nav[-1] / nav[0]) ** (1 / yrs) - 1
    peak = np.maximum.accumulate(nav)
    mdd = (nav / peak - 1).min()
    cal = cagr / abs(mdd) if mdd < 0 else float("inf")
    ex = port - RF_DAILY
    shp = (np.nanmean(ex) / np.nanstd(ex) * np.sqrt(252)) if np.nanstd(ex) > 0 else 0.0
    return cagr * 100, mdd * 100, cal, shp


def run():
    base = fdr.DataReader(BASE)["Close"].dropna()
    lev = fdr.DataReader(LEV)["Close"].dropna()
    df = pd.concat([base.rename("b"), lev.rename("l")], axis=1).dropna()
    rb = df["b"].pct_change().to_numpy()      # 1x 일간수익
    rl = df["l"].pct_change().to_numpy()      # 2x 실제 일간수익(감쇠·추적오차 포함)
    frac = ensemble_frac(df["b"])
    rv = realized_vol(rb, 20)
    idx = df.index

    # 포트 수익 시계열: 전일 목표노출·레그로 오늘 수익(미래참조 방지), 노출변화분에 회전비용.
    def make2(mode, hi=0.99, vol_cap=0.20):
        port = np.full(len(df), np.nan)
        prev_expo, prev_leg = 0.0, 0.0
        started = False
        for i in range(len(df)):
            f = frac[i]
            if np.isnan(f):
                prev_leg = rl[i] if False else rb[i]
                continue
            if i > 0 and started:
                turn = abs(cur_expo - prev_expo)
                port[i] = prev_expo * prev_leg + (1 - prev_expo) * RF_DAILY - turn * ONE_WAY_COST
            # 오늘의 목표노출·레그 결정(내일 적용)
            if mode == "cur1x":
                cur_expo, use_lev = W_OFF + (1 - W_OFF) * f, False
            elif mode == "always2x":
                cur_expo, use_lev = 1.0, True
            else:
                if f >= hi and rv[i] <= vol_cap:
                    cur_expo, use_lev = 1.0, True
                else:
                    cur_expo, use_lev = W_OFF + (1 - W_OFF) * f, False
            prev_expo = cur_expo
            prev_leg = rl[i] if use_lev else rb[i]
            started = True
        return port

    variants = [
        ("1x B&H", None),
        ("2x 존버(always2x)", "always2x"),
        ("현행 1x(앙상블+단기채)", "cur1x"),
        ("조건부 2x (강세+변동≤20%)", ("cond", 0.99, 0.20)),
        ("조건부 2x (강세+변동≤25%)", ("cond", 0.99, 0.25)),
        ("조건부 2x (frac≥0.66+≤20%)", ("cond", 0.66, 0.20)),
    ]

    print(f"KODEX 1x(069500)/2x(122630) {idx[0].date()}~{idx[-1].date()} | 방어 단기채 연{RF_ANNUAL:.2%}")
    print("레버리지=실제 ETF(감쇠·추적오차 포함). 신호=전일 종가(미래참조 없음)\n")
    hdr = (f"{'설계':<27}{'훈CAGR':>7}{'훈MDD':>7}{'훈Cal':>6} |"
           f"{'검CAGR':>7}{'검MDD':>7}{'검Cal':>6}{'검Shp':>6}")
    print(hdr); print("-" * len(hdr))
    # 1x B&H는 단순 처리
    def bh():
        port = np.full(len(df), np.nan)
        for i in range(1, len(df)):
            port[i] = rb[i]
        return port
    for name, spec in variants:
        if spec is None:
            port = bh()
        elif isinstance(spec, str):
            port = make2(spec)
        else:
            port = make2(spec[0], hi=spec[1], vol_cap=spec[2])
        valid = ~np.isnan(port)
        tr = np.asarray(idx[valid] <= TRAIN_END)
        c_tr, m_tr, cal_tr, _ = metrics(port[valid][tr])
        c_te, m_te, cal_te, s_te = metrics(port[valid][~tr])
        print(f"{name:<27}{c_tr:>6.1f}%{m_tr:>6.1f}%{cal_tr:>6.2f} |"
              f"{c_te:>6.1f}%{m_te:>6.1f}%{cal_te:>6.2f}{s_te:>6.2f}")

    print("\n판정: 조건부가 양 구간에서 현행 대비 CAGR↑ AND Calmar 유지/개선이면 채택. "
          "Calmar 훼손(레버리지 감쇠·갭 손실)이면 폐기.")
    stress_2008()


def stress_2008():
    """결정적 스트레스: KODEX 2x ETF는 2014~라 2008이 없다. KOSPI로 합성 2x를 만들어
    2008 금융위기를 통과시켜 조건부 레버리지의 꼬리(저변동 상승장 반전)를 본다.
    합성 2x = 2×KOSPI일간 − 보수(연0.64%). 실제 ETF 아닌 근사 — 방향성 확인용."""
    ks = fdr.DataReader("KS11", "2005-01-01")["Close"].dropna()
    rb = ks.pct_change().to_numpy()
    rl = 2 * rb - 0.0064 / 252
    frac = ensemble_frac(ks)
    rv = realized_vol(rb, 20)

    def make(cond, hi=0.99, vc=0.20):
        port = np.full(len(ks), np.nan); pe = pl = 0.0; started = False
        for i in range(len(ks)):
            if np.isnan(frac[i]):
                continue
            if i > 0 and started:
                port[i] = pe * pl + (1 - pe) * RF_DAILY - abs(ce - pe) * ONE_WAY_COST
            if cond and frac[i] >= hi and rv[i] <= vc:
                ce, use = 1.0, True
            else:
                ce, use = W_OFF + (1 - W_OFF) * frac[i], False
            pe, pl, started = ce, (rl[i] if use else rb[i]), True
        return port

    def mdd(port, mask=None):
        p = port.copy()
        if mask is not None:
            p[~mask] = np.nan
        p = p[~np.isnan(p)]
        nav = np.cumprod(1 + np.nan_to_num(p))
        return (nav / np.maximum.accumulate(nav) - 1).min() * 100

    m08 = (ks.index >= "2007-06-01") & (ks.index <= "2009-06-30")
    print("\n" + "=" * 60)
    print("[결정적] 2008 스트레스 (합성 2x, KOSPI 2005~2026)")
    for nm, cond in [("현행 1x", False), ("조건부 2x(≤20%)", True)]:
        p = make(cond)
        pv = p[~np.isnan(p)]
        nav = np.cumprod(1 + np.nan_to_num(pv))
        cagr = (nav[-1] / nav[0]) ** (252 / len(nav)) - 1
        print(f"  {nm:16} 전체 CAGR {cagr*100:5.1f}% / MDD {mdd(p):6.1f}% / "
              f"2008낙폭 {mdd(p, m08):6.1f}%")
    print("  → 2008 낙폭이 1x와 비슷하면 '레버리지가 하락장엔 꺼진다'는 설계가 작동한 것.")


if __name__ == "__main__":
    run()
