import os
import sys
import json
import pandas as pd
from datetime import datetime
import FinanceDataReader as fdr

sys.stdout.reconfigure(encoding='utf-8')

from notifier.email_sender import send_radar_alert
from backtest.data_loader import get_theme_stocks
from portfolio_manager import load_portfolio, save_portfolio
from backtest.realistic import DEFAULT_COST
from backtest.strategy import _atr
from backtest.index_strategy import calculate_rsi
from universe_updater import update_dynamic_universe

HISTORY_FILE = 'alert_history.json'

def load_alert_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if data.get("date") == datetime.today().strftime('%Y-%m-%d'):
                return data.get("alerts", [])
    return []

def save_alert_history(alerts):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json_data = {
            "date": datetime.today().strftime('%Y-%m-%d'),
            "alerts": alerts
        }
        json.dump(json_data, f, indent=4)

def run_radar():
    import tempfile
    lock_file = os.path.join(tempfile.gettempdir(), 'radar_daemon.lock')
    
    # 락 파일이 존재하고, 생성된 지 50초 이내라면 다른 프로세스가 실행 중인 것으로 간주
    if os.path.exists(lock_file):
        if datetime.now().timestamp() - os.path.getmtime(lock_file) < 50:
            print("⚠️ 이미 다른 레이더 프로세스가 실행 중입니다. 중복 실행을 방지합니다.")
            return
            
    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))
        
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 1분 주기 타점 레이더 및 실시간 가상 매매 엔진 스캔 시작...")
    today = datetime.today().strftime('%Y-%m-%d')
    
    # 동적 유니버스 업데이트 (하루 1회)
    theme_dir = os.path.join(os.path.dirname(__file__), 'themes')
    dyn_csv = os.path.join(theme_dir, 'dynamic_universe.csv')
    need_update = True
    if os.path.exists(dyn_csv):
        mtime = datetime.fromtimestamp(os.path.getmtime(dyn_csv))
        if mtime.strftime('%Y-%m-%d') == today:
            need_update = False
            
    if need_update:
        print("오늘의 주도주 동적 스캔 중...")
        update_dynamic_universe()
        
    stocks_df = get_theme_stocks(is_backtest=False)
    if stocks_df.empty:
        print("감시할 동적 유니버스 종목이 없습니다. 종료합니다.")
        return
        
    alerted_today = load_alert_history()
    new_alerts = []
    
    pf = load_portfolio()
    
    MAX_POSITIONS = 4
    MAX_DAILY_LOSS = -3.0
    
    today_loss = sum(t.get('profit_pct', 0) for t in pf.get('trade_history', [])
                     if t.get('sell_date') == today and t.get('profit_pct', 0) < 0)
    
    # 0. 기존 보유 종목 실시간 익절/손절 감시
    surviving_holdings = []
    for h in pf['holdings']:
        code = h['code']
        buy_price = h['buy_price']
        qty = h['qty']
        
        try:
            df = fdr.DataReader(code)
            if df.empty:
                surviving_holdings.append(h)
                continue
                
            curr_price = float(df.iloc[-1]['Close'])
            sold = False
            reason = ""
            
            # 인버스는 +5%, -2% / 일반 테마주는 +15%, -1%
            if code == '114800':
                if curr_price >= buy_price * 1.05:
                    reason = "익절 (+5%)"
                    sold = True
                elif curr_price <= buy_price * 0.98:
                    reason = "손절 (-2%)"
                    sold = True
            else:
                # 개별 종목별 동적 설정 적용: TP 15%, SL은 진입 시 기록된 손절가 적용
                # 구버전 호환성을 위해 h에 sl_price가 없으면 기본 -7% 적용
                sl_price = h.get('sl_price', buy_price * 0.93)
                tp_price = h.get('tp_price', buy_price * 1.15)
                
                if curr_price >= tp_price:
                    reason = f"익절 (+{((tp_price-buy_price)/buy_price)*100:.0f}%)"
                    sold = True
                elif curr_price <= sl_price:
                    reason = f"손절 ({((sl_price-buy_price)/buy_price)*100:.0f}%)"
                    sold = True
                    
            if sold:
                profit_pct = DEFAULT_COST.net_return(buy_price, curr_price) * 100
                pf['cash'] += curr_price * qty
                trade_record = {
                    "type": "sell",
                    "code": code,
                    "name": h['name'],
                    "buy_date": h['buy_date'],
                    "sell_date": today,
                    "buy_price": buy_price,
                    "sell_price": curr_price,
                    "profit_pct": profit_pct,
                    "reason": reason
                }
                pf['trade_history'].append(trade_record)
                
                subject = f"[{reason}] {h['name']} 실시간 매도 체결"
                msg = (
                    f"*[가상 매매 실시간 매도 체결]*\n"
                    f"종목: {h['name']} ({code})\n"
                    f"매수가: {int(buy_price):,}원\n"
                    f"매도가: {int(curr_price):,}원\n"
                    f"수익률: {profit_pct:.2f}%\n"
                    f"사유: {reason}\n"
                )
                send_radar_alert(subject, msg)
                print(f"[{h['name']}] 실시간 {reason} 매도 완료")
            else:
                surviving_holdings.append(h)
                
        except Exception as e:
            print(f"보유 종목 {code} 스캔 에러: {e}")
            surviving_holdings.append(h)
            
    pf['holdings'] = surviving_holdings

    # 1. 매크로 공포 점수(Fear Score) 및 코스피 기술적 지표 기반 하이브리드 인버스 헷징
    try:
        from backtest.macro_indicators import get_macro_fear_score
        
        macro = get_macro_fear_score()
        fear_score = macro['score']
        
        print(f"  [매크로 공포 점수] {fear_score}/4 - {macro['recommendation']}")
        for detail in macro['details']:
            print(f"    > {detail}")
            
        # KOSPI 기술적 지표 계산 (index_strategy.py 로직)
        ks11_df = fdr.DataReader('KS11')
        technical_danger = False
        tech_reason = ""
        
        if len(ks11_df) >= 60:
            ks11_df['RSI'] = calculate_rsi(ks11_df, 14)
            ks11_df['MA20'] = ks11_df['Close'].rolling(window=20).mean()
            ks11_df['MA60'] = ks11_df['Close'].rolling(window=60).mean()
            
            curr_close = float(ks11_df.iloc[-1]['Close'])
            prev_close = float(ks11_df.iloc[-2]['Close'])
            prev_rsi = float(ks11_df.iloc[-2]['RSI'])
            curr_ma20 = float(ks11_df.iloc[-1]['MA20'])
            curr_ma60 = float(ks11_df.iloc[-1]['MA60'])
            prev_ma60 = float(ks11_df.iloc[-2]['MA60'])
            prev_ma20 = float(ks11_df.iloc[-2]['MA20'])
            
            cond_overbought_reversal = (prev_rsi >= 75) and (curr_close < prev_close)
            cond_trend_breakdown = (prev_close > prev_ma60) and (curr_close < curr_ma60)
            cond_20ma_breakdown = (prev_close > prev_ma20) and (curr_close < curr_ma20)
            
            if cond_overbought_reversal:
                technical_danger = True
                tech_reason = f"KOSPI 과매수 역회전 (RSI {prev_rsi:.1f} -> 하락전환)"
            elif cond_trend_breakdown:
                technical_danger = True
                tech_reason = f"KOSPI 60일선(수급선) 하향 돌파"
            elif cond_20ma_breakdown:
                technical_danger = True
                tech_reason = f"KOSPI 20일선(생명선) 데드크로스"
                
        if technical_danger:
            print(f"  [KOSPI 기술적 위험 발생] {tech_reason}")
        
        # Fear Score 2점 이상 OR 기술적 위험 발생 시 인버스 매수
        if fear_score >= 2 or technical_danger:
            if '114800' not in alerted_today:
                inv_df = fdr.DataReader('114800')
                if not inv_df.empty:
                    curr_inv_price = int(inv_df.iloc[-1]['Close'])
                    
                    # 인버스는 자본금 20% 한도 (공격적 헷징)
                    invest_amount = min(pf['cash'] * 0.20, 1000000)
                    
                    if invest_amount >= 100000 and not any(h['code'] == '114800' for h in pf['holdings']):
                        qty = int(invest_amount // curr_inv_price)
                        pf['cash'] -= qty * curr_inv_price
                        
                        buy_record = {
                            "type": "buy",
                            "code": "114800",
                            "name": "KODEX 인버스",
                            "buy_date": today,
                            "buy_price": float(curr_inv_price),
                            "qty": qty,
                            "sl_price": curr_inv_price * 0.98,
                            "tp_price": curr_inv_price * 1.05
                        }
                        pf['holdings'].append(buy_record)
                        pf['trade_history'].append(buy_record)
                        
                        # 이메일에 포함될 메시지 구성
                        macro_detail_str = "\n".join([f"  - {d}" for d in macro['details']])
                        trigger_reason = f"Fear Score {fear_score}/4" if fear_score >= 2 else f"기술적 시그널 ({tech_reason})"
                        
                        subject = f"[방어막 가동] 코스피 하방 헷징 인버스 매수 체결"
                        msg = (
                            f"*[하이브리드 인버스 헷징 매수 완료]*\n"
                            f"진입 사유: {trigger_reason}\n\n"
                            f"[매크로 공포 점수]: {fear_score}/4\n"
                            f"{macro_detail_str}\n\n"
                            f"[기술적 지표]: {'위험 (' + tech_reason + ')' if technical_danger else '안정'}\n\n"
                            f"종목: KODEX 인버스 (114800)\n"
                            f"체결가: {curr_inv_price:,}원\n"
                            f"수량: {qty}주\n"
                            f"목표 익절가: {int(curr_inv_price * 1.05):,}원 (+5%)\n"
                            f"손절가: {int(curr_inv_price * 0.98):,}원 (-2%)"
                        )
                        send_radar_alert(subject, msg)
                        alerted_today.append('114800')
                        new_alerts.append('114800')
    except Exception as e:
        print(f"매크로 인버스 스캔 에러: {e}")

    # 2. 테마주 슈팅 타점 스캔 (조선, 원전, 방산, 반도체, 로봇, 전력 등)
    if today_loss <= MAX_DAILY_LOSS:
        print(f"⚠️ 일일 손실 한도({today_loss:.2f}%) 도달. 금일 신규 매수 중단.")
        save_portfolio(pf)
        return

    if len(pf['holdings']) >= MAX_POSITIONS:
        print(f"⚠️ 최대 보유 종목 수({MAX_POSITIONS}개) 도달. 신규 매수 스캔 생략.")
        save_portfolio(pf)
        return

    theme_stocks = get_theme_stocks()
    if not theme_stocks.empty:
        for idx, row in theme_stocks.iterrows():
            code = str(row['Code']).zfill(6)
            name = row['Name']
            
            if code in alerted_today:
                continue
                
            try:
                df = fdr.DataReader(code)
                if len(df) < 21: continue
                
                vol_ma20 = df['Volume'].iloc[-21:-1].mean()
                ma20 = df['Close'].iloc[-21:-1].mean()
                curr_vol = df['Volume'].iloc[-1]
                curr_price = float(df['Close'].iloc[-1])
                prev_price = float(df['Close'].iloc[-2])
                open_price = float(df['Open'].iloc[-1])
                
                # 1. 장중 시간 비례 예상 거래량 산출 (Time-proportional Volume)
                now_time = datetime.now()
                market_open = now_time.replace(hour=9, minute=0, second=0, microsecond=0)
                elapsed_minutes = (now_time - market_open).total_seconds() / 60.0
                
                # [시간 필터] 개장 후 30분(09:30) 이전에는 뇌동매매 방지를 위해 컷오프
                if elapsed_minutes < 30: continue
                
                elapsed_minutes = max(1, min(elapsed_minutes, 390)) # 09:00~15:30 (390분)
                proj_vol = curr_vol * (390 / elapsed_minutes)
                
                # [절대 대금 필터] 현재 실제 체결된 거래대금이 100억 미만이면 잡주로 간주하여 패스
                trading_value = curr_price * curr_vol
                if trading_value < 10000000000: continue
                
                # 2. 추세 필터: 전일 종가가 20일선 위에 있을 때만
                if prev_price < ma20: continue
                
                # 3. 당일 양봉 필터 (Intraday Momentum) - 현재가가 시가보다 높아야 함
                if curr_price <= open_price: continue
                
                # 4. 고점 추격 매수(FOMO) 방지 - 전일 종가 대비 15% 이상 급등 시 패스
                if curr_price >= prev_price * 1.15: continue
                
                # 5. 거래량 3배 필터 (예상 거래량 기준) & 시가 갭 4% 미만
                if proj_vol >= vol_ma20 * 3 and curr_price > prev_price:
                    if open_price < prev_price * 1.04:
                        if len(pf['holdings']) >= MAX_POSITIONS: break
                        
                        # Half-Kelly 기반 사이징 근사 (자본의 10% 한도)
                        invest_amount = min(pf['cash'] * 0.10, 500000)
                        if invest_amount < 100000: continue
                        
                        if not any(h['code'] == code for h in pf['holdings']):
                            qty = int(invest_amount // curr_price)
                            if qty == 0: continue
                            
                            pf['cash'] -= qty * curr_price
                            
                            # ATR 기반 동적 손절
                            atr_series = _atr(df)
                            curr_atr = float(atr_series.iloc[-1])
                            atr_pct = curr_atr / curr_price
                            
                            # 기본 -7%와 -1.5*ATR 중 더 넓은(안전한) 쪽을 선택해 노이즈 손절 제거
                            dynamic_sl_pct = min(-0.07, -1.5 * atr_pct)
                            sl_price = curr_price * (1 + dynamic_sl_pct)
                            tp_price = curr_price * 1.15
                            
                            buy_record = {
                                "type": "buy",
                                "code": code,
                                "name": name,
                                "buy_date": today,
                                "buy_price": curr_price,
                                "qty": qty,
                                "sl_price": sl_price,
                                "tp_price": tp_price
                            }
                            pf['holdings'].append(buy_record)
                            pf['trade_history'].append(buy_record)
                            
                            subject = f"{name} 단기 슈팅 타점 가상 매수 체결"
                            msg = (
                                f"*[테마 대장주 슈팅 포착 및 매수 완료]*\n"
                                f"테마: {row.get('Theme', '수주산업')} / 거래대금 100억+ & 추세필터\n\n"
                                f"종목: {name} ({code})\n"
                                f"돌파 시각: {now_time.strftime('%H:%M:%S')}\n"
                                f"현재 거래대금: {int(trading_value // 100000000):,}억 원\n"
                                f"체결가: {curr_price:,}원\n"
                                f"수량: {qty}주\n"
                                f"목표 익절가: {int(tp_price):,}원 (+15%)\n"
                                f"손절가: {int(sl_price):,}원 ({dynamic_sl_pct*100:.1f}% / ATR기반)"
                            )
                            send_radar_alert(subject, msg)
                            alerted_today.append(code)
                            new_alerts.append(code)
            except Exception as e:
                print(f"{name} 스캔 에러: {e}")
                
    save_portfolio(pf)
    
    if new_alerts:
        save_alert_history(alerted_today)
        print(f"새로운 매수 체결 알림 {len(new_alerts)}건 발송 완료.")
    else:
        print("조건에 부합하는 타점(매수/매도)이 없습니다.")

    # 실행 종료 시 락 파일 해제
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except:
            pass

if __name__ == "__main__":
    run_radar()
