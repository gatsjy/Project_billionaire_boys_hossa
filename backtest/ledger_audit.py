"""
ledger_audit.py — 장부 자가감사(재생 검증) 순수 로직 (네트워크/부작용 없음)

[왜] 이 페이퍼 장부는 장차 실계좌 연동의 기반이다. 실계좌라면 "이력으로 재구성한
보유·현금"과 "장부에 적힌 보유·현금"이 원 단위까지 일치해야 하고, 불일치 상태에서
매매를 계속하는 것은 사고다. 옛 테마/인버스 장부는 매도 기록에 수량이 없어 감사
불능이었다(2026-07-13 판정) — 그 교훈을 시스템으로 만든 것.

[규칙]
  - 모든 매매 기록은 type/code/qty/eff_price 를 반드시 갖는다(불완전 기록 = 감사 실패).
  - 재생(replay)한 보유 수량이 장부 보유와 정확히 일치해야 한다.
  - 재생 현금은 기록 반올림(2dp) 누적 오차 한도 안에서 장부 현금과 일치해야 한다.
  - 감사 실패 시 봇은 매매하지 않는다(호출부 책임).
"""

REQUIRED_FIELDS = ("type", "code", "qty", "eff_price")


def replay_ledger(initial_capital, trade_history):
    """매매 이력을 처음부터 재생 → (종목별 수량 dict, 현금, 문제 목록). 순수 함수."""
    pos = {}
    cash = float(initial_capital)
    problems = []
    for i, t in enumerate(trade_history):
        missing = [f for f in REQUIRED_FIELDS if t.get(f) in (None, "")]
        if missing:
            problems.append(f"기록 #{i} 필드 누락 {missing}: type={t.get('type')} code={t.get('code')}")
            continue
        ty = str(t["type"]).lower()
        code, qty, eff = t["code"], float(t["qty"]), float(t["eff_price"])
        if qty <= 0 or eff <= 0:
            problems.append(f"기록 #{i} 값 이상(qty={qty}, eff_price={eff})")
            continue
        if ty == "buy":
            cash -= qty * eff
            pos[code] = pos.get(code, 0) + qty
        elif ty == "sell":
            cash += qty * eff
            pos[code] = pos.get(code, 0) - qty
            if pos[code] < 0:
                problems.append(f"기록 #{i} {code} 매도 후 수량 음수({pos[code]})")
        else:
            problems.append(f"기록 #{i} 알 수 없는 type '{t['type']}'")
    return pos, cash, problems


def audit_ledger(pf, cash_tol_per_trade=0.5, cash_tol_min=1.0):
    """장부 전체 감사 → (ok: bool, issues: list[str]).

    cash 허용오차 = max(cash_tol_min, 기록수 × cash_tol_per_trade)
      — eff_price 가 2dp 반올림 저장되므로 기록당 최대 ±0.5원 누적을 허용.
    """
    issues = []
    hist = pf.get("trade_history", [])
    derived_pos, derived_cash, problems = replay_ledger(pf.get("initial_capital", 0), hist)
    issues.extend(problems)

    stored_pos = {}
    for h in pf.get("holdings", []):
        stored_pos[h["code"]] = stored_pos.get(h["code"], 0) + h["qty"]

    for code in sorted(set(derived_pos) | set(stored_pos)):
        d = derived_pos.get(code, 0)
        s = stored_pos.get(code, 0)
        if abs(d - s) > 1e-9:
            issues.append(f"보유 불일치 {code}: 이력 재생 {d} vs 장부 {s}")

    tol = max(cash_tol_min, len(hist) * cash_tol_per_trade)
    diff = pf.get("cash", 0.0) - derived_cash
    if abs(diff) > tol:
        issues.append(f"현금 불일치: 이력 재생 {derived_cash:,.0f} vs 장부 {pf.get('cash', 0):,.0f} "
                      f"(차이 {diff:+,.0f}원, 허용 ±{tol:.0f}원)")
    return (len(issues) == 0), issues
