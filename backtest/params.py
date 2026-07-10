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

# --- 스윙 반전 전략 (검증 통과 후보 — reversal_research/entry_quality_research) ---
# 한국 개별주는 단기 모멘텀이 약하고 반전이 강함 → '추격'이 아니라 '눌림 매수'.
# OOS 기댓값 +0.42~0.49%/매매, PF 1.17, 승률 60~65% (비용 반영). 아직 라이브 미적용.
REV_RSI_ENTRY = 30           # 진입: RSI(14) < 이 값 (과매도)
REV_TREND_MA = 60            # 진입: 종가 > N일선 (중기추세 유지 = 떨어지는 칼날 배제)
REV_ATR_CAP = 8.0            # 진입 제외: 일변동성 ATR% > 이 값 (작전주·펌핑주 회피; 금호전기 20.6%)
REV_RSI_EXIT = 50            # 청산: RSI 반등 > 이 값 (엣지의 핵심)
REV_TP = 0.05                # 익절 +5%
REV_SL = -0.05               # 손절 하한 (실제는 max(5%, 1.5×ATR)로 노이즈 위에서)
REV_ATR_K = 1.5              # ATR 기반 손절 배수
REV_HOLD_DAYS = 10           # 영업일 타임아웃

# --- 공통 리스크 ---
TIME_STOP_DAYS = 3           # 영업일 기준 보유 상한
POSITION_SIZE = 500000       # 종목당 진입 금액(원)
