import os
import json
import pandas as pd
from datetime import datetime
import FinanceDataReader as fdr

from notifier.email_sender import send_radar_alert
from backtest.data_loader import get_theme_stocks
from portfolio_manager import load_portfolio, save_portfolio

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
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 1분 주기 타점 레이더 및 실시간 가상 매매 엔진 스캔 시작...")
    today = datetime.today().strftime('%Y-%m-%d')
    
    alerted_today = load_alert_history()
    new_alerts = []
    
    pf = load_portfolio()
    
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
                if curr_price >= buy_price * 1.15:
                    reason = "익절 (+15%)"
                    sold = True
                elif curr_price <= buy_price * 0.99:
                    reason = "손절 (-1%)"
                    sold = True
                    
            if sold:
                profit_pct = (curr_price - buy_price) / buy_price * 100
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

    # 1. KODEX 인버스 타점 스캔 (930원 ~ 950원)
    try:
        inv_df = fdr.DataReader('114800')
        if not inv_df.empty:
            curr_inv_price = int(inv_df.iloc[-1]['Close'])
            if 930 <= curr_inv_price <= 950:
                if '114800' not in alerted_today:
                    if pf['cash'] >= 500000 and not any(h['code'] == '114800' for h in pf['holdings']):
                        qty = int(500000 // curr_inv_price)
                        pf['cash'] -= qty * curr_inv_price
                        
                        buy_record = {
                            "type": "buy",
                            "code": "114800",
                            "name": "KODEX 인버스",
                            "buy_date": today,
                            "buy_price": float(curr_inv_price),
                            "qty": qty
                        }
                        pf['holdings'].append(buy_record)
                        pf['trade_history'].append(buy_record)
                        
                        subject = "코스피 하방 헷징 인버스 가상 매수 체결"
                        msg = (
                            "*[긴급 하방 헷징 타점 포착 및 매수 완료]*\n"
                            "코스피 데드캣 바운스 고점 도달 (인버스 매수 최적기)\n\n"
                            "종목: KODEX 인버스 (114800)\n"
                            f"체결가: {curr_inv_price:,}원\n"
                            f"수량: {qty}주\n"
                            f"목표 익절가: {int(curr_inv_price * 1.05):,}원 (+5%)\n"
                            f"손절가: {int(curr_inv_price * 0.98):,}원 (-2%)"
                        )
                        send_radar_alert(subject, msg)
                        alerted_today.append('114800')
                        new_alerts.append('114800')
    except Exception as e:
        print(f"인버스 스캔 에러: {e}")

    # 2. 테마주 슈팅 타점 스캔 (조선, 원전, 방산, 반도체, 로봇, 전력 등)
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
                curr_vol = df['Volume'].iloc[-1]
                curr_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                
                if curr_vol >= vol_ma20 and curr_price > prev_price:
                    open_price = df['Open'].iloc[-1]
                    if open_price < prev_price * 1.04:
                        if pf['cash'] >= 500000 and not any(h['code'] == code for h in pf['holdings']):
                            qty = int(500000 // curr_price)
                            pf['cash'] -= qty * curr_price
                            
                            buy_record = {
                                "type": "buy",
                                "code": code,
                                "name": name,
                                "buy_date": today,
                                "buy_price": float(curr_price),
                                "qty": qty
                            }
                            pf['holdings'].append(buy_record)
                            pf['trade_history'].append(buy_record)
                            
                            subject = f"{name} 단기 슈팅 타점 가상 매수 체결"
                            msg = (
                                f"*[테마 대장주 슈팅 포착 및 매수 완료]*\n"
                                f"테마: {row.get('Theme', '수주산업')} / 장중 거래량 폭발\n\n"
                                f"종목: {name} ({code})\n"
                                f"체결가: {curr_price:,}원\n"
                                f"수량: {qty}주\n"
                                f"목표 익절가: {int(curr_price * 1.15):,}원 (+15%)\n"
                                f"손절가: {int(curr_price * 0.99):,}원 (-1%)"
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

if __name__ == "__main__":
    run_radar()
