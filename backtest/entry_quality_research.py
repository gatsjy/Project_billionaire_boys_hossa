"""
entry_quality_research.py — '타점(진입) 품질' 개선: 오늘 금호전기 실패의 교훈 대입

오늘 실패 해부 (001210 금호전기, 2026-07-10):
  어제종가 1,316 → 시가 1,368(갭+4%) → 고가 1,535 분출 → 봇 1,500 시장가 매수
  → 저가 1,320(-12%) → -3.4% 손절.  ATR% 20.6%(정상주 4~5배)인 펌핑주.
  실패 본질 = '분출의 높은 타점을 시장가로 추격'. 좋은 타점 = 극단변동성 회피 + 눌림 지정가.

검증된 반전 전략(RSI<30 & 종가>60일선, RSI회복/TP/ATR손절/10일)에 두 개선을 '대입':
  (F) ATR% 상한   : 극단 변동성(작전주) 신호 제외        → 금호전기(ATR20.6%) 배제
  (L) 눌림 지정가 : 다음날 저가가 '전일 종가' 이하로 내려올 때만, min(시가, 전일종가)에 체결.
                    갭상승 추격을 원천 차단(안 내려오면 스킵).  → 금호전기(저가1320>전일종가1316) 미체결

정직성: 비용·갭 인지 체결·70/30 walk-forward 동일. 진입바(다음날)는 체결 전용,
청산은 그 다음 봉부터(양 변형 동일 규칙으로 사과-사과 비교).
실행: cd backtest && python entry_quality_research.py
"""

import io
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", line_buffering=True)

from realistic import evaluate, DEFAULT_COST

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache_prices.pkl")
MAX_HOLD = 12


def rsi(s, p=14):
    d = s.diff()
    g = d.where(d > 0, 0.0).rolling(p).mean()
    l = (-d.where(d < 0, 0.0)).rolling(p).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))


