"""
index_core_bot.py — 지수 추세추종 코어 봇 (Phase 14 재편 + Phase 16 검증 개선)

hossa 재편: 개별주 자동매매가 정직한 검증에서 모두 지수에 패배(progress.md §9~13) →
지수 추세추종을 라이브 코어로. 이어 검증된 개선 2종을 적용(§16):
  A. 방어 슬리브: RISK_OFF 비중을 현금(0%) 대신 KODEX 단기채권에 → 캐리 확보.
  B. 이평 앙상블(120/150/200): 목표비중을 0.2~1.0 연속화 → 박스장 휩쏘·단일MA 취약성 완화.
  [검증] A+B 훈련 Calmar 0.21→0.38, 검증 1.07→1.18, 훈련 MDD -20.3%→-15.1% (양 구간 개선).

동작(일 1회): 주식 목표비중(앙상블) + 방어 목표비중(1-주식)으로 2자산 리밸런싱.
  - 매수(주식 비중 확대)는 1회 max_buy_step 만큼 분할, 방어(축소)는 즉시.
  - ETF 비용(거래세 면제, tax=0) 반영. 별도 장부/락, 1시간 중복실행 방지.
"""

import sys
from datetime import datetime

import FinanceDataReader as fdr

sys.stdout.reconfigure(encoding="utf-8")

from backtest.index_trend_strategy import get_index_status
from backtest.realistic import CostModel
from backtest.params import (INDEX_CODE, INDEX_NAME, INDEX_REBAL_TOL,
                             INDEX_PORTFOLIO_FILE, INDEX_MAX_BUY_STEP,
                             INDEX_BOND_CODE, INDEX_BOND_NAME)
from portfolio_manager import load_portfolio, save_portfolio, portfolio_lock
from notifier.email_sender import send_radar_alert

ETF_COST = CostModel(tax=0.0)   # ETF 증권거래세 면제
INDEX_LOCK = 'portfolio_index.lock'


