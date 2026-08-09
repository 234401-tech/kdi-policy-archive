@echo off
chcp 65001 >nul
rem 주간 보고서 docx -> 한글 hwpx 변환
rem 사용법: 이 배치파일 위에 .docx 파일을 끌어다 놓거나, 그냥 더블클릭(폴더 내 최신 docx 변환)
setlocal
set "PS=%~dp0hwpx_convert.ps1"
if "%~1"=="" (
  powershell -ExecutionPolicy Bypass -NoProfile -File "%PS%"
) else (
  powershell -ExecutionPolicy Bypass -NoProfile -File "%PS%" "%~1"
)
echo.
pause
