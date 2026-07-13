"""
kiwoom_broker.py — 키움 REST API 브로커 (Step 2 자리, 현재 미구현 스텁)

[Step 2에서 채울 것 — openapi.kiwoom.com REST API]
  인증:   앱키/시크릿 → 접근토큰 발급(POST /oauth2/token) + 만료 전 갱신.
          앱키/시크릿은 config.json(gitignore)에서 읽는다. 절대 코드/깃에 넣지 않는다.
  잔고:   계좌 예수금·보유 조회 TR → Balance 로 매핑.
  시세:   현재가 조회 TR(또는 WebSocket 실시간).
  주문:   현금영수증 아님 — 주식 주문 TR(매수/매도, 시장가/지정가) → OrderResult.
          주문 후 체결통보(WebSocket) 또는 체결내역 조회로 filled_qty 확정(부분체결 반영).
  안전:   TR 호출한도(초당/일일) 준수, 주문 실패 재시도·타임아웃, mock/live 분리.

  ※ mode='kiwoom_mock'(모의투자)로 충분히 검증한 뒤에만 'kiwoom_live'로 전환.
     실계좌 주문은 사용자 승인·킬스위치·일일 한도 가드를 통과해야 한다(Step 4).
"""
from typing import Optional

from broker.base import Broker, Balance, OrderResult


class KiwoomRestBroker(Broker):
    def __init__(self, config: dict, live: bool = False):
        self.mode = "kiwoom_live" if live else "kiwoom_mock"
        self.config = config          # app_key/secret 등은 여기(=config.json)에서만
        self._token = None
        raise NotImplementedError(
            "KiwoomRestBroker 는 Step 2에서 구현합니다. "
            "먼저 openapi.kiwoom.com 에서 앱키/시크릿·모의투자를 신청하세요.")

    def get_price(self, code: str) -> float:
        raise NotImplementedError

    def get_balance(self) -> Balance:
        raise NotImplementedError

    def place_order(self, code: str, side: str, qty: int,
                    price: Optional[float] = None, name: str = "") -> OrderResult:
        raise NotImplementedError
