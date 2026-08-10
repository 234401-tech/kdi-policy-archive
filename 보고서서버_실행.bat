@echo off
chcp 65001 >nul
title 주간보고서 실행기
rem ── 주간 정책동향 보고서 (통합 실행) ──
rem 더블클릭 한 번: 최신 데이터 받기 → 서버 실행 → 준비 확인 → 브라우저 열기
rem HWPX 저장은 한글(HWP)이 설치된 이 PC에서만 동작합니다.
cd /d "%~dp0"

echo [1/4] 최신 데이터 확인 중...
git pull --rebase --autostash 2>nul
if errorlevel 1 echo        (원격 갱신 실패 - 기존 데이터로 진행합니다)

rem Python 선택 + 설치 확인
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

echo [2/4] 서버 준비...
set "CODE="
for /f %%A in ('curl -s -o nul -w "%%{http_code}" --max-time 1 http://localhost:8000/api/ping 2^>nul') do set "CODE=%%A"
if "%CODE%"=="200" (
    echo        기존 서버를 재시작합니다 ^(항상 최신 코드로^)...
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /f /pid %%P >nul 2>nul
    ping -n 2 127.0.0.1 >nul
)
rem 로그는 파일로 기록(콘솔 클릭 시 출력이 얼어 서버가 멈추는 Windows 문제 방지)
start "정책보고서서버" /min cmd /c "%PY% scripts\report_server.py > "%~dp0weekly_report\server.log" 2>&1"

echo [3/4] 서버 응답 확인 중...
set "OK="
for /l %%I in (1,1,20) do (
    if not defined OK (
        for /f %%A in ('curl -s -o nul -w "%%{http_code}" --max-time 1 http://localhost:8000/api/ping 2^>nul') do if "%%A"=="200" set "OK=1"
        if not defined OK ping -n 2 127.0.0.1 >nul
    )
)
if not defined OK (
    echo.
    echo  [오류] 서버가 시작되지 않았습니다. 최근 로그:
    echo  ─────────────────────────────────────────
    powershell -NoProfile -Command "Get-Content 'weekly_report\server.log' -Tail 6 -Encoding UTF8" 2>nul
    echo  ─────────────────────────────────────────
    echo  자세한 내용: weekly_report\server.log
    echo.
    pause
    exit /b 1
)

rem AI 요약 가능 여부 확인(키 인식 상태)
set "AI=키 없음 - weekly_report\hasa_key.txt 저장 시 자동 요약"
for /f %%A in ('powershell -NoProfile -Command "(Invoke-RestMethod http://localhost:8000/api/ping -TimeoutSec 3).ai" 2^>nul') do if /i "%%A"=="True" set "AI=자동 요약 가능"

echo [4/4] 브라우저 열기...
start "" "http://localhost:8000/"
echo.
echo  ┌─ 준비 완료 ─────────────────────────────
echo  │  AI 요약:  %AI%
echo  │  아카이브: http://localhost:8000/
echo  │  보고서:   http://localhost:8000/report.html
echo  │  팀 공유:  https://234401-tech.github.io/kdi-policy-archive/
echo  │  종료:     작업표시줄 '정책보고서서버' 창 닫기
echo  │  로그:     weekly_report\server.log
echo  └─────────────────────────────────────────
echo.
echo  이 창은 잠시 후 자동으로 닫힙니다.
ping -n 7 127.0.0.1 >nul
