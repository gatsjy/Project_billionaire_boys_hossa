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

def get_foreign_selling_streak():
    """
    코스피 시장에서 외국인의 연속 순매도 일수와 누적 금액을 계산합니다.
    Returns: dict {streak_days, cumulative_amount, is_danger}
    """
    try:
        from pykrx import stock
        
        end_dt = datetime.today().strftime('%Y%m%d')
        start_dt = (datetime.today() - timedelta(days=30)).strftime('%Y%m%d')
        
        # 코스피 시장 전체의 투자자별 매매동향
        df = stock.get_market_trading_value_by_date(start_dt, end_dt, "KOSPI")
        
        if df.empty:
            return {"streak_days": 0, "cumulative_amount": 0, "is_danger": False}
        
        # 외국인 순매수 금액 컬럼 추출
        foreign_col = None
        for col in df.columns:
            if '외국인' in str(col):
                foreign_col = col
                break
        
        if foreign_col is None:
            return {"streak_days": 0, "cumulative_amount": 0, "is_danger": False}
        
        foreign_net = df[foreign_col]
        
        # 최근부터 연속 순매도(음수) 일수 계산
        streak_days = 0
        cumulative_amount = 0
        
        for val in reversed(foreign_net.values):
            if val < 0:
                streak_days += 1
                cumulative_amount += abs(val)
            else:
                break
        
        # 위험 판단: 5일 이상 연속 순매도 AND 누적 1조원 이상
        is_danger = streak_days >= 5 and cumulative_amount >= 1_000_000_000_000
        
        return {
            "streak_days": streak_days,
            "cumulative_amount": cumulative_amount,
            "is_danger": is_danger
        }
    except Exception as e:
        print(f"외국인 수급 데이터 조회 에러: {e}")
        return {"streak_days": 0, "cumulative_amount": 0, "is_danger": False}


def get_vkospi():
    """
    VKOSPI (코스피 200 변동성지수 / 한국판 공포지수) 현재값을 조회합니다.
    Returns: dict {current, is_fear}
    """
    try:
        df = fdr.DataReader('VKOSPI')
        if df.empty:
            return {"current": 0, "is_fear": False}
        
        curr_vkospi = float(df.iloc[-1]['Close'])
        is_fear = curr_vkospi >= 25
        
        return {"current": round(curr_vkospi, 2), "is_fear": is_fear}
    except Exception as e:
        print(f"VKOSPI 조회 에러: {e}")
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
        df = fdr.DataReader('US10YT=X')
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
    foreign = get_foreign_selling_streak()
    vkospi = get_vkospi()
    usd_krw = get_usd_krw_surge()
    treasury = get_us_treasury_10y()
    
    score = 0
    details = []
    
    if foreign['is_danger']:
        score += 1
        details.append(f"외국인 {foreign['streak_days']}일 연속 순매도 (누적 {foreign['cumulative_amount']/1e12:.1f}조원)")
    
    if vkospi['is_fear']:
        score += 1
        details.append(f"VKOSPI 공포지수 {vkospi['current']}pt (25pt 이상)")
    
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
        "foreign": foreign,
        "vkospi": vkospi,
        "usd_krw": usd_krw,
        "treasury": treasury
    }
