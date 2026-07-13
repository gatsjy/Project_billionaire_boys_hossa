"""
kiwoom_broker.py — 키움 REST API 브로커 (모의투자/실전) Broker 구현체

[중요] 이 파일은 공개 스펙에 근거해 작성됐고, **네 모의투자 앱키로 connect_test.py 를
실행해 검증하기 전까지는 미검증**이다. 실계좌(kiwoom_live)는 모의(kiwoom_mock)로
충분히 검증하고 Step 3(대사)·Step 4(킬스위치·한도) 가드를 붙인 뒤에만 사용한다.

[스펙 출처] openapi.kiwoom.com 개발가이드 + 공개 파이썬 래퍼.
  도메인:  모의 https://mockapi.kiwoom.com  /  실전 https://api.kiwoom.com
  인증:    POST /oauth2/token  {grant_type, appkey, secretkey} → {token, expires_dt}
  요청:    POST {path}  헤더 Authorization: Bearer{token}, api-id: <TR>
  TR:      au10001 토큰 · ka10004 현재가 · kt00004 예수금·kt00005 잔고 · kt10000 매수·kt10001 매도
  주문필드: dmst_stex_tp(거래소) stk_cd(종목) ord_qty(수량) trde_tp(매매구분) ord_uv(단가)

  ⚠️ 아래 PATHS(카테고리 경로)와 일부 필드는 로그인 후 공식 개발가이드로 최종 확인 필요.
     불일치 시 이 상수들만 고치면 된다(한 곳에 모아둠).

자격증명은 config.json 의 "kiwoom" 섹션에서만 읽는다(gitignore). 코드/깃에 넣지 않는다.
"""
import time
from datetime import datetime
from typing import Optional

import requests

from broker.base import Broker, Balance, Position, OrderResult

MOCK_DOMAIN = "https://mockapi.kiwoom.com"
LIVE_DOMAIN = "https://api.kiwoom.com"

# TR(api-id) — 공개 스펙 기준
TR_TOKEN = "au10001"
TR_PRICE = "ka10004"       # 현재가(주식호가/시세)
TR_DEPOSIT = "kt00004"     # 예수금/계좌평가
TR_HOLDINGS = "kt00005"    # 체결잔고(보유종목)
TR_BUY = "kt10000"
TR_SELL = "kt10001"

# ⚠️ 카테고리 경로 — 공식 개발가이드로 최종 확인(불일치 시 여기만 수정)
PATHS = {
    "token": "/oauth2/token",
    TR_PRICE: "/api/dostk/mrkcond",
    TR_DEPOSIT: "/api/dostk/acnt",
    TR_HOLDINGS: "/api/dostk/acnt",
    TR_BUY: "/api/dostk/ordr",
    TR_SELL: "/api/dostk/ordr",
}

TRADE_MARKET = "3"         # 매매구분: 시장가(지정가는 "0", 단가 ord_uv 필요)
EXCHANGE_KRX = "KRX"


class KiwoomError(Exception):
    pass


