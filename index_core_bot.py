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
from backtest.data_integrity import DataIntegrityError
from backtest.realistic import CostModel
from backtest.ledger_audit import audit_ledger
from backtest.params import (INDEX_CODE, INDEX_NAME, INDEX_REBAL_TOL,
                             INDEX_PORTFOLIO_FILE, INDEX_MAX_BUY_STEP,
                             INDEX_BOND_CODE, INDEX_BOND_NAME,
                             INDEX_HEDGE_CODE, INDEX_HEDGE_NAME, INDEX_HEDGE_FRAC,
                             INDEX_TAIL_HEDGE_FRAC)
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


def _apply(pf, code, name, price, plan, today, msgs, source="manual"):
    """계획을 장부에 반영하고 사람이 읽는 메시지를 append.

    ★ 실계좌 연동 대비 회계 규칙: cash_delta 는 'round(eff,2) × qty' 로 계산해
      기록(eff_price 2dp)과 현금 흐름이 원 단위까지 재생 가능해야 한다(ledger_audit).
      기록엔 실행 시각·주체(src)도 남긴다 — 무단/이중 실행 추적용.
    """
    if plan["action"] == "HOLD":
        return
    hold = next((h for h in pf["holdings"] if h["code"] == code), None)
    eff, q = round(plan["eff_price"], 2), plan["qty"]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if plan["action"] == "BUY":
        pf["cash"] -= q * eff
        if hold:
            tot = hold["buy_price"] * hold["qty"] + q * eff
            hold["qty"] += q
            hold["buy_price"] = tot / hold["qty"]
        else:
            pf["holdings"].append({"code": code, "name": name, "buy_price": eff,
                                   "qty": q, "buy_date": today})
        pf["trade_history"].append({"type": "buy", "code": code, "name": name,
                                    "date": today, "time": ts, "src": source,
                                    "price": price, "eff_price": eff, "qty": q})
        msgs.append(f"🔵 {name} 매수 {q}주 ({q*eff:,.0f}원)")
    else:  # SELL
        pf["cash"] += q * eff
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
                                    "date": today, "time": ts, "src": source,
                                    "price": price, "eff_price": eff,
                                    "qty": q, "realized_pnl": round(realized, 0)})
        msgs.append(f"🟠 {name} 매도 {q}주 (실현 {realized:+,.0f}원 / 수취 {q*eff:,.0f}원)")


