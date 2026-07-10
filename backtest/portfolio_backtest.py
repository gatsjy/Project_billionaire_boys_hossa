"""
portfolio_backtest.py — 반전 전략 '포트폴리오' 백테스트 (최종 실전 관문)

지금까지는 매매 '건당' 기댓값(+0.4%/매매, PF 1.17)만 봤다. 하지만 실전 가치는
'여러 종목을 병렬로, 한정된 현금으로, 포지션을 나눠' 굴렸을 때의 '계좌곡선'이 결정한다.
건당 얇은 엣지가 분산·복리로 쓸 만한 수익/낙폭이 되는지, 아니면 현금 제약·동시성에
막혀 사라지는지를 일자별 시뮬레이션으로 확인한다.

규칙:
  - 매일: (1) 보유분 청산 판정(갭 인지·RSI반등·ATR손절·타임아웃)  (2) 신규 진입
  - 진입: 전일 반전신호(RSI<30 & 종가>60일선 & ATR%≤8) → 당일 시가 매수
  - 슬롯 초과 시 'RSI 낮은(더 과매도)' 순 우선. 종목당 1포지션.
  - 포지션 크기 = 현재 총자산 / MAX_POS (현금 한도 내). 매 체결 비용 반영.
  - 마킹: 매일 종가로 평가.

정직성: 비용(realistic.CostModel) · look-ahead 없음(신호=전일, 체결=당일시가) ·
전체구간 + 앞70%/뒤30% 분할 · KOSPI 단순보유 벤치마크.
캐시(_cache_prices.pkl) 재사용. 실행: cd backtest && python portfolio_backtest.py
"""

import io
import os
import pickle
import sys

import numpy as np
import pandas as pd
import FinanceDataReader as fdr

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", line_buffering=True)

from reversal_strategy import apply_reversal_strategy, check_exit
from params import REV_HOLD_DAYS
from realistic import DEFAULT_COST

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache_prices.pkl")
INITIAL_CAPITAL = 10_000_000
COST = DEFAULT_COST


def load_prices():
    with open(CACHE, "rb") as f:
        return pickle.load(f)


def build_signals(price_data):
    """종목별 지표 부착 + 빠른 조회용 구조. entries: (entry_date, code, entry_price, signal_rsi)."""
    bars = {}       # code -> {date: (o,h,l,c,rsi,stop_pct)}
    entries = []    # 전일 신호 → 당일 시가 진입
    for code, raw in price_data.items():
        df = apply_reversal_strategy(raw)
        if df.empty:
            continue
        rows = {}
        idx = df.index
        for j in range(len(df)):
            r = df.iloc[j]
            rows[idx[j]] = (float(r["Open"]), float(r["High"]), float(r["Low"]),
                            float(r["Close"]), float(r["RSI"]), float(r["Stop_Pct"]))
        bars[code] = rows
        # 신호일 t → 진입일 t+1
        sig_positions = np.where(df["Buy_Signal"].to_numpy())[0]
        for j in sig_positions:
            if j + 1 < len(df):
                ed = idx[j + 1]
                op = float(df.iloc[j + 1]["Open"])
                if op > 0:
                    entries.append((ed, code, op, float(df.iloc[j]["RSI"]),
                                    float(df.iloc[j + 1].name == ed)))
    entries_by_date = {}
    for ed, code, op, rsi_, _ in entries:
        entries_by_date.setdefault(ed, []).append((code, op, rsi_))
    return bars, entries_by_date


