@echo off
chcp 65001 >nul
rem 주간 정책동향 보고서 로컬 서버 실행 (HWPX 저장 + AI 요약 지원)
rem 한글(HWP)이 설치된 이 PC에서만 HWPX 생성이 됩니다.
cd /d "%~dp0"
echo 보고서 서버를 시작합니다... (이 창을 닫으면 서버가 종료됩니다)
start "정책보고서서버" /min cmd /c "python scripts\report_server.py & pause"
timeout /t 2 /nobreak >nul
start "" "http://localhost:8000/report.html"
echo.
echo 브라우저에서 http://localhost:8000/report.html 이 열립니다.
echo 서버는 최소화된 창(정책보고서서버)에서 실행 중입니다.