class KiwoomRestBroker(Broker):
    def __init__(self, config: dict, live: bool = False, timeout: int = 10):
        kw = (config or {}).get("kiwoom", {})
        self.app_key = kw.get("app_key")
        self.secret_key = kw.get("secret_key")
        self.account = kw.get("account_no", "")
        if not self.app_key or not self.secret_key:
            raise KiwoomError("config.json 의 kiwoom.app_key / secret_key 가 필요합니다. "
                              "openapi.kiwoom.com 에서 발급 후 넣으세요.")
        self.live = live
        self.mode = "kiwoom_live" if live else "kiwoom_mock"
        self.domain = LIVE_DOMAIN if live else MOCK_DOMAIN
        self.timeout = timeout
        self._token = None
        self._token_exp = 0.0
        self._last_call = 0.0
        self._min_interval = 0.25       # TR 호출한도 완화(초당 4회 이하로)

    # --- 인증 ---
    def _ensure_token(self):
        if self._token and time.time() < self._token_exp - 60:
            return
        url = self.domain + PATHS["token"]
        body = {"grant_type": "client_credentials",
                "appkey": self.app_key, "secretkey": self.secret_key}
        r = requests.post(url, json=body, timeout=self.timeout,
                          headers={"Content-Type": "application/json;charset=UTF-8"})
        r.raise_for_status()
        d = r.json()
        self._token = d.get("token") or d.get("access_token")
        if not self._token:
            raise KiwoomError(f"토큰 발급 실패: {d}")
        # expires_dt('YYYYMMDDHHMMSS') 또는 expires_in(초) 둘 다 대응
        exp = d.get("expires_dt")
        if exp:
            try:
                self._token_exp = datetime.strptime(str(exp), "%Y%m%d%H%M%S").timestamp()
            except ValueError:
                self._token_exp = time.time() + 3600
        else:
            self._token_exp = time.time() + float(d.get("expires_in", 3600))

    def _post(self, api_id: str, body: dict, cont_yn: str = "N", next_key: str = "") -> dict:
        self._ensure_token()
        # 호출한도 간격 유지
        dt = time.time() - self._last_call
        if dt < self._min_interval:
            time.sleep(self._min_interval - dt)
        url = self.domain + PATHS[api_id]
        headers = {"Content-Type": "application/json;charset=UTF-8",
                   "Authorization": f"Bearer {self._token}",
                   "api-id": api_id, "cont-yn": cont_yn, "next-key": next_key}
        r = requests.post(url, json=body, headers=headers, timeout=self.timeout)
        self._last_call = time.time()
        r.raise_for_status()
        d = r.json()
        rc = d.get("return_code", d.get("rt_cd", 0))
        if str(rc) not in ("0", "None"):
            raise KiwoomError(f"{api_id} 실패 rc={rc}: {d.get('return_msg', d.get('msg1',''))}")
        return d

    # --- 조회 ---
    def get_price(self, code: str) -> float:
        d = self._post(TR_PRICE, {"stk_cd": code})
        # 현재가 필드는 스펙에 따라 cur_prc 등 — 여러 후보를 방어적으로 탐색
        for k in ("cur_prc", "stk_prpr", "prpr", "close_prc"):
            if k in d and d[k] not in (None, ""):
                return abs(float(str(d[k]).replace(",", "").lstrip("+-") or 0))
        raise KiwoomError(f"현재가 필드를 찾지 못함: {list(d)[:10]}")

    def get_balance(self) -> Balance:
        dep = self._post(TR_DEPOSIT, {"qry_tp": "3", "dmst_stex_tp": EXCHANGE_KRX})
        cash = 0.0
        for k in ("entr", "dnca_tot_amt", "prsm_dpst_aset_amt", "ord_alow_amt"):
            if k in dep and dep[k] not in (None, ""):
                cash = float(str(dep[k]).replace(",", "")); break
        hold = self._post(TR_HOLDINGS, {"dmst_stex_tp": EXCHANGE_KRX})
        rows = hold.get("output") or hold.get("acnt_evlt_remn_indv_tot") or hold.get("stk_acnt_evlt") or []
        positions = []
        for row in rows:
            try:
                qty = float(str(row.get("rmnd_qty", row.get("hldg_qty", 0))).replace(",", ""))
                if qty <= 0:
                    continue
                positions.append(Position(
                    code=str(row.get("stk_cd", "")).lstrip("A"),
                    name=row.get("stk_nm", ""),
                    qty=qty,
                    avg_price=float(str(row.get("pur_pric", row.get("avg_prc", 0))).replace(",", "")),
                ))
            except (ValueError, TypeError):
                continue
        return Balance(cash=cash, positions=positions)

    # --- 주문 ---
    def place_order(self, code: str, side: str, qty: int,
                    price: Optional[float] = None, name: str = "") -> OrderResult:
        side = side.lower()
        api_id = TR_BUY if side == "buy" else TR_SELL if side == "sell" else None
        if api_id is None:
            return OrderResult(False, code, side, qty, 0, 0.0, "rejected", reason="side 오류")
        trde_tp = TRADE_MARKET if price is None else "0"
        body = {"dmst_stex_tp": EXCHANGE_KRX, "stk_cd": code,
                "ord_qty": str(int(qty)), "trde_tp": trde_tp,
                "ord_uv": "" if price is None else str(int(price))}
        try:
            d = self._post(api_id, body)
        except (requests.RequestException, KiwoomError) as e:
            return OrderResult(False, code, side, qty, 0, price or 0.0, "rejected", reason=str(e))
        order_id = d.get("ord_no") or d.get("odno")
        # 접수 성공 = 주문 접수(체결은 비동기). filled_qty는 체결조회/WebSocket로 확정(Step 2 확장).
        return OrderResult(True, code, side, qty, qty, float(price or 0.0), "accepted",
                           order_id=order_id, reason="주문 접수(체결 확정은 체결조회 필요)",
                           meta={"raw": d})