def run_portfolio(price_data, max_pos):
    bars, entries_by_date = build_signals(price_data)
    all_dates = sorted({d for rows in bars.values() for d in rows})

    cash = INITIAL_CAPITAL
    positions = {}   # code -> dict(entry, qty, held, stop_pct, entry_date)
    equity_curve = []
    trades = []

    for d in all_dates:
        # (1) 보유분 청산 판정
        for code in list(positions.keys()):
            p = positions[code]
            bar = bars[code].get(d)
            if bar is None:
                continue
            o, h, l, c, r, _ = bar
            p["held"] += 1
            px, reason = check_exit(p["entry"], h, l, o, c, r, p["stop_pct"])
            if px is None and p["held"] >= REV_HOLD_DAYS:
                px, reason = c, f"타임아웃({REV_HOLD_DAYS}일)"
            if px is not None:
                cash += p["qty"] * px * (1 - COST.sell_fee - COST.tax - COST.slippage)
                trades.append({"code": code, "ret": COST.net_return(p["entry"], px) * 100,
                               "held": p["held"], "reason": reason})
                del positions[code]

        # (2) 신규 진입 (슬롯·현금 한도)
        todays = entries_by_date.get(d, [])
        todays = sorted(todays, key=lambda x: x[2])  # RSI 낮은(과매도 깊은) 순
        equity_now = cash + sum(pp["qty"] * bars[cc].get(d, (0, 0, 0, pp["entry"], 0, 0))[3]
                                for cc, pp in positions.items())
        for code, op, _ in todays:
            if len(positions) >= max_pos or code in positions:
                continue
            target = equity_now / max_pos
            if cash < target * 0.5:      # 현금 부족하면 스킵
                continue
            eff = op * (1 + COST.buy_fee + COST.slippage)
            qty = int(min(target, cash) // eff)
            if qty <= 0:
                continue
            cash -= qty * eff
            stop_pct = bars[code][d][5]
            positions[code] = {"entry": op, "qty": qty, "held": 0,
                               "stop_pct": stop_pct, "entry_date": d}

        # (3) 마킹
        mkt = sum(pp["qty"] * bars[cc].get(d, (0, 0, 0, pp["entry"], 0, 0))[3]
                  for cc, pp in positions.items())
        equity_curve.append((d, cash + mkt, len(positions)))

    ec = pd.DataFrame(equity_curve, columns=["date", "equity", "npos"]).set_index("date")
    return ec, pd.DataFrame(trades)


def metrics(equity: pd.Series):
    equity = equity.dropna()
    if len(equity) < 2:
        return {}
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
    peak = equity.cummax()
    mdd = (equity / peak - 1).min()
    dr = equity.pct_change().dropna()
    sharpe = (dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else 0
    return {"cagr": cagr * 100, "mdd": mdd * 100,
            "calmar": cagr / abs(mdd) if mdd < 0 else float("inf"),
            "sharpe": sharpe, "final": equity.iloc[-1]}


def run():
    price_data = load_prices()

    # KOSPI 벤치마크
    ks = fdr.DataReader("KS11")["Close"]

    print(f"초기자본 {INITIAL_CAPITAL:,}원 · 비용 왕복 {COST.round_trip_drag()*100:.2f}%\n")
    print(f"{'설정':<16}{'최종자산':>16}{'CAGR':>8}{'MDD':>8}{'Calmar':>8}{'Sharpe':>8}"
          f"{'매매수':>7}{'승률':>7}{'평균보유':>7}")
    print("-" * 92)

    for max_pos in (5, 8, 12, 20):
        ec, tr = run_portfolio(price_data, max_pos)
        m = metrics(ec["equity"])
        win = (tr["ret"] > 0).mean() * 100 if len(tr) else 0
        avgh = tr["held"].mean() if len(tr) else 0
        print(f"{'MAX '+str(max_pos)+'종목':<16}{m['final']:>15,.0f}원{m['cagr']:>7.1f}%"
              f"{m['mdd']:>7.1f}%{m['calmar']:>8.2f}{m['sharpe']:>8.2f}"
              f"{len(tr):>7}{win:>6.1f}%{avgh:>6.1f}d")

    # 대표 설정(8종목)으로 train/test 분할 + 벤치마크
    ec, tr = run_portfolio(price_data, 8)
    split = ec.index[int(len(ec) * 0.7)]
    m_tr = metrics(ec["equity"][ec.index <= split])
    m_te = metrics(ec["equity"][ec.index > split])
    ks_p = ks[(ks.index >= ec.index[0]) & (ks.index <= ec.index[-1])]
    m_ks = metrics(ks_p)

    print("\n" + "=" * 92)
    print(f"대표설정 MAX 8종목 — 기간 {ec.index[0].date()} ~ {ec.index[-1].date()}")
    print("=" * 92)
    print(f"  훈련(~{split.date()}) : CAGR {m_tr['cagr']:5.1f}% MDD {m_tr['mdd']:6.1f}% "
          f"Calmar {m_tr['calmar']:4.2f} Sharpe {m_tr['sharpe']:4.2f}")
    print(f"  검증({split.date()}~) : CAGR {m_te['cagr']:5.1f}% MDD {m_te['mdd']:6.1f}% "
          f"Calmar {m_te['calmar']:4.2f} Sharpe {m_te['sharpe']:4.2f}")
    print(f"  [벤치] KOSPI 단순보유 : CAGR {m_ks['cagr']:5.1f}% MDD {m_ks['mdd']:6.1f}% "
          f"Calmar {m_ks['calmar']:4.2f} Sharpe {m_ks['sharpe']:4.2f}")
    print(f"  평균 동시보유 {ec['npos'].mean():.1f}종목 / 최대 {int(ec['npos'].max())} · "
          f"투자노출 {(ec['npos']/8*100).mean():.0f}%")

    print("\n판정: 검증구간 Sharpe>0.5 & Calmar가 KOSPI 이상이면 실전 페이퍼 진입 가치.")


if __name__ == "__main__":
    run()
