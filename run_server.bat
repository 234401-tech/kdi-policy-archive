@echo off
chcp 65001 >nul
rem 아카이브 + 주간 보고서 로컬 서버 (HWPX 저장·AI 요약 지원 서버로 통합)
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
echo Starting local server on port 8000... (Ctrl+C to stop)
start "" "http://localhost:8000"
%PY% scripts\report_server.py
pause
