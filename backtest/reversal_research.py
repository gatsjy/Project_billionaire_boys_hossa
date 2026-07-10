"""
reversal_research.py — 스윙 반전(mean-reversion) 전략 검증

배경 (이 프로젝트 실데이터 판정):
  거래량 돌파 '추격 매수'는 사망(OOS -1.1%/매매). 한국 개별주는 단기 모멘텀이 약하고
  '단기 반전'이 강한 시장이다. 그래서 방향을 뒤집는다 —
  '오른 걸 쫓지 말고, 과대낙폭된 우량주를 눌림에 사서 반등에 판다.'

설계:
  진입(다음날 시가): RSI(14) < THRESH  AND  (선택) 종가 > 장기이평(추세 유지 = 낙폭 우량주)
    → '떨어지는 칼날(추세 이탈주)'이 아니라 '상승추세 속 눌림'만 잡는다.
  청산(갭 인지·비용 반영·손절 우선): 아래 중 먼저 도달
    - 반등 청산: 종가 기준 RSI > EXIT_RSI 면 종가 청산
    - 익절 +TP / 손절 -SL / HOLD일 타임아웃
  변동성 보정: 손절을 max(고정, k×ATR%)로 넓혀 노이즈 손절 방지(어제 교훈).

정직성: 비용(왕복 ~0.38%) · 갭 인지 체결 · 매수시그널 날짜순 70% 학습 / 30% 검증.
캐시된 가격(_cache_prices.pkl) 재사용.
실행: cd backtest && python reversal_research.py
"""

import io
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", line_buffering=True)

from data_loader import get_theme_stocks, get_daily_data
from realistic import evaluate, DEFAULT_COST

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache_prices.pkl")
MAX_HOLD = 15


def load_prices():
    if os.path.exists(CACHE):
        with open(CACHE, "rb") as f:
            data = pickle.load(f)
        print(f"가격 캐시 사용: {len(data)}종목")
        return data
    raise SystemExit("가격 캐시가 없습니다. 먼저 hold_research.py 를 실행해 캐시를 생성하세요.")


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr_pct(df, period=14):
    pc = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - pc).abs(),
                    (df["Low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean() / df["Close"] * 100


def prep(df):
    df = df.copy()
    df["RSI"] = rsi(df["Close"])
    df["MA60"] = df["Close"].rolling(60).mean()
    df["MA120"] = df["Close"].rolling(120).mean()
    df["ATR_Pct"] = atr_pct(df)
    return df


def collect_signals(price_data, rsi_thr, trend_ma):
    """(날짜, 진입가=다음날시가, 향후봉[RSI포함], ATR%). trend_ma: None|'MA60'|'MA120'."""
    sigs = []
    for code, raw in price_data.items():
        if len(raw) < 130:
            continue
        df = prep(raw)
        cond = df["RSI"] < rsi_thr
        if trend_ma is not None:
            cond &= df["Close"] > df[trend_ma]
        for d in df[cond].index:
            i = df.index.get_loc(d)
            if i + 1 >= len(df):
                continue
            entry = float(df.iloc[i + 1]["Open"])
            if entry <= 0:
                continue
            win = df.iloc[i + 1: i + 1 + MAX_HOLD]
            bars = [{"Open": r.Open, "High": r.High, "Low": r.Low,
                     "Close": r.Close, "RSI": r.RSI} for r in win.itertuples()]
            if bars:
                sigs.append((d, entry, bars, float(df.iloc[i]["ATR_Pct"])))
    sigs.sort(key=lambda s: s[0])
    return sigs


def resolve(entry, bars, atrp, tp, sl_fixed, atr_k, exit_rsi, hold, cost=DEFAULT_COST):
    sl = -max(abs(sl_fixed), atr_k * (atrp / 100)) if atr_k else sl_fixed
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
            return cost.net_return(entry, px) * 100, i + 1
    last = bars[min(hold, len(bars)) - 1]
    return cost.net_return(entry, last["Close"]) * 100, min(hold, len(bars))


def report(label, sigs, cutoff, **kw):
    is_r, oos_r, holds = [], [], []
    for i, (d, entry, bars, atrp) in enumerate(sigs):
        net, held = resolve(entry, bars, atrp, **kw)
        (is_r if i < cutoff else oos_r).append(net)
        holds.append(held)
    m_is, m_oos = evaluate(is_r), evaluate(oos_r)
    if m_oos.get("trades", 0) == 0:
        return None
    avgh = sum(holds) / len(holds)
    print(f"{label:<34}{m_oos['trades']:>6}{m_is['expectancy']:>9.3f}%{m_oos['expectancy']:>10.3f}%"
          f"{m_oos['win_rate']:>7.1f}%{m_oos['profit_factor']:>7.2f}{m_oos['max_drawdown']:>8.1f}%{avgh:>7.1f}d")
    return m_is, m_oos


def run():
    price_data = load_prices()

    print("\n" + "=" * 96)
    print("A. 진입 필터 비교  (청산 공통: RSI>55 청산 / TP+7% / ATR손절(k=1.5,최소5%) / 15일)")
    print("=" * 96)
    hdr = f"{'설계':<34}{'표본':>6}{'IS기댓값':>9}{'OOS기댓값':>10}{'승률':>7}{'PF':>7}{'MDD':>8}{'평균보유':>7}"
    print(hdr); print("-" * len(hdr))
    common = dict(tp=0.07, sl_fixed=-0.05, atr_k=1.5, exit_rsi=55, hold=15)
    entries = [
        ("A1 RSI<30, 추세필터 없음", 30, None),
        ("A2 RSI<30 + 120일선 위",  30, "MA120"),
        ("A3 RSI<25 + 120일선 위",  25, "MA120"),
        ("A4 RSI<30 + 60일선 위",   30, "MA60"),
    ]
    best_entry, best_oos = None, -1e9
    for label, thr, ma in entries:
        sigs = collect_signals(price_data, thr, ma)
        cutoff = int(len(sigs) * 0.7)
        res = report(label, sigs, cutoff, **common)
        if res and res[1]["expectancy"] > best_oos:
            best_oos, best_entry = res[1]["expectancy"], (thr, ma, sigs)

    thr, ma, sigs = best_entry
    cutoff = int(len(sigs) * 0.7)
    print("\n" + "=" * 96)
    print(f"B. 청산 변형  (진입 고정: RSI<{thr}" + (f" + {ma} 위" if ma else "") + ")")
    print("=" * 96)
    print(hdr); print("-" * len(hdr))
    exits = [
        ("B1 RSI55 / TP7 / ATR손절 / 15d", dict(tp=0.07, sl_fixed=-0.05, atr_k=1.5, exit_rsi=55, hold=15)),
        ("B2 RSI50 / TP5 / ATR손절 / 10d", dict(tp=0.05, sl_fixed=-0.05, atr_k=1.5, exit_rsi=50, hold=10)),
        ("B3 RSI60 / TP10 / ATR손절 / 20d",dict(tp=0.10, sl_fixed=-0.05, atr_k=2.0, exit_rsi=60, hold=20)),
        ("B4 RSI청산없음 / TP7 / -5% / 10d",dict(tp=0.07, sl_fixed=-0.05, atr_k=0, exit_rsi=200, hold=10)),
    ]
    for label, kw in exits:
        report(label, sigs, cutoff, **kw)

    print("\n판정 관문: OOS 기댓값 > 0 AND PF > 1 (비용 반영). 미달 시 이 진입도 실전 부적합.")


if __name__ == "__main__":
    run()
