import os
import json
from datetime import datetime
import FinanceDataReader as fdr
from portfolio_manager import load_portfolio, save_portfolio, log_false_signal
from notifier.email_sender import send_radar_alert

def liquidate_all():
    pf = load_portfolio()
    if not pf['holdings']:
        print("매도할 종목이 없습니다.")
        return
        
    today = datetime.today().strftime('%Y-%m-%d')
    sell_records = []
    
    print("전량 수동 매도 진행 중...")
    
    for h in pf['holdings']:
        code = h['code']
        df = fdr.DataReader(code)
        if df.empty:
            continue
            
        curr_price = float(df.iloc[-1]['Close'])
        buy_price = h['buy_price']
        qty = h['qty']
        
        profit_pct = (curr_price - buy_price) / buy_price * 100
        pf['cash'] += curr_price * qty
        
        reason = "수동 전량 매도 (수익 실현/포지션 정리)"
        trade_record = {
            "type": "sell",
            "code": code,
            "name": h['name'],
            "buy_date": h['buy_date'],
            "sell_date": today,
            "buy_price": buy_price,
            "sell_price": curr_price,
            "profit_pct": profit_pct,
            "reason": reason,
            "theme": h.get("theme", ""),
            "trading_value_100m": h.get("trading_value_100m", 0),
            "buy_time": h.get("buy_time", "")
        }
        
        pf['trade_history'].append(trade_record)
        sell_records.append(trade_record)
        
        # 손실 마감이면 헛방 로거에도 저장
        if profit_pct < 0:
            log_false_signal(trade_record)
            
        print(f"[{h['name']}] 매도 완료: {curr_price}원 ({profit_pct:.2f}%)")
        
    # 모든 종목 삭제
    pf['holdings'] = []
    
    save_portfolio(pf)
    
    # 결과 요약 이메일 생성
    subject = "[수동 개입] 포트폴리오 전량 매도 완료"
    msg = "*[가상 매매 수동 전량 매도]*\n\n"
    for r in sell_records:
        msg += f"- {r['name']}: {int(r['sell_price']):,}원 ({r['profit_pct']:.2f}%)\n"
        
    msg += f"\n총 현금 보유량: {int(pf['cash']):,}원"
    send_radar_alert(subject, msg)
    print("매도 완료 및 이메일 발송 성공!")

if __name__ == "__main__":
    liquidate_all()
