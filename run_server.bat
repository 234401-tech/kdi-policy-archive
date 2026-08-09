@echo off
chcp 65001 >nul
rem 아카이브 + 주간 보고서 로컬 서버 (HWPX 저장·AI 요약 지원 서버로 통합)
rem 예전 python -m http.server 방식은 보고서 API가 없어 report_server.py로 통일함.
cd /d "%~dp0"
echo Starting local server on port 8000... (Ctrl+C to stop)
start "" "http://localhost:8000"
python scripts\report_server.py
pause
