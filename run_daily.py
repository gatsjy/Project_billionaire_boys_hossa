import os
import json
import time
from datetime import datetime, timedelta
import pandas as pd
import FinanceDataReader as fdr

from backtest.data_loader import get_daily_data
from portfolio_manager import load_portfolio, save_portfolio
from notifier.email_sender import send_radar_alert

LOG_DIR = 'trading_logs'

def generate_markdown_report(today, pf, daily_trades, total_value):
    profit_amt = total_value - pf['initial_capital']
    profit_pct = (profit_amt / pf['initial_capital']) * 100
    
    md = f"# 📈 억만장자 보이즈 클럽: 일일 가상 매매 일지\n\n"
    md += f"## 📅 일자: {today}\n"
    md += f"- **💰 초기 자본금:** {pf['initial_capital']:,} 원\n"
    md += f"- **💵 현재 현금:** {int(pf['cash']):,} 원\n"
    md += f"- **📊 총 평가 자산:** {int(total_value):,} 원\n"
    md += f"- **📈 누적 수익률:** {profit_pct:.2f}%\n\n"
    
    md += "## 🔄 당일 발생 매매 내역 (실시간 체결 내역 포함)\n"
    if daily_trades:
        md += "| 종목명 | 매수일 | 체결구분 | 단가 | 수익률 | 사유 |\n"
        md += "|---|---|---|---|---|---|\n"
        for t in daily_trades:
            if t['type'] == 'sell':
                md += f"| {t['name']} | {t['buy_date']} | **매도** | {int(t['sell_price']):,}원 | {t['profit_pct']:.2f}% | {t['reason']} |\n"
            else:
                md += f"| {t['name']} | {t['buy_date']} | **매수** | {int(t['buy_price']):,}원 | - | 레이더 시그널 포착 |\n"
    else:
        md += "오늘 발생한 매매 내역이 없습니다.\n"
        
    md += "\n## 💼 현재 보유 종목 (Holdings)\n"
    if pf['holdings']:
        md += "| 종목명 | 매수가 | 수량 |\n"
        md += "|---|---|---|\n"
        for h in pf['holdings']:
            md += f"| {h['name']} | {int(h['buy_price']):,}원 | {h['qty']}주 |\n"
    else:
        md += "보유 중인 주식이 없습니다.\n"
        
    return md

def run_daily_eod_tasks():
    today = datetime.today().strftime('%Y-%m-%d')
    
    pf = load_portfolio()
    
    # 일일 실행 잠금 (Daily Lock)
    if pf.get('last_eod_date') == today:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 오늘({today}) 장 마감 EOD 결산 작업이 이미 완료되었습니다. 중복 실행을 방지합니다.")
        return
        
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 장 마감 EOD 결산 작업 시작")
    
    end_dt = datetime.today()
    start_dt = end_dt - timedelta(days=20)
    
    today_trades = []
    
    # 1. 3일 경과 타임스탑 청산 (종가 기준)
    surviving_holdings = []
    for h in pf['holdings']:
        code = h['code']
        buy_date_obj = datetime.strptime(h['buy_date'], '%Y-%m-%d')
        days_held = (end_dt - buy_date_obj).days
        
        if days_held >= 3:
            df = get_daily_data(code, start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d'))
            if df.empty:
                surviving_holdings.append(h)
                continue
            
            today_close = df.iloc[-1]['Close']
            qty = h['qty']
            buy_price = h['buy_price']
            
            profit_pct = (today_close - buy_price) / buy_price * 100
            pf['cash'] += today_close * qty
            trade_record = {
                "type": "sell",
                "code": code,
                "name": h['name'],
                "buy_date": h['buy_date'],
                "sell_date": today,
                "buy_price": buy_price,
                "sell_price": float(today_close),
                "profit_pct": profit_pct,
                "reason": "보유기간 3일 경과 (EOD 타임스탑)",
                "theme": h.get("theme", ""),
                "trading_value_100m": h.get("trading_value_100m", 0),
                "buy_time": h.get("buy_time", "")
            }
            
            if profit_pct < 0:
                from portfolio_manager import log_false_signal
                log_false_signal(trade_record)
                
            pf['trade_history'].append(trade_record)
            today_trades.append(trade_record)
            print(f"[{h['name']}] 타임스탑 강제 청산 (종가: {today_close}원)")
        else:
            surviving_holdings.append(h)
            
    pf['holdings'] = surviving_holdings
    save_portfolio(pf)
    
    # 2. 오늘 하루 동안 장중에 발생한 매매 내역(레이더가 체결한 것들) 가져오기
    for t in pf['trade_history']:
        if (t.get('buy_date') == today and t.get('type') == 'buy') or (t.get('sell_date') == today and t.get('type') == 'sell'):
            # 중복 방지를 위해 이미 today_trades에 없으면 추가
            if t not in today_trades:
                today_trades.append(t)
                
    # 3. 평가액 계산 및 일일 보고서 생성
    holdings_value = 0
    for h in pf['holdings']:
        # 간이 평가를 위해 매수가를 현재가로 추정 (실제론 실시간가 필요하지만 EOD 리포트용)
        holdings_value += h['buy_price'] * h['qty']
        
    total_value = pf['cash'] + holdings_value
    
    md_content = generate_markdown_report(today, pf, today_trades, total_value)
    
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
        
    log_filename = os.path.join(LOG_DIR, f"{today}_log.md")
    with open(log_filename, 'w', encoding='utf-8') as f:
        f.write(md_content)
        
    # 데일리 리포트 이메일 발송
    send_radar_alert(f"[가상매매 일지] {today} 결산 리포트", md_content)
    
    pf['last_eod_date'] = today
    save_portfolio(pf)
    
    print(f"가상 매매 EOD 결산 종료. 매매 일지 생성 및 이메일 발송 완료: {log_filename}")

if __name__ == "__main__":
    run_daily_eod_tasks()
