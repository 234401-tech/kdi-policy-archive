@echo off
chcp 65001 >nul
rem ── 주간 정책동향 보고서 (통합 실행) ──
rem 더블클릭 한 번: 최신 데이터 받기 → 서버 실행 → 보고서 페이지 열기
rem HWPX 저장은 한글(HWP)이 설치된 이 PC에서만 동작합니다.
cd /d "%~dp0"

echo [1/3] 최신 데이터 확인 중...
git pull --rebase --autostash 2>nul
if errorlevel 1 echo    (원격 갱신 실패 - 기존 데이터로 진행합니다)

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")

rem 기존 서버가 있으면 종료 후 새로 시작 (항상 최신 코드로 실행되도록)
set "CODE="
for /f %%A in ('curl -s -o nul -w "%%{http_code}" --max-time 1 http://localhost:8000/api/ping 2^>nul') do set "CODE=%%A"
if "%CODE%"=="200" (
    echo [2/3] 기존 서버를 재시작합니다...
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /f /pid %%P >nul 2>nul
    timeout /t 1 /nobreak >nul
) else (
    echo [2/3] 보고서 서버 시작...
)
rem 로그는 파일로 기록(콘솔 클릭 시 출력이 얼어 서버가 멈추는 Windows 문제 방지)
start "정책보고서서버" /min cmd /c "%PY% scripts\report_server.py > "%~dp0weekly_report\server.log" 2>&1"
timeout /t 2 /nobreak >nul

echo [3/3] 브라우저 열기...
start "" "http://localhost:8000/"
echo.
echo   아카이브:  http://localhost:8000/  (첫 화면 - 상단 메뉴로 보고서/대시보드 이동)
echo   보고서:    http://localhost:8000/report.html  (HWPX 저장 버튼은 1~2초 뒤 표시)
echo   팀 공유:   https://234401-tech.github.io/kdi-policy-archive/
echo   서버 로그: KDI 정책자료\weekly_report\server.log (메모장으로 열어 확인)
echo   종료:      작업표시줄의 '정책보고서서버' 창을 닫으면 서버가 꺼집니다.
echo.
echo   이 창은 잠시 후 자동으로 닫힙니다.
timeout /t 8 >nul
