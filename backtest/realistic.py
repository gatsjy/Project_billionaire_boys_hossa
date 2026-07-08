"""
realistic.py — 현실적 백테스트 코어 (Gap-aware fills + 비용/세금 + 리스크 지표)

기존 engine.py / simulator.py / optimizer.py 는 세 가지 치명적 왜곡이 있었다.
이 모듈은 그것을 한 곳에서 바로잡아 세 러너가 공유하도록 한다.

  1) 체결가 낙관 편향 (가장 치명적)
     기존: `if low <= buy*(1+sl): profit = sl*100`  → 갭하락으로 시가가 손절선보다
     아래에서 시작해도 무조건 정확히 -1%에 체결된 것으로 기록.
     실제: 시가가 손절선을 하회하면 그 '시가'에 체결된다(-1%가 아니라 -5%일 수 있음).
     이 편향이 -1% 손절 전략을 마법처럼 안전해 보이게 만들었다.
     (expected_profit_loss_log.md 의 모든 손절이 정확히 -1.00%인 것이 그 증거)

  2) 거래비용·세금·슬리피지 0 가정
     한국 시장: 매도 증권거래세(코스닥 0.15%) + 양방향 수수료(~0.015%x2) + 슬리피지.
     539~599회 매매, 78~89%가 소액 손실인 전략에서 비용만으로 기댓값이 음(-)으로 뒤집힌다.

  3) 단리 합산·리스크 무시
     기존 지표는 수익률 단순 합(sum). 복리도, 최대낙폭(MDD)도, 손실연속도 없다.
     승률 10.58% 전략의 실제 고통(연속 손절 20회+)이 숫자에 전혀 드러나지 않았다.

이 모듈은 pandas 만 있으면 시장데이터 없이도 단위테스트가 돌아간다(맨 아래 self-test).
"""

from dataclasses import dataclass
import math


# ---------------------------------------------------------------------------
# 1. 비용 모델 (한국 주식, 2024~ 기준. 필요시 값만 바꾸면 됨)
# ---------------------------------------------------------------------------
@dataclass
class CostModel:
    buy_fee: float = 0.00015     # 매수 수수료 (0.015%)
    sell_fee: float = 0.00015    # 매도 수수료 (0.015%)
    tax: float = 0.0015          # 매도 증권거래세 (코스닥 0.15%)
    slippage: float = 0.001      # 한쪽 슬리피지 (0.1%). 소외/급등주는 더 클 수 있음

    def net_return(self, entry_price: float, exit_price: float) -> float:
        """수수료·세금·슬리피지를 모두 반영한 '실현' 수익률(소수)."""
        eff_buy = entry_price * (1 + self.buy_fee + self.slippage)
        eff_sell = exit_price * (1 - self.sell_fee - self.tax - self.slippage)
        return eff_sell / eff_buy - 1.0

    def round_trip_drag(self) -> float:
        """왕복 비용이 잡아먹는 대략적 수익률(bp 감각용)."""
        return self.buy_fee + self.sell_fee + self.tax + 2 * self.slippage


DEFAULT_COST = CostModel()


# ---------------------------------------------------------------------------
# 2. Gap-aware 청산 체결 (핵심 수정)
# ---------------------------------------------------------------------------
def resolve_exit(entry_price, future_bars, tp, sl, cost=DEFAULT_COST):
    """
    현실적 청산 체결.

    Parameters
    ----------
    entry_price : float          다음날 시가 매수가(엔진에서 정함)
    future_bars : list[dict]     매수 다음날부터 시간순 OHLC. dict 는 Open/High/Low/Close 키.
                                 이미 time-stop 만큼(예: 3개)으로 잘려서 들어온다.
    tp, sl      : float          익절/손절 비율(소수). 예 tp=0.07, sl=-0.02
    cost        : CostModel

    Returns
    -------
    dict(exit_price, gross_pct, net_pct, holding_days, reason)

    체결 규칙 (보수적):
      * 시가가 손절선 하회 → 시가 체결(갭 손절, 실제 손실은 -sl 보다 클 수 있음)
      * 시가가 익절선 상회 → 시가 체결(갭 익절)
      * 장중 저가가 손절선 터치 → 손절선 체결
      * 장중 고가가 익절선 터치 → 익절선 체결
      * 한 봉에서 손절/익절이 동시 도달 가능하면 '손절 먼저'로 가정(경로를 모르므로 최악 가정)
    """
    if not future_bars:
        return None

    stop_price = entry_price * (1 + sl)
    target_price = entry_price * (1 + tp)

    for i, bar in enumerate(future_bars):
        o, h, l = bar["Open"], bar["High"], bar["Low"]
        exit_price = None
        reason = None

        # (a) 갭: 시가가 이미 손절/익절선을 넘어선 채 시작 → 시가 체결
        if o <= stop_price:
            exit_price, reason = o, "손절(갭)"
        elif o >= target_price:
            exit_price, reason = o, "익절(갭)"
        # (b) 장중: 손절 우선(경로 미상 → 최악 가정)
        elif l <= stop_price:
            exit_price, reason = stop_price, "손절"
        elif h >= target_price:
            exit_price, reason = target_price, "익절"

        if exit_price is not None:
            return {
                "exit_price": exit_price,
                "gross_pct": (exit_price - entry_price) / entry_price * 100,
                "net_pct": cost.net_return(entry_price, exit_price) * 100,
                "holding_days": i + 1,
                "reason": reason,
            }

    # 시간 청산: 마지막 봉 종가
    last = future_bars[-1]
    exit_price = last["Close"]
    return {
        "exit_price": exit_price,
        "gross_pct": (exit_price - entry_price) / entry_price * 100,
        "net_pct": cost.net_return(entry_price, exit_price) * 100,
        "holding_days": len(future_bars),
        "reason": "시간청산",
    }


