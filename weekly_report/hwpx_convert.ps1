# 주간 보고서 docx/doc → 네이티브 한글 hwpx (+ pdf) 변환
# 사용:
#   powershell -ExecutionPolicy Bypass -File hwpx_convert.ps1 "보고서.docx"
#   (인자 없으면 이 폴더에서 가장 최근 .docx 를 변환)
# 처음 실행 시 한글 '스크립트 보안 허용' 창이 뜨면 [허용]을 누르세요(1회).
param([string]$File)

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $File) {
    $latest = Get-ChildItem -Path $dir -Filter *.docx | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) { Write-Host "변환할 .docx 파일이 없습니다."; exit 1 }
    $File = $latest.FullName
}
if (-not (Test-Path $File)) { Write-Host "파일 없음: $File"; exit 1 }

$File = (Resolve-Path $File).Path
$hwpx = [System.IO.Path]::ChangeExtension($File, ".hwpx")
$pdf  = [System.IO.Path]::ChangeExtension($File, ".pdf")
Write-Host "변환: $File"

# 이전에 멈춘 한글 인스턴스 정리
Get-Process -Name Hwp -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

$h = New-Object -ComObject HWPFrame.HwpObject
# 보안 모듈이 있으면 등록(없어도 진행) — 있으면 보안창이 안 뜸
try { $h.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule") | Out-Null } catch {}
$h.XHwpWindows.Item(0).Visible = $true    # 보안창 클릭이 필요할 수 있어 보이게 실행

if ($h.Open($File, "", "forceopen:true")) {
    $okH = $h.SaveAs($hwpx, "HWPX", "")
    $okP = $h.SaveAs($pdf, "PDF", "")
    $h.Quit()
    Start-Sleep -Milliseconds 500
    if (Test-Path $hwpx) { Write-Host "완료: $hwpx  ($((Get-Item $hwpx).Length) bytes)" }
    if (Test-Path $pdf)  { Write-Host "완료: $pdf" }
} else {
    Write-Host "열기 실패"; $h.Quit()
}
