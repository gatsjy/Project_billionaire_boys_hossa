"""
hold_research.py — 청산 방식 연구: "보유기간 연장 + 우측꼬리 보존"이 우위를 만드는가

배경 (optimization_results.md, 2026-07-10):
  진입(거래량 3배+갭+추세)을 고정한 채 익절/손절 20개 조합 전부가 OOS 기댓값 음수.
  현재 청산 구조(+7% 익절 상한 / 3일 타임스탑)는 돌파 전략의 생명줄인
  '우측 꼬리(대박 소수)'를 스스로 자르면서 손절 비용만 쌓는다는 가설을 검증한다.

비교 청산 설계 (진입 시그널은 전부 동일 — apply_strategy_v1):
  A. 기준: TP+7% / SL-3% / 3영업일      (현행 = optimizer 판정 재현용)
  B. 보유 연장: 동일 TP/SL / 10일
  C. 보유 연장: 동일 TP/SL / 20일
  D. 꼬리 보존: TP 없음 / SL-7% / 20일
  E. 트레일링: TP 없음 / 고점대비 -10% 트레일 / 20일
  F. 추세 청산: TP 없음 / 종가<MA20 이탈 시 청산 / 하드 SL-10% / 20일
  G. 신호 선별: E 조건 + 거래량 5배 이상만 (빈도 축소)
  H. 신호 선별: F 조건 + 거래량 5배 이상만

정직성 규칙은 optimizer 와 동일:
  - 비용 반영(왕복 ~0.38%), 갭 인지 체결(시가가 선을 넘겨 시작하면 시가 체결)
  - 한 봉에서 손절/익절 동시 가능 시 손절 우선(최악 가정)
  - 매수시그널 날짜순 앞 70% 학습(IS) / 뒤 30% 검증(OOS), 판단은 OOS 기준
  - 트레일링 고점은 '전일까지의 고가'로만 갱신(당일 고가로 당일 청산선을 올리지 않음 — 보수적)

실행: cd backtest && python hold_research.py   (가격 캐시 _cache_prices.pkl 재사용)
"""

import io
import os
import pickle
import sys
from datetime import datetime, timedelta

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", line_buffering=True)

from strategy import apply_strategy_v1
from data_loader import get_theme_stocks, get_daily_data
from realistic import evaluate, DEFAULT_COST

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache_prices.pkl")
YEARS = 3
MAX_HOLD = 20  # 최장 실험 보유일


