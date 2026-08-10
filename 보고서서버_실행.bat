@echo off
chcp 65001 >nul
rem ── 주간 정책동향 보고서 서버 (인코딩 전환 직후 줄은 이 rem이 흡수) ──
title 정책보고서서버 - 닫으면 종료
cd /d "%~dp0"

echo [1/3] 최신 데이터 확인 중...
git pull --rebase --autostash 2>nul
if errorlevel 1 echo        (원격 갱신 실패 - 기존 데이터로 진행합니다)

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version >nul 2>nul
if errorlevel 1 (
    echo.
    echo  [오류] Python을 찾을 수 없습니다.
    echo         https://www.python.org 에서 설치한 뒤 다시 실행해주세요.
    echo.
    pause
    exit /b 1
)

echo [2/3] 기존 서버 정리...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /f /pid %%P >nul 2>nul

echo [3/3] 서버 시작 — 준비되면 브라우저가 자동으로 열립니다.
echo.
echo  ┌─ 이 창이 보고서 서버입니다 ──────────────────
echo  │  닫으면 서버 종료, 계속 쓰려면 최소화해 두세요.
echo  │
echo  │  아카이브: http://localhost:8000/
echo  │  보고서:   http://localhost:8000/report.html
echo  │  팀 공유:  https://234401-tech.github.io/kdi-policy-archive/
echo  │  로그:     weekly_report\server.log
echo  └───────────────────────────────────────────
echo.
rem 도우미: 서버가 응답하는 순간 브라우저를 열고 스스로 닫힘(최대 30초 시도)
start "브라우저열기" /min cmd /c "for /l %%I in (1,1,30) do (curl -s -o nul --max-time 1 http://localhost:8000/api/ping 2>nul && start http://localhost:8000/ && exit || ping -n 2 127.0.0.1 >nul)"
%PY% scripts\report_server.py > "%~dp0weekly_report\server.log" 2>&1

echo.
echo  서버가 종료되었습니다. (새로 실행했거나, 오류일 수 있습니다)
echo  오류가 의심되면 아래 최근 로그를 확인하세요:
echo  ─────────────────────────────────────────
powershell -NoProfile -Command "Get-Content 'weekly_report\server.log' -Tail 6 -Encoding UTF8" 2>nul
echo  ─────────────────────────────────────────
echo  이 창은 닫으셔도 됩니다.
pause >nul
