"""broker — 매매 실행 어댑터 계층.

봇의 '판단'(index_core_bot·index_trend_strategy)과 '실행'(주문/잔고)을 분리한다.
같은 Broker 인터페이스 뒤에 PaperBroker(가상 장부)와 KiwoomRestBroker(실/모의 계좌)를
두어, config 한 줄("mode")로 페이퍼↔실계좌를 전환한다. 봇은 자신이 어느 쪽인지 몰라도 된다.

  make_broker(config, portfolio) 로 mode 에 맞는 구현체를 돌려받는다.
    mode='paper'        → PaperBroker(portfolio)
    mode='kiwoom_mock'  → KiwoomRestBroker(config, live=False)   # Step 2
    mode='kiwoom_live'  → KiwoomRestBroker(config, live=True)    # Step 2 (+ 안전가드)
"""
from broker.base import Broker, Position, Balance, OrderResult
from broker.paper_broker import PaperBroker

__all__ = ["Broker", "Position", "Balance", "OrderResult", "PaperBroker", "make_broker"]


def make_broker(config: dict, portfolio: dict = None, **kw) -> Broker:
    """config['mode'] 에 맞는 브로커를 생성. portfolio 는 paper 모드에서만 필요."""
    mode = (config or {}).get("mode", "paper")
    if mode == "paper":
        return PaperBroker(portfolio if portfolio is not None else {}, **kw)
    if mode in ("kiwoom_mock", "kiwoom_live"):
        from broker.kiwoom_broker import KiwoomRestBroker   # 지연 임포트(스텁 의존 최소화)
        return KiwoomRestBroker(config, live=(mode == "kiwoom_live"))
    raise ValueError(f"알 수 없는 broker mode '{mode}' (paper|kiwoom_mock|kiwoom_live)")
