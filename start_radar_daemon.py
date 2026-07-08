import time
from datetime import datetime
from radar_alert import run_radar

print("==================================================")
print("[Billionaire Boys] 실시간 타점 레이더 데몬 가동 시작")
print("==================================================")

while True:
    now = datetime.now()
    # 평일 오전 9시 ~ 오후 3시 30분 사이에만 가동
    if now.weekday() < 5 and (9 <= now.hour <= 15):
        try:
            run_radar()
        except Exception as e:
            print(f"레이더 구동 중 에러 발생: {e}")
    else:
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 현재는 장 운영 시간이 아닙니다. 휴식 중...")
        
    # 1분(60초) 대기
    time.sleep(60)
