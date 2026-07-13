"""
paper_broker.py — 가상 장부 브로커 (Broker 구현체)

현재 index_core_bot 의 페이퍼 매매 동작(비용 반영·평단 갱신·실현손익·이력 기록)을
Broker 인터페이스 뒤로 캡슐화한다. 실계좌 대비를 위해:
  - 현금 부족 → 살 수 있는 만큼만 부분체결(현실 반영)
  - 보유 초과 매도 → 보유분까지만 부분체결
  - 모든 체결 이력에 type/code/qty/eff_price/time/src 기록 → ledger_audit 재생 가능
가격 조회는 price_provider(주입 가능)로 → 오프라인 단위테스트 가능.
"""
import json
import math
from datetime import datetime
from typing import Callable, Optional

from broker.base import Broker, Balance, Position, OrderResult

try:
    from backtest.realistic import CostModel
except ImportError:
    from realistic import CostModel


def _fdr_price(code: str) -> float:
    import FinanceDataReader as fdr
    return float(fdr.DataReader(code)["Close"].iloc[-1])


class PaperBroker(Broker):
    mode = "paper"

    def __init__(self, portfolio: dict, cost: Optional[CostModel] = None,
                 source: str = "paper", price_provider: Optional[Callable[[str], float]] = None):
        self.pf = portfolio
        self.pf.setdefault("cash", float(portfolio.get("initial_capital", 0)))
        self.pf.setdefault("holdings", [])
        self.pf.setdefault("trade_history", [])
        self.cost = cost or CostModel(tax=0.0)   # ETF 거래세 면제 기본
        self.source = source
        self._price_provider = price_provider or _fdr_price

    # --- 조회 ---
    def get_price(self, code: str) -> float:
        return float(self._price_provider(code))

    def get_balance(self) -> Balance:
        positions = [Position(h["code"], h.get("name", h["code"]), h["qty"], h["buy_price"])
                     for h in self.pf["holdings"] if h["qty"] > 0]
        return Balance(cash=float(self.pf["cash"]), positions=positions)

    # --- 실행 ---
    def place_order(self, code: str, side: str, qty: int,
                    price: Optional[float] = None, name: str = "") -> OrderResult:
        side = side.lower()
        if qty <= 0:
            return OrderResult(False, code, side, qty, 0, 0.0, "rejected", reason="수량 0 이하")
        px = float(price) if price is not None else self.get_price(code)
        if px <= 0:
            return OrderResult(False, code, side, qty, 0, px, "rejected", reason="가격 이상치")

        if side == "buy":
            return self._buy(code, name or code, qty, px)
        elif side == "sell":
            return self._sell(code, name or code, qty, px)
        return OrderResult(False, code, side, qty, 0, px, "rejected", reason=f"알 수 없는 side '{side}'")

    def _buy(self, code, name, qty, px) -> OrderResult:
        eff = round(px * (1 + self.cost.buy_fee + self.cost.slippage), 2)
        affordable = int(self.pf["cash"] // eff)          # 현금으로 살 수 있는 최대
        fill = min(qty, affordable)
        if fill <= 0:
            return OrderResult(False, code, "buy", qty, 0, eff, "rejected",
                               reason=f"현금 부족(가용 {self.pf['cash']:,.0f}, 1주 {eff:,.0f})")
        spend = fill * eff
        self.pf["cash"] -= spend
        hold = next((h for h in self.pf["holdings"] if h["code"] == code), None)
        if hold:
            tot = hold["buy_price"] * hold["qty"] + spend
            hold["qty"] += fill
            hold["buy_price"] = tot / hold["qty"]
        else:
            self.pf["holdings"].append({"code": code, "name": name, "buy_price": eff,
                                        "qty": fill, "buy_date": datetime.now().strftime("%Y-%m-%d")})
        status = "filled" if fill == qty else "partial"
        self._record("buy", code, name, px, eff, fill)
        return OrderResult(True, code, "buy", qty, fill, eff, status, cash_delta=-spend,
                           reason="" if status == "filled" else "현금 한도로 부분체결")

    def _sell(self, code, name, qty, px) -> OrderResult:
        eff = round(px * (1 - self.cost.sell_fee - self.cost.tax - self.cost.slippage), 2)
        held = sum(h["qty"] for h in self.pf["holdings"] if h["code"] == code)
        fill = min(qty, held)
        if fill <= 0:
            return OrderResult(False, code, "sell", qty, 0, eff, "rejected",
                               reason=f"보유 없음(보유 {held})")
        proceeds = fill * eff
        realized = 0.0
        for h in list(self.pf["holdings"]):
            if h["code"] != code:
                continue
            realized = (eff - h["buy_price"]) * fill
            h["qty"] -= fill
            if h["qty"] <= 0:
                self.pf["holdings"].remove(h)
            break
        self.pf["cash"] += proceeds
        status = "filled" if fill == qty else "partial"
        self._record("sell", code, name, px, eff, fill, realized)
        return OrderResult(True, code, "sell", qty, fill, eff, status, cash_delta=proceeds,
                           realized_pnl=round(realized, 0),
                           reason="" if status == "filled" else "보유 한도로 부분체결")

    def _record(self, ty, code, name, price, eff, qty, realized=None):
        rec = {"type": ty, "code": code, "name": name,
               "date": datetime.now().strftime("%Y-%m-%d"),
               "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "src": self.source, "price": price, "eff_price": eff, "qty": qty}
        if realized is not None:
            rec["realized_pnl"] = round(realized, 0)
        self.pf["trade_history"].append(rec)

    # --- 영속화 ---
    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.pf, f, ensure_ascii=False, indent=2)

    @classmethod
    def from_file(cls, path: str, **kw) -> "PaperBroker":
        with open(path, "r", encoding="utf-8") as f:
            return cls(json.load(f), **kw)
