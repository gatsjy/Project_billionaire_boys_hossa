"""
index_core_bot.py — 지수 추세추종 코어 봇 (Phase 14, 라이브 메인)

hossa 재편: 개별주 자동매매(테마 돌파·인버스·스윙 반전)가 정직한 검증에서 모두 지수에
패배(progress.md §9~13). 검증된 유일 방향인 '지수 추세추종'을 라이브 코어로 승격한다.

동작(매일 장 마감 후 1회):
  1) KODEX 200 추세 판별(200일선 ±2% 밴드) → 목표비중(RISK_ON 100% / RISK_OFF 20%)
  2) 별도 장부(portfolio_index.json)를 목표비중으로 리밸런싱 — ETF 비용(거래세 면제) 반영
  3) 판단·매매·평가를 이메일 리포트로 발송
안전장치: 별도 락(index 전용), 원자적 저장, 1시간 중복실행 방지, 목표±5%p 이내면 매매 생략.
기존 테마/인버스 장부(portfolio.json)와 완전히 분리 — 서로 간섭 없음.
"""

import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

from backtest.index_trend_strategy import get_index_status
from backtest.realistic import CostModel
from backtest.params import INDEX_CODE, INDEX_NAME, INDEX_REBAL_TOL, INDEX_PORTFOLIO_FILE
from portfolio_manager import load_portfolio, save_portfolio, portfolio_lock
from notifier.email_sender import send_radar_alert

# ETF 는 증권거래세 면제 → tax=0 (개별주 기본 0.15%와 다름)
ETF_COST = CostModel(tax=0.0)
INDEX_LOCK = 'portfolio_index.lock'


def plan_rebalance(qty, cash, price, target_weight, cost=ETF_COST, tol=INDEX_REBAL_TOL):
    """목표비중까지의 리밸런싱 계획(비용 반영). 순수 함수."""
    value = qty * price
    total = cash + value
    base = {"current_weight": (value / total if total > 0 else 0.0),
            "target_weight": target_weight}
    if total <= 0 or price <= 0:
        return {**base, "action": "HOLD", "qty": 0, "eff_price": price, "cash_delta": 0.0}
    gap = target_weight - base["current_weight"]
    if abs(gap) < tol:
        return {**base, "action": "HOLD", "qty": 0, "eff_price": price, "cash_delta": 0.0}
    if gap > 0:
        eff = price * (1 + cost.buy_fee + cost.slippage)
        budget = min(gap * total, cash)
        q = int(budget // eff)
        if q <= 0:
            return {**base, "action": "HOLD", "qty": 0, "eff_price": eff, "cash_delta": 0.0}
        return {**base, "action": "BUY", "qty": q, "eff_price": eff, "cash_delta": -q * eff}
    eff = price * (1 - cost.sell_fee - cost.tax - cost.slippage)
    q = min(qty, int((-gap) * total // price))
    if q <= 0:
        return {**base, "action": "HOLD", "qty": 0, "eff_price": eff, "cash_delta": 0.0}
    return {**base, "action": "SELL", "qty": q, "eff_price": eff, "cash_delta": q * eff}


def run_index_core_bot():
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 지수 추세추종 코어 봇 가동...")
    try:
        st = get_index_status(INDEX_CODE)
    except Exception as e:
        print(f"데이터 조회/검증 실패: {e}")
        return
    print(f"판단: {st['reason']}")

    with portfolio_lock(INDEX_LOCK):
        pf = load_portfolio(INDEX_PORTFOLIO_FILE)

        # 1시간 중복실행 방지
        last = pf.get("last_run_time")
        if last and (datetime.now() - datetime.strptime(last, "%Y-%m-%d %H:%M")).total_seconds() < 3600:
            print(f"⚠️ 최근 1시간 내 실행됨({last}). 중복 방지.")
            return

        hold = next((h for h in pf["holdings"] if h["code"] == INDEX_CODE), None)
        qty = hold["qty"] if hold else 0
        today = datetime.today().strftime("%Y-%m-%d")

        plan = plan_rebalance(qty, pf["cash"], st["price"], st["target_weight"])
        trade_msg = "목표 비중 유지 — 매매 없음."

        if plan["action"] == "BUY":
            amt = -plan["cash_delta"]
            pf["cash"] += plan["cash_delta"]
            if hold:
                tot = hold["buy_price"] * hold["qty"] + amt
                hold["qty"] += plan["qty"]
                hold["buy_price"] = tot / hold["qty"]
            else:
                pf["holdings"].append({"code": INDEX_CODE, "name": INDEX_NAME,
                                       "buy_price": plan["eff_price"], "qty": plan["qty"],
                                       "buy_date": today})
            pf["trade_history"].append({"type": "buy", "code": INDEX_CODE, "name": INDEX_NAME,
                                        "date": today, "price": st["price"],
                                        "eff_price": round(plan["eff_price"], 2),
                                        "qty": plan["qty"], "reason": st["action"]})
            trade_msg = (f"🔵 리밸런싱 매수 {plan['qty']}주 "
                         f"(비중 {plan['current_weight']:.0%}→목표 {plan['target_weight']:.0%}) "
                         f"실지출 {amt:,.0f}원")

        elif plan["action"] == "SELL":
            proceeds = plan["cash_delta"]
            pf["cash"] += proceeds
            realized = 0.0
            for h in list(pf["holdings"]):
                if h["code"] != INDEX_CODE:
                    continue
                realized += (plan["eff_price"] - h["buy_price"]) * plan["qty"]
                h["qty"] -= plan["qty"]
                if h["qty"] <= 0:
                    pf["holdings"].remove(h)
                break
            pf["trade_history"].append({"type": "sell", "code": INDEX_CODE, "name": INDEX_NAME,
                                        "date": today, "price": st["price"],
                                        "eff_price": round(plan["eff_price"], 2),
                                        "qty": plan["qty"], "realized_pnl": round(realized, 0),
                                        "reason": st["action"]})
            trade_msg = (f"🟠 리밸런싱 매도 {plan['qty']}주 "
                         f"(비중 {plan['current_weight']:.0%}→목표 {plan['target_weight']:.0%}) "
                         f"실현손익 {realized:+,.0f}원 / 실수취 {proceeds:,.0f}원")

        pf["last_run_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_portfolio(pf, INDEX_PORTFOLIO_FILE)

        qty_after = sum(h["qty"] for h in pf["holdings"] if h["code"] == INDEX_CODE)
        total_after = pf["cash"] + qty_after * st["price"]

    print(trade_msg)

    body = f"""*[지수 추세추종 코어 데일리]*
{datetime.now():%Y-%m-%d %H:%M}

[시장 지표]
- {INDEX_NAME} 현재가: {st['price']:,.0f}원
- 200일선: {st['sma_200']:,.0f}원 / 이격도 {st['disparity']:+.1f}%

[판단] {st['action']}
{st['reason']}

{trade_msg}

[포트폴리오]
- 총자산 {total_after:,.0f}원 / 현금 {pf['cash']:,.0f}원
- {INDEX_NAME} {qty_after}주 (비중 {(qty_after*st['price']/total_after if total_after else 0):.0%})
"""
    try:
        send_radar_alert(f"[{st['action']}] 지수 코어 리밸런싱", body)
        print("이메일 발송 완료.")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")


if __name__ == "__main__":
    run_index_core_bot()