def plan_leg(cur_qty, price, target_val, cash_avail, max_buy_val=None, cost=ETF_COST):
    """한 자산을 목표금액으로 이동하는 주문 계획(비용 반영). 순수 함수.
    반환: dict(action HOLD/BUY/SELL, qty, eff_price, cash_delta)
    max_buy_val: 매수 상한(분할). 매도는 상한 없음.
    """
    cur_val = cur_qty * price
    gap = target_val - cur_val
    hold = {"action": "HOLD", "qty": 0, "eff_price": price, "cash_delta": 0.0}
    if price <= 0:
        return hold
    if gap > 0:  # 매수
        budget = gap if max_buy_val is None else min(gap, max_buy_val)
        budget = min(budget, cash_avail)
        eff = price * (1 + cost.buy_fee + cost.slippage)
        q = int(budget // eff)
        if q <= 0:
            return hold
        return {"action": "BUY", "qty": q, "eff_price": eff, "cash_delta": -q * eff}
    else:        # 매도
        eff = price * (1 - cost.sell_fee - cost.tax - cost.slippage)
        q = min(cur_qty, round((-gap) / price))
        if q <= 0:
            return hold
        return {"action": "SELL", "qty": q, "eff_price": eff, "cash_delta": q * eff}


def _apply(pf, code, name, price, plan, today, msgs):
    """계획을 장부에 반영하고 사람이 읽는 메시지를 append."""
    if plan["action"] == "HOLD":
        return
    hold = next((h for h in pf["holdings"] if h["code"] == code), None)
    eff, q = plan["eff_price"], plan["qty"]
    pf["cash"] += plan["cash_delta"]
    if plan["action"] == "BUY":
        if hold:
            tot = hold["buy_price"] * hold["qty"] + q * eff
            hold["qty"] += q
            hold["buy_price"] = tot / hold["qty"]
        else:
            pf["holdings"].append({"code": code, "name": name, "buy_price": eff,
                                   "qty": q, "buy_date": today})
        pf["trade_history"].append({"type": "buy", "code": code, "name": name,
                                    "date": today, "price": price, "eff_price": round(eff, 2),
                                    "qty": q})
        msgs.append(f"🔵 {name} 매수 {q}주 ({q*eff:,.0f}원)")
    else:  # SELL
        realized = 0.0
        for h in list(pf["holdings"]):
            if h["code"] != code:
                continue
            realized = (eff - h["buy_price"]) * q
            h["qty"] -= q
            if h["qty"] <= 0:
                pf["holdings"].remove(h)
            break
        pf["trade_history"].append({"type": "sell", "code": code, "name": name,
                                    "date": today, "price": price, "eff_price": round(eff, 2),
                                    "qty": q, "realized_pnl": round(realized, 0)})
        msgs.append(f"🟠 {name} 매도 {q}주 (실현 {realized:+,.0f}원 / 수취 {q*eff:,.0f}원)")


def run_index_core_bot():
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 지수 추세추종 코어 봇 가동...")
    try:
        st = get_index_status(INDEX_CODE)
        bond_px = float(fdr.DataReader(INDEX_BOND_CODE)["Close"].iloc[-1])
    except Exception as e:
        print(f"데이터 조회/검증 실패: {e}")
        return
    eq_price, eq_target_w = st["price"], st["target_weight"]
    print(f"판단: {st['reason']}")

    today = datetime.today().strftime("%Y-%m-%d")
    with portfolio_lock(INDEX_LOCK):
        pf = load_portfolio(INDEX_PORTFOLIO_FILE)
        last = pf.get("last_run_time")
        if last and (datetime.now() - datetime.strptime(last, "%Y-%m-%d %H:%M")).total_seconds() < 3600:
            print(f"⚠️ 최근 1시간 내 실행됨({last}). 중복 방지.")
            return

        def qty_of(code):
            return sum(h["qty"] for h in pf["holdings"] if h["code"] == code)
        eq_qty, bond_qty = qty_of(INDEX_CODE), qty_of(INDEX_BOND_CODE)

        total = pf["cash"] + eq_qty * eq_price + bond_qty * bond_px
        eq_target_val = eq_target_w * total
        bond_target_val = (1 - eq_target_w) * total
        tol_val = INDEX_REBAL_TOL * total
        msgs = []

        # 1) 매도 먼저(현금 확보): 초과분 정리. 주식은 축소=방어이므로 상한 없음.
        for code, name, price, cur_qty, tgt in (
                (INDEX_CODE, INDEX_NAME, eq_price, eq_qty, eq_target_val),
                (INDEX_BOND_CODE, INDEX_BOND_NAME, bond_px, bond_qty, bond_target_val)):
            if cur_qty * price - tgt > tol_val:
                _apply(pf, code, name, price, plan_leg(cur_qty, price, tgt, pf["cash"]), today, msgs)

        # 2) 매수(현금 배분): 주식은 분할 상한, 방어(단기채)는 나머지 현금으로.
        eq_qty = qty_of(INDEX_CODE)
        if eq_target_val - eq_qty * eq_price > tol_val:
            _apply(pf, INDEX_CODE, INDEX_NAME, eq_price,
                   plan_leg(eq_qty, eq_price, eq_target_val, pf["cash"],
                            max_buy_val=INDEX_MAX_BUY_STEP * total), today, msgs)
        bond_qty = qty_of(INDEX_BOND_CODE)
        if bond_target_val - bond_qty * bond_px > tol_val:
            _apply(pf, INDEX_BOND_CODE, INDEX_BOND_NAME, bond_px,
                   plan_leg(bond_qty, bond_px, bond_target_val, pf["cash"]), today, msgs)

        pf["last_run_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_portfolio(pf, INDEX_PORTFOLIO_FILE)

        eq_after, bond_after = qty_of(INDEX_CODE), qty_of(INDEX_BOND_CODE)
        total_after = pf["cash"] + eq_after * eq_price + bond_after * bond_px

    trade_msg = "\n".join(msgs) if msgs else "목표 비중 이내 — 매매 없음."
    print(trade_msg)

    body = f"""*[지수 추세추종 코어 데일리]*
{datetime.now():%Y-%m-%d %H:%M}

[판단] {st['action']} · 주식 목표 {eq_target_w:.0%} / 방어 {1-eq_target_w:.0%}
{st['reason']}

[리밸런싱]
{trade_msg}

[포트폴리오] 총자산 {total_after:,.0f}원
- {INDEX_NAME} {eq_after}주 (비중 {(eq_after*eq_price/total_after if total_after else 0):.0%})
- {INDEX_BOND_NAME} {bond_after}주 (비중 {(bond_after*bond_px/total_after if total_after else 0):.0%})
- 현금 {pf['cash']:,.0f}원
"""
    try:
        send_radar_alert(f"[{st['action']}] 지수 코어 리밸런싱", body)
        print("이메일 발송 완료.")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")


if __name__ == "__main__":
    run_index_core_bot()
