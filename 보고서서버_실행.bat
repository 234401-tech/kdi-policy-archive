@echo off
chcp 65001 >nul
rem 주간 정책동향 보고서 로컬 서버 실행 (HWPX 저장 + AI 요약 지원)
rem 한글(HWP)이 설치된 이 PC에서만 HWPX 생성이 됩니다.
cd /d "%~dp0"
echo 보고서 서버를 시작합니다...  (종료: 이 창에서 Ctrl+C)
start "" "http://localhost:8000/report.html"
python scripts\report_server.py
pause
