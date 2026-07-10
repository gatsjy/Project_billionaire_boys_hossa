@echo off
REM 지수 추세추종 코어 봇 런처 (Windows 작업 스케줄러용)
REM 매 영업일 장 마감 후 1회 실행. 로그는 trading_logs\index_core.log 에 누적.
cd /d "C:\Users\KNUH\knuh_chatbot\Project_billionaire_boys_hossa"
if not exist "trading_logs" mkdir "trading_logs"
echo ================================================================ >> "trading_logs\index_core.log"
echo [%date% %time%] index_core_bot 실행 >> "trading_logs\index_core.log"
"C:\Users\KNUH\AppData\Local\Programs\Python\Python311\python.exe" -X utf8 index_core_bot.py >> "trading_logs\index_core.log" 2>&1