def run_index_core_bot(source="manual"):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 지수 추세추종 코어 봇 가동... (source={source})")
    try:
        st = get_index_status(INDEX_CODE)
        bond_px = float(fdr.DataReader(INDEX_BOND_CODE)["Close"].iloc[-1])
        hedge_px = float(fdr.DataReader(INDEX_HEDGE_CODE)["Close"].iloc[-1])
    except DataIntegrityError as e:
        # 시세가 신뢰 불가 — 가짜 데이터로 매매하지 않는다(실계좌 연동 시 생명줄).
        print(f"🔴 시세 무결성 실패 — 매매 중단: {e}")
        try:
            send_radar_alert("🔴 [시세 무결성 실패] 지수 코어 매매 중단",
                             "시세 데이터가 신뢰 불가로 판정되어 오늘 매매를 중단했습니다.\n\n"
                             f"{e}\n\n브로커 앱에서 실제 시세를 확인하세요. "
                             "데이터가 정상화되면 다음 실행에서 자동 재개됩니다.")
        except Exception:
            pass
        return
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

        # ★ 매매 전 장부 자가감사 — 실계좌 연동 대비 원칙: 검증 안 되는 장부 위에서 매매하지 않는다.
        ok, issues = audit_ledger(pf)
        if not ok:
            print("🔴 장부 감사 실패 — 매매 중단:")
            for msg in issues[:8]:
                print(f"   - {msg}")
            try:
                send_radar_alert("🔴 [장부 감사 실패] 지수 코어 매매 중단",
                                 "장부-이력 재생 검증에 실패해 오늘 매매를 중단했습니다.\n\n"
                                 + "\n".join(f"- {m}" for m in issues[:10])
                                 + "\n\n장부(portfolio_index.json)를 점검 후 재실행하세요.")
            except Exception:
                pass
            return

        def qty_of(code):
            return sum(h["qty"] for h in pf["holdings"] if h["code"] == code)

        prices = {INDEX_CODE: eq_price, INDEX_HEDGE_CODE: hedge_px, INDEX_BOND_CODE: bond_px}
        total = pf["cash"] + sum(qty_of(c) * p for c, p in prices.items())

        # 목표: 상시 tail hedge(항상 달러)를 먼저 떼고, 나머지(base)를 추세로 운용.
        #   주식 = 앙상블 비중 × base, 방어(1-주식)×base 를 헷지(달러):단기채로 분할.
        #   헷지 = 상시 + 조건부. → 강세장에도 소액 달러가 초기 급락을 쿠션.
        base = 1 - INDEX_TAIL_HEDGE_FRAC
        defensive = (1 - eq_target_w) * base * total
        targets = {
            INDEX_CODE: eq_target_w * base * total,
            INDEX_HEDGE_CODE: INDEX_TAIL_HEDGE_FRAC * total + INDEX_HEDGE_FRAC * defensive,
            INDEX_BOND_CODE: (1 - INDEX_HEDGE_FRAC) * defensive,
        }
        names = {INDEX_CODE: INDEX_NAME, INDEX_HEDGE_CODE: INDEX_HEDGE_NAME, INDEX_BOND_CODE: INDEX_BOND_NAME}
        caps = {INDEX_CODE: INDEX_MAX_BUY_STEP * total}   # 주식만 분할 상한, 방어는 즉시
        tol_val = INDEX_REBAL_TOL * total
        msgs = []

        legs = [INDEX_CODE, INDEX_HEDGE_CODE, INDEX_BOND_CODE]
        # 1) 매도 먼저(현금 확보): 각 자산 초과분 정리(상한 없음).
        for code in legs:
            price, cur_qty, tgt = prices[code], qty_of(code), targets[code]
            if cur_qty * price - tgt > tol_val:
                _apply(pf, code, names[code], price, plan_leg(cur_qty, price, tgt, pf["cash"]),
                       today, msgs, source)
        # 2) 매수(현금 배분): 주식은 분할 상한, 헷지·단기채는 나머지 현금으로.
        for code in legs:
            price, cur_qty, tgt = prices[code], qty_of(code), targets[code]
            if tgt - cur_qty * price > tol_val:
                _apply(pf, code, names[code], price,
                       plan_leg(cur_qty, price, tgt, pf["cash"], max_buy_val=caps.get(code)),
                       today, msgs, source)

        pf["last_run_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_portfolio(pf, INDEX_PORTFOLIO_FILE)

        aft = {c: qty_of(c) for c in legs}
        total_after = pf["cash"] + sum(aft[c] * prices[c] for c in legs)

    trade_msg = "\n".join(msgs) if msgs else "목표 비중 이내 — 매매 없음."
    print(trade_msg)

    def line(code):
        q, p = aft[code], prices[code]
        return f"- {names[code]} {q}주 (비중 {(q*p/total_after if total_after else 0):.0%})"
    body = f"""*[지수 추세추종 코어 데일리]*
{datetime.now():%Y-%m-%d %H:%M}

[판단] {st['action']} · 주식 목표 {eq_target_w:.0%} / 방어 {1-eq_target_w:.0%}
(방어 = 달러헷지 {INDEX_HEDGE_FRAC:.0%} + 단기채 {1-INDEX_HEDGE_FRAC:.0%})
{st['reason']}

[리밸런싱]
{trade_msg}

[포트폴리오] 총자산 {total_after:,.0f}원
{line(INDEX_CODE)}
{line(INDEX_HEDGE_CODE)}
{line(INDEX_BOND_CODE)}
- 현금 {pf['cash']:,.0f}원
"""
    try:
        send_radar_alert(f"[{st['action']}] 지수 코어 리밸런싱", body)
        print("이메일 발송 완료.")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")


if __name__ == "__main__":
    # 실행주체 기록: 스케줄러 런처는 --source scheduler 를 넘긴다. 그 외는 manual.
    src = "manual"
    if "--source" in sys.argv:
        i = sys.argv.index("--source")
        if i + 1 < len(sys.argv):
            src = sys.argv[i + 1]
    run_index_core_bot(source=src)
