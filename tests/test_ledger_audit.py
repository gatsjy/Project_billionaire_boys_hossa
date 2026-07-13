"""
test_ledger_audit.py — 장부 자가감사 오프라인 단위 테스트 (네트워크 불필요)

실계좌 연동 대비 원칙: "이력으로 재구성한 보유·현금 = 장부"가 항상 성립해야 하며,
불완전 기록(수량 없는 매도 등)은 감사 실패로 즉시 드러나야 한다.
(옛 테마/인버스 장부가 매도 qty 누락으로 감사 불능이었던 2026-07-13 사고의 재발 방지.)

실행:  python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.ledger_audit import replay_ledger, audit_ledger
import index_core_bot  # noqa: F401 — 임포트 스모크(문법/의존성 오류를 테스트 단계에서 검출)


def _pf(cash, holdings, hist, init=1_000_000):
    return {"initial_capital": init, "cash": cash, "holdings": holdings, "trade_history": hist}


class TestReplay(unittest.TestCase):
    def test_buy_then_sell_roundtrip(self):
        hist = [
            {"type": "buy", "code": "069500", "qty": 10, "eff_price": 100.0},
            {"type": "sell", "code": "069500", "qty": 4, "eff_price": 110.0},
        ]
        pos, cash, problems = replay_ledger(1000.0, hist)
        self.assertEqual(problems, [])
        self.assertEqual(pos["069500"], 6)
        self.assertAlmostEqual(cash, 1000.0 - 1000.0 + 440.0)

    def test_missing_qty_flagged(self):
        # 옛 장부 사고의 재현: 매도 기록에 qty 없음 → 감사 가능해야 함(문제로 표면화)
        hist = [{"type": "sell", "code": "114800", "eff_price": 1005.0}]
        _, _, problems = replay_ledger(0, hist)
        self.assertTrue(problems and "누락" in problems[0])

    def test_oversell_flagged(self):
        hist = [{"type": "sell", "code": "A", "qty": 5, "eff_price": 10.0}]
        _, _, problems = replay_ledger(0, hist)
        self.assertTrue(any("음수" in p for p in problems))


class TestAudit(unittest.TestCase):
    def test_consistent_ledger_passes(self):
        hist = [{"type": "buy", "code": "069500", "qty": 10, "eff_price": 100.0}]
        pf = _pf(cash=1_000_000 - 1000.0,
                 holdings=[{"code": "069500", "name": "KODEX 200", "qty": 10, "buy_price": 100.0}],
                 hist=hist)
        ok, issues = audit_ledger(pf)
        self.assertTrue(ok, issues)

    def test_position_mismatch_fails(self):
        hist = [{"type": "buy", "code": "069500", "qty": 10, "eff_price": 100.0}]
        pf = _pf(cash=1_000_000 - 1000.0,
                 holdings=[{"code": "069500", "name": "KODEX 200", "qty": 7, "buy_price": 100.0}],
                 hist=hist)
        ok, issues = audit_ledger(pf)
        self.assertFalse(ok)
        self.assertTrue(any("보유 불일치" in m for m in issues))

    def test_cash_mismatch_fails(self):
        hist = [{"type": "buy", "code": "069500", "qty": 10, "eff_price": 100.0}]
        pf = _pf(cash=999_999_999.0,
                 holdings=[{"code": "069500", "name": "KODEX 200", "qty": 10, "buy_price": 100.0}],
                 hist=hist)
        ok, issues = audit_ledger(pf)
        self.assertFalse(ok)
        self.assertTrue(any("현금 불일치" in m for m in issues))

    def test_rounding_within_tolerance(self):
        # eff_price 2dp 저장 반올림 오차는 허용돼야 함(기록당 ±0.5원)
        hist = [{"type": "buy", "code": "A", "qty": 3, "eff_price": 100.33}]
        pf = _pf(cash=1_000_000 - 301.0,   # 실제 흐름 300.99 대비 1원 내 차이
                 holdings=[{"code": "A", "name": "A", "qty": 3, "buy_price": 100.33}],
                 hist=hist)
        ok, issues = audit_ledger(pf)
        self.assertTrue(ok, issues)

    def test_live_index_ledger_passes(self):
        """현역 장부 실파일 감사 — 이 테스트가 깨지면 매매 전 게이트도 막힌다."""
        import json
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "portfolio_index.json")
        if not os.path.exists(path):
            self.skipTest("장부 파일 없음")
        pf = json.load(open(path, encoding="utf-8"))
        ok, issues = audit_ledger(pf)
        self.assertTrue(ok, issues)


if __name__ == "__main__":
    unittest.main(verbosity=2)