# ---------------------------------------------------------------------------
# 데이터
# ---------------------------------------------------------------------------
def load_price_data():
    if os.path.exists(CACHE):
        with open(CACHE, "rb") as f:
            data = pickle.load(f)
        print(f"가격 캐시 사용: {len(data)}종목 ({CACHE})")
        return data

    end = datetime.today()
    start = end - timedelta(days=365 * YEARS)
    theme_stocks = get_theme_stocks()
    print(f"가격 다운로드: {len(theme_stocks)}종목 ({start:%Y-%m-%d} ~ {end:%Y-%m-%d})")
    data = {}
    for _, row in theme_stocks.iterrows():
        code = row["Code"]
        df = get_daily_data(code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if not df.empty and len(df) >= 25:
            data[code] = df
    with open(CACHE, "wb") as f:
        pickle.dump(data, f)
    print(f"다운로드 완료 {len(data)}종목 → 캐시 저장")
    return data


def collect_signals(price_data):
    """(날짜, 진입가, 향후봉리스트, 거래량배수) — 진입은 시그널 당일 시가."""
    signals = []
    for code, raw in price_data.items():
        df = apply_strategy_v1(raw)
        if df.empty:
            continue
        vol_ratio = df["Prev_Volume"] / df["Prev_Volume_MA20"]
        for buy_date in df[df["Buy_Signal"]].index:
            entry = float(df.loc[buy_date, "Open"])
            if entry <= 0:
                continue
            window = df.loc[buy_date:].iloc[1: 1 + MAX_HOLD]
            if window.empty:
                continue
            bars = [
                {"Open": r.Open, "High": r.High, "Low": r.Low,
                 "Close": r.Close, "MA20": r.MA20}
                for r in window.itertuples()
            ]
            signals.append((buy_date, entry, bars, float(vol_ratio.loc[buy_date])))
    signals.sort(key=lambda s: s[0])
    return signals


# ---------------------------------------------------------------------------
# 범용 청산 엔진 (갭 인지·손절 우선·보수적 트레일링)
# ---------------------------------------------------------------------------
def resolve_exit_ex(entry, bars, tp=None, sl=None, trail=None, ma_exit=False,
                    hold_days=MAX_HOLD, cost=DEFAULT_COST):
    stop = entry * (1 + sl) if sl is not None else None
    target = entry * (1 + tp) if tp is not None else None
    peak = entry  # 트레일 고점: '전일까지' 정보로만 갱신 (보수적)

    for i, b in enumerate(bars[:hold_days]):
        o, h, l, c = b["Open"], b["High"], b["Low"], b["Close"]
        tstop = peak * (1 - trail) if trail is not None else None

        exit_price = None
        # (a) 갭: 시가가 이미 선을 넘겨 시작
        if stop is not None and o <= stop:
            exit_price = o
        elif tstop is not None and o <= tstop:
            exit_price = o
        elif target is not None and o >= target:
            exit_price = o
        # (b) 장중: 손절류 우선 (경로 미상 → 최악 가정)
        elif stop is not None and l <= stop:
            exit_price = stop
        elif tstop is not None and l <= tstop:
            exit_price = tstop
        elif target is not None and h >= target:
            exit_price = target
        # (c) 추세 이탈: 그 봉 종가가 MA20 아래면 종가 청산
        elif ma_exit and not pd.isna(b["MA20"]) and c < b["MA20"]:
            exit_price = c

        if exit_price is not None:
            return cost.net_return(entry, exit_price) * 100, i + 1

        peak = max(peak, h)  # 다음 봉부터 반영

    last = bars[min(hold_days, len(bars)) - 1]
    return cost.net_return(entry, last["Close"]) * 100, min(hold_days, len(bars))


# ---------------------------------------------------------------------------
# 실험 정의/실행
# ---------------------------------------------------------------------------
VARIANTS = [
    # (라벨, dict(tp, sl, trail, ma_exit, hold), 최소 거래량배수)
    ("A 기준 +7/-3/3d (현행)",        dict(tp=0.07, sl=-0.03, hold_days=3), 0),
    ("B +7/-3/10d",                  dict(tp=0.07, sl=-0.03, hold_days=10), 0),
    ("C +7/-3/20d",                  dict(tp=0.07, sl=-0.03, hold_days=20), 0),
    ("D TP없음/SL-7/20d",            dict(sl=-0.07, hold_days=20), 0),
    ("E TP없음/트레일-10%/20d",       dict(trail=0.10, hold_days=20), 0),
    ("F TP없음/MA20이탈+SL-10/20d",   dict(sl=-0.10, ma_exit=True, hold_days=20), 0),
    ("G = E + 거래량5배+",            dict(trail=0.10, hold_days=20), 5),
    ("H = F + 거래량5배+",            dict(sl=-0.10, ma_exit=True, hold_days=20), 5),
]


def run():
    price_data = load_price_data()
    signals = collect_signals(price_data)
    print(f"시그널 {len(signals)}건 수집 (거래량 5배+ : "
          f"{sum(1 for s in signals if s[3] >= 5)}건)\n")

    cutoff = int(len(signals) * 0.7)
    header = (f"{'설계':<28}{'표본':>6}{'IS기댓값':>9}{'OOS기댓값':>10}{'OOS승률':>8}"
              f"{'OOS PF':>7}{'OOS MDD':>8}{'평균보유':>8}")
    print(header)
    print("-" * len(header))

    rows = []
    for label, kw, min_vol in VARIANTS:
        is_ret, oos_ret, holds = [], [], []
        for i, (d, entry, bars, vr) in enumerate(signals):
            if vr < min_vol:
                continue
            net, held = resolve_exit_ex(entry, bars, **kw)
            (is_ret if i < cutoff else oos_ret).append(net)
            holds.append(held)
        m_is, m_oos = evaluate(is_ret), evaluate(oos_ret)
        if m_oos.get("trades", 0) == 0:
            continue
        avg_hold = sum(holds) / len(holds)
        rows.append((label, m_is, m_oos, avg_hold))
        print(f"{label:<28}{m_oos['trades']:>6}{m_is['expectancy']:>8.3f}%"
              f"{m_oos['expectancy']:>9.3f}%{m_oos['win_rate']:>7.1f}%"
              f"{m_oos['profit_factor']:>7.2f}{m_oos['max_drawdown']:>7.1f}%"
              f"{avg_hold:>7.1f}일")

    print("\n판정 기준: OOS 기댓값 > 0 그리고 PF > 1 인 설계만 실전 후보.")
    positives = [r for r in rows if r[2]["expectancy"] > 0 and r[2]["profit_factor"] > 1]
    if positives:
        best = max(positives, key=lambda r: r[2]["expectancy"])
        print(f"→ 통과 설계 {len(positives)}건. 최상: {best[0]} "
              f"(OOS {best[2]['expectancy']:+.3f}%/매매, PF {best[2]['profit_factor']})")
    else:
        print("→ 통과 설계 없음. 이 진입(거래량 돌파) 계열은 청산을 바꿔도 비용을 이기지 못함.")


if __name__ == "__main__":
    run()