def atr_pct(df, p=14):
    pc = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - pc).abs(),
                    (df["Low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(p).mean() / df["Close"] * 100


def load_prices():
    with open(CACHE, "rb") as f:
        return pickle.load(f)


def collect(price_data):
    """반전 신호(RSI<30 & 종가>MA60). 진입바(t+1) OHLC + 신호일 종가/ATR% + 이후 봉(RSI)."""
    sigs = []
    for code, raw in price_data.items():
        if len(raw) < 130:
            continue
        df = raw.copy()
        df["RSI"] = rsi(df["Close"])
        df["MA60"] = df["Close"].rolling(60).mean()
        df["ATR_Pct"] = atr_pct(df)
        cond = (df["RSI"] < 30) & (df["Close"] > df["MA60"])
        for d in df[cond].index:
            i = df.index.get_loc(d)
            if i + 2 >= len(df):
                continue
            sig_close = float(df.iloc[i]["Close"])
            atrp = float(df.iloc[i]["ATR_Pct"])
            eb = df.iloc[i + 1]  # 진입바(다음날)
            entry_bar = {"Open": float(eb["Open"]), "High": float(eb["High"]),
                         "Low": float(eb["Low"]), "Close": float(eb["Close"])}
            win = df.iloc[i + 2: i + 2 + MAX_HOLD]  # 청산은 진입바 다음 봉부터
            exit_bars = [{"Open": r.Open, "High": r.High, "Low": r.Low,
                          "Close": r.Close, "RSI": r.RSI} for r in win.itertuples()]
            if exit_bars:
                sigs.append({"date": d, "code": code, "sig_close": sig_close,
                             "atrp": atrp, "eb": entry_bar, "bars": exit_bars})
    sigs.sort(key=lambda s: s["date"])
    return sigs


def resolve(entry, bars, atrp, tp=0.05, sl_fixed=-0.05, atr_k=1.5,
            exit_rsi=50, hold=10, cost=DEFAULT_COST):
    sl = -max(abs(sl_fixed), atr_k * (atrp / 100))
    stop, target = entry * (1 + sl), entry * (1 + tp)
    for i, b in enumerate(bars[:hold]):
        o, h, l, c = b["Open"], b["High"], b["Low"], b["Close"]
        px = None
        if o <= stop:
            px = o
        elif o >= target:
            px = o
        elif l <= stop:
            px = stop
        elif h >= target:
            px = target
        elif not pd.isna(b["RSI"]) and b["RSI"] > exit_rsi:
            px = c
        if px is not None:
            return cost.net_return(entry, px) * 100
    return cost.net_return(entry, bars[min(hold, len(bars)) - 1]["Close"]) * 100


def fill_price(s, use_limit):
    """진입 체결가. use_limit=True면 '전일(신호일) 종가' 지정가로 눌림만 체결(아니면 None=스킵)."""
    eb = s["eb"]
    if not use_limit:
        return eb["Open"]                      # 시가 추격(현행)
    limit = s["sig_close"]
    if eb["Low"] <= limit:                     # 지정가까지 내려왔을 때만
        return min(eb["Open"], limit)          # 갭상승분은 지불 안 함
    return None                                 # 안 내려오면 미체결(스킵)


def evaluate_variant(sigs, cutoff, atr_cap=None, use_limit=False):
    is_r, oos_r, filled = [], [], 0
    for i, s in enumerate(sigs):
        if atr_cap is not None and s["atrp"] > atr_cap:
            continue
        entry = fill_price(s, use_limit)
        if entry is None or entry <= 0:
            continue
        filled += 1
        net = resolve(entry, s["bars"], s["atrp"])
        (is_r if i < cutoff else oos_r).append(net)
    m_oos = evaluate(oos_r)
    m_is = evaluate(is_r)
    return m_is, m_oos, filled


def run():
    price_data = load_prices()
    sigs = collect(price_data)
    cutoff = int(len(sigs) * 0.7)
    print(f"반전 신호 {len(sigs)}건 (ATR%>10 인 고변동성 신호: "
          f"{sum(1 for s in sigs if s['atrp'] > 10)}건)\n")

    variants = [
        ("E1 기준(시가 추격)",              dict(atr_cap=None, use_limit=False)),
        ("E2 +ATR상한 8%",                dict(atr_cap=8,   use_limit=False)),
        ("E3 +ATR상한 6%",                dict(atr_cap=6,   use_limit=False)),
        ("E4 +눌림 지정가",                dict(atr_cap=None, use_limit=True)),
        ("E5 +ATR8% & 눌림지정가(둘다)",     dict(atr_cap=8,   use_limit=True)),
        ("E6 +ATR6% & 눌림지정가(둘다)",     dict(atr_cap=6,   use_limit=True)),
    ]
    hdr = f"{'설계':<30}{'체결수':>7}{'IS기댓값':>10}{'OOS기댓값':>11}{'승률':>7}{'PF':>7}{'MDD':>8}"
    print(hdr); print("-" * len(hdr))
    for label, kw in variants:
        m_is, m_oos, filled = evaluate_variant(sigs, cutoff, **kw)
        if m_oos.get("trades", 0) == 0:
            print(f"{label:<30}{filled:>7}   (OOS 표본 없음)"); continue
        print(f"{label:<30}{filled:>7}{m_is['expectancy']:>9.3f}%{m_oos['expectancy']:>10.3f}%"
              f"{m_oos['win_rate']:>6.1f}%{m_oos['profit_factor']:>7.2f}{m_oos['max_drawdown']:>7.1f}%")

    # 금호전기 케이스 명시적 확인
    print("\n[금호전기(001210) 신호가 각 필터에 걸리는가]")
    kh = [s for s in sigs if s["code"] == "001210"]
    if kh:
        for s in kh[-3:]:
            atr_hit = "ATR8%컷 제외" if s["atrp"] > 8 else "ATR통과"
            limit_fill = fill_price(s, True)
            lim = "지정가 미체결(스킵)" if limit_fill is None else f"지정가 체결 {limit_fill:.0f}"
            print(f"  {s['date'].date()} ATR%={s['atrp']:.1f} → {atr_hit} / {lim}")
    else:
        print("  (금호전기는 RSI<30&MA60 반전신호에는 해당 없음 — 원래 돌파봇 매수였음)")

    print("\n판정: OOS 기댓값·PF·승률이 E1 대비 개선되고 PF>1 유지되면 '타점 개선' 유효.")


if __name__ == "__main__":
    run()
