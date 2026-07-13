"""
kiwoom_connect_test.py — 키움 모의투자 연결 검증 (읽기 전용, 주문 안 함)

Step 2의 첫 관문: 네 모의투자 앱키로 (1) 토큰 발급 (2) 잔고 조회 (3) 현재가 조회가
되는지만 확인한다. 주문은 넣지 않으므로 안전하다. 성공하면 다음 단계(주문·대사)로 간다.

준비:
  1) openapi.kiwoom.com 에서 앱키/시크릿 발급 + '모의투자' 신청
  2) config.json 에 kiwoom 섹션 추가(config.example.json 참고)
  3) python kiwoom_connect_test.py

이 스크립트는 모의(mock) 도메인만 사용한다. 실전 전환은 대사·킬스위치 완료 후.
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from broker.kiwoom_broker import KiwoomRestBroker, KiwoomError


def main():
    try:
        config = json.load(open("config.json", encoding="utf-8"))
    except FileNotFoundError:
        print("❌ config.json 이 없습니다. config.example.json 을 참고해 만드세요.")
        return

    try:
        b = KiwoomRestBroker(config, live=False)   # 모의투자
    except KiwoomError as e:
        print(f"❌ 설정 오류: {e}")
        return

    print(f"모드: {b.mode} · 도메인: {b.domain}\n")

    print("[1/3] 토큰 발급...")
    try:
        b._ensure_token()
        print(f"  ✅ 토큰 발급 성공 (만료 예정 {b._token_exp:.0f})")
    except Exception as e:
        print(f"  ❌ 토큰 실패: {e}")
        print("  → 앱키/시크릿, 모의투자 신청 여부를 확인하세요.")
        return

    print("[2/3] 잔고 조회...")
    try:
        bal = b.get_balance()
        print(f"  ✅ 예수금 {bal.cash:,.0f}원 · 보유 {len(bal.positions)}종목")
        for p in bal.positions[:10]:
            print(f"     - {p.name}({p.code}) {p.qty:g}주 @ {p.avg_price:,.0f}")
    except Exception as e:
        print(f"  ⚠️ 잔고 조회 실패: {e}")
        print("     (PATHS/필드명이 공식 개발가이드와 다를 수 있음 — kiwoom_broker.py 상수 확인)")

    print("[3/3] 현재가 조회 (KODEX 200, 069500)...")
    try:
        px = b.get_price("069500")
        print(f"  ✅ 현재가 {px:,.0f}원")
    except Exception as e:
        print(f"  ⚠️ 현재가 조회 실패: {e}")

    print("\n완료. ✅가 3개면 연결 성공 → 다음: 소액 모의 주문 테스트 + 대사(Step 3).")
    print("⚠️는 인증은 됐으나 응답 필드/경로 매핑을 개발가이드로 맞추면 됩니다.")


if __name__ == "__main__":
    main()
