"""
params.py — 매매 파라미터 단일 소스(Single Source of Truth)

기존 문제: 익절/손절/거래량배수가 문서·주석·radar_alert·백테스트에 제각각으로 하드코딩되어
있었다(+15/-1, +7/-2, +7/-3 …). '검증한 값'과 '실전에 쓰는 값'이 달라 백테스트가 무의미했다.
이제 실행부(radar_alert, run_daily)와 검증부(strategy, engine, simulator, optimizer)가
모두 이 파일 하나만 참조한다. 값을 바꾸려면 여기만 고친다.
"""

# --- 테마주 롱 전략 ---
VOLUME_SPIKE_MULT = 3        # 전일 거래량 ≥ 20일평균 × 이 배수 (진입 핵심 조건)
THEME_TP = 0.07              # 익절 +7%
THEME_SL = -0.03             # 손절 -3% (노이즈보다 넓게; -1~-2%는 필히 털림)
GAP_MIN = -2                 # 시가 갭 하한(%)
GAP_MAX = 5                  # 시가 갭 상한(%)

# --- 인버스 헷징 전략 ---
INVERSE_CODE = '114800'
INVERSE_TP = 0.05            # 익절 +5%
INVERSE_SL = -0.02           # 손절 -2%
FEAR_SCORE_ENTRY = 2         # 매크로 공포점수 ≥ 2 일 때 인버스 매수

# --- 공통 리스크 ---
TIME_STOP_DAYS = 3           # 영업일 기준 보유 상한
POSITION_SIZE = 500000       # 종목당 진입 금액(원)
