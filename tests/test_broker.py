"""
test_broker.py — 브로커 어댑터 오프라인 단위 테스트 (네트워크 불필요)

핵심 검증:
  - PaperBroker 가 Broker 인터페이스를 만족하고 가격을 주입받아 결정론적으로 체결
  - 현금 부족·보유 초과가 '부분체결/거부'로 안전 처리(실계좌 대비)
  - 체결 후 장부가 ledger_audit 재생검증을 통과(대사 가능)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from broker import PaperBroker, Broker
from broker.base import OrderResult
from backtest.realistic import CostModel
from backtest.ledger_audit import audit_ledger


def _fresh():
    pf = {"initial_capital": 1_000_000, "cash": 1_000_000, "holdings": [], "trade_history": []}
    # 비용 0 브로커로 산수 단순화(무비용). 가격은 고정 주입.
    prices = {"069500": 100_000, "153130": 10_000}
    b = PaperBroker(pf, cost=CostModel(buy_fee=0, sell_fee=0, tax=0, slippage=0),
                    price_provider=lambda c: prices[c])
    return pf, b, prices


class TestPaperBroker(unittest.TestCase):
    def test_is_broker(self):
        _, b, _ = _fresh()
        self.assertIsInstance(b, Broker)
        self.assertEqual(b.mode, "paper")

    def test_buy_fills_and_updates_balance(self):
        pf, b, _ = _fresh()
        r = b.place_order("069500", "buy", 5, name="KODEX 200")
        self.assertEqual(r.status, "filled")
        self.assertEqual(r.filled_qty, 5)
        bal = b.get_balance()
        self.assertEqual(bal.qty_of("069500"), 5)
        self.assertAlmostEqual(bal.cash, 1_000_000 - 5 * 100_000)

    def test_buy_partial_on_insufficient_cash(self):
        pf, b, _ = _fresh()
        r = b.place_order("069500", "buy", 20, name="KODEX 200")  # 20주=200만 > 100만
        self.assertEqual(r.status, "partial")
        self.assertEqual(r.filled_qty, 10)                        # 100만/10만 = 10주만
        self.assertTrue(r.ok)

    def test_sell_capped_to_holdings(self):
        pf, b, _ = _fresh()
        b.place_order("069500", "buy", 5, name="KODEX 200")
        r = b.place_order("069500", "sell", 8)                    # 보유 5뿐
        self.assertEqual(r.status, "partial")
        self.assertEqual(r.filled_qty, 5)
        self.assertEqual(b.get_balance().qty_of("069500"), 0)

    def test_sell_without_holding_rejected(self):
        _, b, _ = _fresh()
        r = b.place_order("069500", "sell", 1)
        self.assertFalse(r.ok)
        self.assertEqual(r.status, "rejected")

    def test_realized_pnl_on_profit(self):
        pf, b, prices = _fresh()
        b.place_order("069500", "buy", 5)
        prices["069500"] = 110_000                                 # +10% 상승
        r = b.place_order("069500", "sell", 5)
        self.assertAlmostEqual(r.realized_pnl, (110_000 - 100_000) * 5)

    def test_zero_qty_rejected(self):
        _, b, _ = _fresh()
        self.assertFalse(b.place_order("069500", "buy", 0).ok)

    def test_ledger_stays_auditable_after_trades(self):
        # 브로커로 매매한 뒤에도 장부가 이력 재생과 원 단위로 일치해야 한다(실계좌 대사 전제).
        pf, b, prices = _fresh()
        b.place_order("069500", "buy", 5, name="KODEX 200")
        b.place_order("153130", "buy", 3, name="KODEX 단기채")
        prices["069500"] = 105_000
        b.place_order("069500", "sell", 2)
        ok, issues = audit_ledger(pf)
        self.assertTrue(ok, msg=f"감사 실패: {issues}")


class TestBrokerWithCost(unittest.TestCase):
    def test_cost_makes_buy_more_expensive(self):
        pf = {"initial_capital": 1_000_000, "cash": 1_000_000, "holdings": [], "trade_history": []}
        b = PaperBroker(pf, cost=CostModel(buy_fee=0.001, sell_fee=0.001, tax=0, slippage=0.001),
                        price_provider=lambda c: 100_000)
        r = b.place_order("069500", "buy", 1)
        self.assertGreater(r.price, 100_000)          # 체결가 > 시장가(비용 반영)
        self.assertAlmostEqual(r.price, 100_000 * 1.002)


if __name__ == "__main__":
    unittest.main(verbosity=2)
