"""
매크로 시장 공포 지표 수집 모듈 (Macro Fear Gauge)
- 외국인 연속 순매도 일수 & 금액 (pykrx)
- VKOSPI (한국판 공포지수)
- 원/달러 환율 급등 여부
- 미국 10년물 국채 금리
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import FinanceDataReader as fdr

def get_kospi_momentum():
    """
    코스피 지수(KS11) 자체의 투심을 확인합니다. (외국인 순매도 대체)
    Returns: dict {current, ma20, is_danger}
    """
    try:
        df = fdr.DataReader('KS11')
        if df.empty or len(df) < 20:
            return {"current": 0, "ma20": 0, "is_danger": False}
        
        curr_price = float(df.iloc[-1]['Close'])
        ma20 = float(df['Close'].iloc[-20:].mean())
        
        # 20일 이동평균선(생명선)을 하향 이탈한 상태면 위험
        is_danger = curr_price < ma20
        
        return {
            "current": round(curr_price, 2),
            "ma20": round(ma20, 2),
            "is_danger": is_danger
        }
    except Exception as e:
        print(f"KOSPI 모멘텀 조회 에러: {e}")
        return {"current": 0, "ma20": 0, "is_danger": False}


def get_us_vix():
    """
    글로벌 공포지수인 미국 VIX 지수 현재값을 조회합니다. (폐지된 VKOSPI 대체)
    Returns: dict {current, is_fear}
    """
    try:
        df = fdr.DataReader('^VIX')
        if df.empty:
            return {"current": 0, "is_fear": False}
        
        curr_vix = float(df.iloc[-1]['Close'])
        # 일반적으로 VIX 20 초과 시 시장의 공포(변동성 심화) 상태로 간주
        is_fear = curr_vix >= 20
        
        return {"current": round(curr_vix, 2), "is_fear": is_fear}
    except Exception as e:
        print(f"US VIX 조회 에러: {e}")
        return {"current": 0, "is_fear": False}


def get_usd_krw_surge():
    """
    원/달러 환율의 급등 여부를 판단합니다.
    Returns: dict {current, ma5, is_surging}
    """
    try:
        df = fdr.DataReader('USD/KRW')
        if df.empty or len(df) < 5:
            return {"current": 0, "ma5": 0, "is_surging": False}
        
        curr_rate = float(df.iloc[-1]['Close'])
        ma5 = float(df['Close'].iloc[-5:].mean())
        
        # 현재 환율이 5일 이평선 위에 있고, 1,400원 이상이면 위험
        is_surging = curr_rate > ma5 and curr_rate >= 1400
        
        return {
            "current": round(curr_rate, 2),
            "ma5": round(ma5, 2),
            "is_surging": is_surging
        }
    except Exception as e:
        print(f"환율 조회 에러: {e}")
        return {"current": 0, "ma5": 0, "is_surging": False}


def get_us_treasury_10y():
    """
    미국 10년물 국채 금리를 조회합니다.
    Returns: dict {current, prev, daily_change, is_warning}
    """
    try:
        df = fdr.DataReader('^TNX')
        if df.empty or len(df) < 2:
            return {"current": 0, "prev": 0, "daily_change": 0, "is_warning": False}
        
        curr_yield = float(df.iloc[-1]['Close'])
        prev_yield = float(df.iloc[-2]['Close'])
        daily_change = curr_yield - prev_yield
        
        # 전일 대비 0.1%p 이상 급등 또는 절대 수준 4.5% 이상
        is_warning = daily_change >= 0.1 or curr_yield >= 4.5
        
        return {
            "current": round(curr_yield, 3),
            "prev": round(prev_yield, 3),
            "daily_change": round(daily_change, 3),
            "is_warning": is_warning
        }
    except Exception as e:
        print(f"미국 국채 금리 조회 에러: {e}")
        return {"current": 0, "prev": 0, "daily_change": 0, "is_warning": False}


def get_macro_fear_score():
    """
    4개의 매크로 지표를 종합하여 0~4점의 공포 점수(Fear Score)를 산출합니다.
    - 0점: 안전 (인버스 매수 금지)
    - 1~2점: 주의 (모니터링)
    - 3~4점: 공포 (인버스 매수 강력 추천)
    
    Returns: dict {score, max_score, details, recommendation}
    """
    kospi_mom = get_kospi_momentum()
    vix = get_us_vix()
    usd_krw = get_usd_krw_surge()
    treasury = get_us_treasury_10y()
    
    score = 0
    details = []
    
    if kospi_mom['is_danger']:
        score += 1
        details.append(f"KOSPI 투심 악화 (현재 {kospi_mom['current']}pt가 20일선 {kospi_mom['ma20']}pt 하향 이탈)")
    
    if vix['is_fear']:
        score += 1
        details.append(f"글로벌 VIX 공포지수 {vix['current']}pt (20pt 이상 위험 구간)")
    
    if usd_krw['is_surging']:
        score += 1
        details.append(f"원/달러 환율 {usd_krw['current']}원 급등 (5일선 {usd_krw['ma5']}원 돌파)")
    
    if treasury['is_warning']:
        score += 1
        details.append(f"미국 10년물 금리 {treasury['current']}% (전일비 +{treasury['daily_change']}%p)")
    
    if score >= 3:
        recommendation = "인버스 매수 강력 추천 (매크로 적색 경보)"
    elif score >= 2:
        recommendation = "인버스 매수 검토 (매크로 황색 경보)"
    else:
        recommendation = "인버스 매수 보류 (매크로 안정)"
    
    return {
        "score": score,
        "max_score": 4,
        "details": details,
        "recommendation": recommendation,
        "kospi_mom": kospi_mom,
        "vix": vix,
        "usd_krw": usd_krw,
        "treasury": treasury
    }
