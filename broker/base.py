"""
base.py — 브로커 추상 인터페이스 + 공용 데이터 타입 (순수, 네트워크 없음)

봇이 실행 계층에 요구하는 최소 계약. 구현체(PaperBroker/KiwoomRestBroker)는 이 인터페이스만
만족하면 되고, 봇은 구현체를 몰라도 된다. 실계좌 대비를 위해 '부분체결/미체결/거부'를
1급 시민으로 모델링한다(페이퍼도 현금 부족·보유 초과 시 부분체결로 처리).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Position:
    code: str
    name: str
    qty: float
    avg_price: float          # 취득단가(비용 포함)

    def value(self, price: float) -> float:
        return self.qty * price


@dataclass
class Balance:
    cash: float
    positions: list           # list[Position]

    def position(self, code: str) -> Optional["Position"]:
        return next((p for p in self.positions if p.code == code), None)

    def qty_of(self, code: str) -> float:
        p = self.position(code)
        return p.qty if p else 0.0

    def total_value(self, prices: dict) -> float:
        """현금 + 보유평가액. prices: {code: 현재가}."""
        return self.cash + sum(p.value(prices.get(p.code, p.avg_price)) for p in self.positions)


@dataclass
class OrderResult:
    ok: bool                  # 주문이 (일부라도) 체결됐는가
    code: str
    side: str                 # 'buy' | 'sell'
    req_qty: int              # 요청 수량
    filled_qty: int           # 실제 체결 수량(부분체결 가능)
    price: float              # 체결 단가(비용 반영 eff_price)
    status: str               # 'filled' | 'partial' | 'rejected'
    cash_delta: float = 0.0   # 현금 변화(매수 음수/매도 양수, 비용 포함)
    realized_pnl: float = 0.0 # 매도 실현손익(비용 반영)
    reason: str = ""          # 거부/부분 사유
    order_id: Optional[str] = None  # 실계좌 주문번호(페이퍼는 None)
    meta: dict = field(default_factory=dict)


class Broker(ABC):
    """매매 실행 어댑터. 판단은 봇이, 실행/잔고는 브로커가 책임진다."""

    mode: str = "abstract"    # 'paper' | 'kiwoom_mock' | 'kiwoom_live'

    @abstractmethod
    def get_price(self, code: str) -> float:
        """현재가(원). 조회 실패 시 예외."""

    @abstractmethod
    def get_balance(self) -> Balance:
        """현금 + 보유 포지션."""

    @abstractmethod
    def place_order(self, code: str, side: str, qty: int,
                    price: Optional[float] = None, name: str = "") -> OrderResult:
        """시장가 주문(paper는 price 또는 조회가로 즉시 체결). side: 'buy'|'sell'.
        현금 부족·보유 초과는 부분체결/거부로 반환(예외 아님)."""

    # --- 실계좌 전용(페이퍼는 미구현) ---
    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError("이 브로커는 주문 취소를 지원하지 않습니다.")

    def order_status(self, order_id: str) -> dict:
        raise NotImplementedError("이 브로커는 주문 상태 조회를 지원하지 않습니다.")

    def sync(self) -> None:
        """실계좌: 원장을 브로커 실잔고로 재동기화. 페이퍼는 no-op."""
        return None