def bars_from_df(df, buy_date, time_stop_days=3):
    """DataFrame(loc[buy_date:]) 에서 매수 다음날부터 time_stop_days 개의 봉을 dict 리스트로."""
    window = df.loc[buy_date:].iloc[1: 1 + time_stop_days]
    return [
        {"Open": r.Open, "High": r.High, "Low": r.Low, "Close": r.Close}
        for r in window.itertuples()
    ]


# ---------------------------------------------------------------------------
# 3. 리스크 지표 (복리 자산곡선 / MDD / Sharpe / Profit Factor)
# ---------------------------------------------------------------------------
def evaluate(net_returns_pct):
    """
    net_returns_pct : list[float]  '비용 반영' 매매별 수익률(%). 시간순.
    한 번에 한 포지션(순차 복리)이라는 단순화 가정으로 자산곡선을 만든다.
    (실제 봇은 종목당 50만원 병렬이지만, 전략의 통계적 우위/낙폭을 보기엔 이 근사가 정직하다.)
    """
    n = len(net_returns_pct)
    if n == 0:
        return {"trades": 0}

    wins = [r for r in net_returns_pct if r > 0]
    losses = [r for r in net_returns_pct if r <= 0]

    win_rate = len(wins) / n * 100
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    expectancy = sum(net_returns_pct) / n  # 비용반영 1회 기댓값(%)

    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    # 복리 자산곡선 & 최대낙폭
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    curve = []
    for r in net_returns_pct:
        equity *= (1 + r / 100)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
        curve.append(equity)
    total_return = (equity - 1) * 100

    # 매매단위 Sharpe (연율화 아님, 상대비교용)
    mean = expectancy
    var = sum((r - mean) ** 2 for r in net_returns_pct) / n
    std = math.sqrt(var)
    sharpe = (mean / std) if std > 0 else 0.0

    # 최대 연속 손실
    max_losing_streak = streak = 0
    for r in net_returns_pct:
        streak = streak + 1 if r <= 0 else 0
        max_losing_streak = max(max_losing_streak, streak)

    return {
        "trades": n,
        "win_rate": round(win_rate, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 3),   # 비용 반영 1회 기댓값(%)
        "profit_factor": round(profit_factor, 2),
        "total_return": round(total_return, 1),  # 복리 누적(%)
        "max_drawdown": round(max_dd * 100, 1),  # MDD(%)
        "sharpe_per_trade": round(sharpe, 3),
        "max_losing_streak": max_losing_streak,
        "equity_curve": curve,
    }


# ---------------------------------------------------------------------------
# self-test: 시장데이터 없이 두 버그(갭 체결·비용)를 수치로 증명
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 64)
    print("realistic.py self-test  (기존 로직 vs 현실 로직 비교)")
    print("=" * 64)

    entry = 1000.0
    tp, sl = 0.07, -0.02  # +7% / -2%

    # 시나리오: 다음날 -6% 갭하락으로 시작(시가 940)해 저가 930까지.
    gapped_down = [{"Open": 940, "High": 945, "Low": 930, "Close": 935}]

    # (구) 로직 재현: low <= stop 이면 무조건 정확히 -2%
    old_pct = sl * 100  # 항상 -2.0%
    # (신) 로직
    new = resolve_exit(entry, gapped_down, tp, sl)

    print(f"\n[갭하락 -6% 시나리오]  익절 +7% / 손절 -2%")
    print(f"  구(舊) 백테스트 기록 손실 : {old_pct:+.2f}%   <- 갭을 무시한 낙관 체결")
    print(f"  현실 총손실(gross)        : {new['gross_pct']:+.2f}%   <- 시가에 체결({new['reason']})")
    print(f"  현실 순손실(net, 비용포함): {new['net_pct']:+.2f}%")
    print(f"  ==> 구 로직은 실손실을 {new['gross_pct'] - old_pct:+.2f}%p 만큼 축소 기록")

    # 비용이 기댓값을 뒤집는지: 승률 22% / 익절 +7 / 손절 -2 인 599매매 근사
    import random
    random.seed(0)
    trades = []
    for _ in range(599):
        if random.random() < 0.222:
            trades.append(DEFAULT_COST.net_return(1000, 1070) * 100)   # 익절
        else:
            trades.append(DEFAULT_COST.net_return(1000, 980) * 100)    # 손절
    m = evaluate(trades)
    gross_exp = 0.222 * 7 + 0.778 * (-2)
    print(f"\n[승률22% / +7% / -2% · 599매매 근사]")
    print(f"  비용무시 기댓값(구 지표) : {gross_exp:+.3f}% / 매매")
    print(f"  비용반영 기댓값(신 지표) : {m['expectancy']:+.3f}% / 매매   "
          f"(왕복비용 ~{DEFAULT_COST.round_trip_drag()*100:.2f}%)")
    print(f"  복리 누적수익            : {m['total_return']:+.1f}%")
    print(f"  최대낙폭(MDD)            : {m['max_drawdown']:.1f}%")
    print(f"  최대 연속손실            : {m['max_losing_streak']}회")
    print(f"  Profit Factor            : {m['profit_factor']}")
    print("=" * 64)
