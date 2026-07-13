"""
data_integrity.py — 시세 무결성 가드 (순수 로직, 네트워크/부작용 없음)

[왜] 실계좌 연동을 앞두고 가장 위험한 것은 '틱 오류/데이터 괴리로 실거래가 나가는 것'이다.
  2026-07-13 실측: KODEX 200(069500) FDR 종가가 하루 -9.8%로 찍혔으나, 기초지수 KOSPI 200은
  -3.67%. ETF/지수 비율이 며칠간 ~100.8에서 그날만 94.4로 6%p 붕괴 — 명백한 데이터 이상.
  기존 _validate(신선도+절대범위)는 이를 통과시켜, 봇이 가짜 -9.8%로 판단했다(다행히 매매 트리거는
  안 걸림). 실계좌였다면 가짜 급락이 추세선을 깨 '전량 매도'를 실행할 수 있었다.

[가드 2종]
  1) ETF↔기초지수 괴리: 최근 비율 중앙값 대비 오늘 비율 이탈이 tol 초과면 이상(데이터 오류/유동성
     디스로케이션). 기초지수를 못 받으면 이 검사는 건너뛴다(참조 부재로 매매를 막지는 않음).
  2) 일간 변동 상한: 1배 지수 ETF가 하루 |x|% 초과 이동은 비현실적 → 절대 백스톱.
"""


class DataIntegrityError(Exception):
    """시세가 신뢰 불가로 판정됨 — 봇은 매매를 중단하고 사용자에게 경보해야 한다."""


def index_tracking_deviation(etf_close, idx_close, lookback=20):
    """ETF가 기초지수를 정상 추종 중인지 → (오늘 비율 이탈률, 최근 중앙 비율).

    etf_close, idx_close : 같은 날짜로 정렬된 종가 시퀀스(list/np/pd). 최소 lookback+1 필요.
    반환: (deviation, median_ratio)
      deviation = 오늘 비율 / (직전 lookback일 비율 중앙값) - 1  (부호 유지)
    데이터 부족/0가격 등으로 계산 불가 시 (None, None).
    """
    e = [float(x) for x in etf_close]
    i = [float(x) for x in idx_close]
    n = min(len(e), len(i))
    if n < lookback + 1:
        return None, None
    e, i = e[-(lookback + 1):], i[-(lookback + 1):]
    ratios = [ev / iv for ev, iv in zip(e, i) if iv > 0]
    if len(ratios) < lookback + 1:
        return None, None
    prior = sorted(ratios[:-1])
    m = len(prior)
    med = prior[m // 2] if m % 2 else (prior[m // 2 - 1] + prior[m // 2]) / 2
    if med <= 0:
        return None, None
    return ratios[-1] / med - 1, med


def check_index_divergence(etf_close, idx_close, lookback=20, tol=0.03):
    """괴리 가드. 이탈 |dev| > tol 이면 DataIntegrityError. 참조 부재 시 통과(경고 없음).
    반환: dev(float) 또는 None(검사 스킵)."""
    dev, _ = index_tracking_deviation(etf_close, idx_close, lookback)
    if dev is None:
        return None
    if abs(dev) > tol:
        raise DataIntegrityError(
            f"ETF-지수 괴리 {dev*100:+.1f}% (허용 ±{tol*100:.0f}%) — 데이터 오류/디스로케이션 의심. 매매 중단.")
    return dev


def check_daily_move(close_seq, max_move=0.25):
    """1배 ETF의 하루 종가 변동이 max_move 초과면 DataIntegrityError(절대 백스톱).
    반환: 일간수익률 또는 None(데이터 부족)."""
    c = [float(x) for x in close_seq]
    if len(c) < 2 or c[-2] <= 0:
        return None
    ret = c[-1] / c[-2] - 1
    if abs(ret) > max_move:
        raise DataIntegrityError(
            f"일간 변동 {ret*100:+.1f}% (상한 ±{max_move*100:.0f}%) — 비현실적, 데이터 오류 의심. 매매 중단.")
    return ret
