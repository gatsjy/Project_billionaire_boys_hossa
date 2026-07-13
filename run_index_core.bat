@echo off
REM Index-core trend bot launcher (Windows Task Scheduler)
REM Runs once per business day after market close. Log: trading_logs\index_core.log
REM NOTE: keep this file ASCII-only. cmd.exe parses .bat in the OEM codepage (cp949),
REM so UTF-8 Korean text corrupts parsing (caused the 2026-07-10 15:40 silent failure).
cd /d "C:\Users\KNUH\knuh_chatbot\Project_billionaire_boys_hossa"
if not exist "trading_logs" mkdir "trading_logs"
echo ================================================================ >> "trading_logs\index_core.log"
echo [%date% %time%] index_core_bot run >> "trading_logs\index_core.log"
"C:\Users\KNUH\AppData\Local\Programs\Python\Python311\python.exe" -X utf8 index_core_bot.py --source scheduler >> "trading_logs\index_core.log" 2>&1
