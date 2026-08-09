# -*- coding: utf-8 -*-
"""로컬 보고서 서버 — 정적 페이지(docs/) 제공 + HWPX 생성 API.

report.html 의 'HWPX 저장' 버튼이 현재 보고서 JSON을 POST /api/hwpx 로 보내면:
  보고서 JSON → (node) build_report_docx.js → docx → (한글 COM) → hwpx
로 변환해 내려준다. 한글이 설치된 PC에서만 동작(hwpx는 한글 전용 포맷).

실행:
  python scripts/report_server.py         # http://localhost:8000/report.html
※ 최초 1회 한글 '스크립트 접근 허용'을 눌러야 이후 자동 변환됨.
"""
import http.server
import json
import os
import socket
import socketserver
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DOCX_BUILDER = ROOT / "weekly_report" / "build_report_docx.js"
KEY_FILE = ROOT / "weekly_report" / "hasa_key.txt"
PORT = int(os.environ.get("REPORT_PORT", "8000"))

# HASA 키: 환경변수 없으면 키파일에서 로드
if not os.environ.get("HASA_API_KEY") and KEY_FILE.exists():
    os.environ["HASA_API_KEY"] = KEY_FILE.read_text(encoding="utf-8").strip()
os.environ.setdefault("HASA_MODEL", "exaone-4.0-32b")

# build_weekly_report.hasa_ai 재사용
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from build_weekly_report import hasa_ai
except Exception:
    hasa_ai = None


def make_hwpx(report):
    """보고서 dict → hwpx 바이트. 실패 시 예외."""
    tmp = Path(tempfile.mkdtemp(prefix="hwpx_"))
    js = tmp / "r.json"
    docx = tmp / "report.docx"
    hwpx = tmp / "report.hwpx"
    js.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

    # 1) JSON → docx (node + docx 패키지: weekly_report/node_modules)
    r = subprocess.run(["node", str(DOCX_BUILDER), str(js), str(docx)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not docx.exists():
        raise RuntimeError(f"docx 생성 실패: {r.stderr[:300]}")

    # 2) docx → hwpx (한글 COM, headless)
    ps = f'''
$ErrorActionPreference="Stop"
Get-Process -Name Hwp -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Start-Sleep -Milliseconds 400
$h = New-Object -ComObject HWPFrame.HwpObject
$h.XHwpWindows.Item(0).Visible = $false
[void]$h.Open("{docx.as_posix()}", "", "forceopen:true")
[void]$h.SaveAs("{hwpx.as_posix()}", "HWPX", "")
$h.Quit()
'''
    r2 = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                        capture_output=True, text=True, timeout=90)
    if not hwpx.exists():
        raise RuntimeError(f"hwpx 변환 실패(한글 승인창 확인): {r2.stderr[:300]}")
    return hwpx.read_bytes()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DOCS), **kw)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/api/ping"):
            self._json({"ok": True, "hwpx": True,
                        "ai": bool(hasa_ai and os.environ.get("HASA_API_KEY"))})
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/ai"):
            try:
                if not hasa_ai:
                    raise RuntimeError("build_weekly_report 임포트 실패")
                if not os.environ.get("HASA_API_KEY"):
                    raise RuntimeError("HASA_API_KEY 없음(weekly_report/hasa_key.txt 확인)")
                n = int(self.headers.get("Content-Length", 0))
                report = json.loads(self.rfile.read(n).decode("utf-8"))
                ai = hasa_ai(report)
                self._json({"ok": True, "ai": ai})
            except Exception as e:
                self._json({"ok": False, "error": str(e)[:400]}, code=500)
            return
        if self.path.startswith("/api/hwpx"):
            try:
                n = int(self.headers.get("Content-Length", 0))
                report = json.loads(self.rfile.read(n).decode("utf-8"))
                data = make_hwpx(report)
                label = report.get("weekLabel", "주간보고서")
                fname = f"{label}_정부정책_{report.get('start','')}_{report.get('end','')}.hwpx"
                self.send_response(200)
                self.send_header("Content-Type", "application/hwp+zip")
                # RFC 5987 (한글 파일명)
                self.send_header("Content-Disposition",
                                 "attachment; filename*=UTF-8''" + _urlq(fname))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self._json({"ok": False, "error": str(e)[:400]}, code=500)
            return
        self.send_error(404)

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


def _urlq(s):
    from urllib.parse import quote
    return quote(s, safe="")


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """IPv6+IPv4 겸용(dualstack) — 브라우저의 localhost(::1) 접속도 처리."""
    daemon_threads = True
    address_family = socket.AF_INET6

    def server_bind(self):
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except OSError:
            pass
        super().server_bind()


if __name__ == "__main__":
    print(f"보고서 서버 실행: http://localhost:{PORT}/report.html")
    print("HWPX 저장 버튼 사용 가능(한글 필요). Ctrl+C로 종료.")
    try:
        srv = Server(("::", PORT), Handler)      # IPv6+IPv4 동시 수신
    except OSError:
        class V4(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
        srv = V4(("0.0.0.0", PORT), Handler)     # IPv6 미지원 환경 폴백
    srv.serve_forever()
