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
import threading
import time
from datetime import datetime
from pathlib import Path


try:  # 리다이렉트된 로그 파일도 한글이 깨지지 않게
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DOCX_BUILDER = ROOT / "weekly_report" / "build_report_docx.js"
KEY_FILE = ROOT / "weekly_report" / "hasa_key.txt"
PORT = int(os.environ.get("REPORT_PORT", "8000"))

# HASA 키: 환경변수 없으면 키파일에서 로드
if not os.environ.get("HASA_API_KEY") and KEY_FILE.exists():
    # utf-8-sig: 메모장이 BOM을 붙여 저장해도 키 앞에 보이지 않는 문자가 섞이지 않게
    os.environ["HASA_API_KEY"] = KEY_FILE.read_text(encoding="utf-8-sig").strip()
os.environ.setdefault("HASA_MODEL", "exaone-4.0-32b")

# build_weekly_report.hasa_ai 재사용
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from build_weekly_report import hasa_ai
except Exception:
    hasa_ai = None


AI_CACHE = {}  # {(start, end, total): AI 요약} — 메모리 + 디스크 이중화(서버 재시작에도 유지)
AI_CACHE_DIR = ROOT / "weekly_report" / ".ai_cache"
AI_INFLIGHT = {}   # 같은 기간 동시 요청 합치기(탭 여러 개 → API 호출 1번)
AI_PROGRESS = {}   # {ckey: {"done": n, "total": m, "current": 부처명}} — 진행률 표시용
AI_LOCK = threading.Lock()


def ai_cache_get(key):
    if key in AI_CACHE:
        return AI_CACHE[key]
    p = AI_CACHE_DIR / f"{key[0]}_{key[1]}_{key[2]}.json"
    if p.exists():
        try:
            ai = json.loads(p.read_text(encoding="utf-8"))
            AI_CACHE[key] = ai
            return ai
        except Exception:
            pass
    return None


def ai_cache_put(key, ai):
    AI_CACHE[key] = ai
    try:
        AI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (AI_CACHE_DIR / f"{key[0]}_{key[1]}_{key[2]}.json").write_text(
            json.dumps(ai, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def make_hwpx(report):
    """보고서 dict → hwpx 바이트. 실패 시 예외."""
    tmp = Path(tempfile.mkdtemp(prefix="hwpx_"))
    js = tmp / "r.json"
    docx = tmp / "report.docx"
    hwpx = tmp / "report.hwpx"
    js.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

    # 1) JSON → docx (node + docx 패키지: weekly_report/node_modules)
    # encoding 미지정 시 자식 프로세스의 UTF-8 한글 출력을 cp949로 읽다가
    # UnicodeDecodeError로 리더 스레드가 죽음 → utf-8 + replace로 고정
    log("HWPX 1/2: Word(docx) 생성 중...")
    r = subprocess.run(["node", str(DOCX_BUILDER), str(js), str(docx)],
                       capture_output=True, encoding="utf-8", errors="replace",
                       timeout=120)
    if r.returncode != 0 or not docx.exists():
        raise RuntimeError(f"docx 생성 실패: {(r.stderr or '')[:300]}")

    # 2) docx → hwpx (한글 COM, headless)
    log("HWPX 2/2: 한글(HWP)로 변환 중...")
    ps = f'''
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
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
                        capture_output=True, encoding="utf-8", errors="replace",
                        timeout=90)
    if not hwpx.exists():
        raise RuntimeError(f"hwpx 변환 실패(한글 승인창 확인): {(r2.stderr or '')[:300]}")
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
        if self.path.startswith("/api/ai/progress"):
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            try:
                key = (q.get("start", [None])[0], q.get("end", [None])[0],
                       int(q.get("total", ["0"])[0]))
            except ValueError:
                key = None
            self._json(AI_PROGRESS.get(key) or {})
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/ai"):
            t0 = time.time()
            log("AI 요약 요청 받음")
            try:
                if not hasa_ai:
                    raise RuntimeError("build_weekly_report 임포트 실패")
                if not os.environ.get("HASA_API_KEY"):
                    raise RuntimeError("HASA_API_KEY 없음(weekly_report/hasa_key.txt 확인)")
                n = int(self.headers.get("Content-Length", 0))
                report = json.loads(self.rfile.read(n).decode("utf-8"))
                ckey = (report.get("start"), report.get("end"), report.get("total"))
                ai = ai_cache_get(ckey)
                if ai is not None:
                    log("AI 요약: 캐시 재사용 (즉시 응답)")
                else:
                    with AI_LOCK:
                        ev = AI_INFLIGHT.get(ckey)
                        leader = ev is None
                        if leader:
                            ev = AI_INFLIGHT[ckey] = threading.Event()
                    if leader:
                        def _prog(dept, done, total):
                            AI_PROGRESS[ckey] = {"done": done, "total": total, "current": dept}
                        try:
                            ai = hasa_ai(report, progress=_prog)
                            if ai:
                                ai_cache_put(ckey, ai)
                        finally:
                            with AI_LOCK:
                                AI_INFLIGHT.pop(ckey, None)
                            AI_PROGRESS.pop(ckey, None)
                            ev.set()
                        log(f"AI 요약 {'완료' if ai else '결과 없음'} ({time.time()-t0:.1f}초)")
                    else:
                        log("AI 요약: 같은 기간 요청 진행 중 — 완료 대기(중복 API 호출 방지)")
                        ev.wait(timeout=600)
                        ai = ai_cache_get(ckey)
                if not ai:
                    raise RuntimeError("AI 요약 생성 실패 — API 사용량 제한(429) 가능성. 잠시 후 다시 시도하세요.")
                payload, code = {"ok": True, "ai": ai}, 200
            except Exception as e:
                log(f"AI 요약 실패: {str(e)[:200]}")
                payload, code = {"ok": False, "error": str(e)[:400]}, 500
            try:
                self._json(payload, code=code)
            except OSError:
                log("브라우저 연결이 끊겨 응답을 못 보냈습니다(새로고침/이탈). "
                    "같은 기간을 다시 생성하면 캐시로 즉시 적용됩니다.")
            return
        if self.path.startswith("/api/hwpx"):
            t0 = time.time()
            try:
                n = int(self.headers.get("Content-Length", 0))
                report = json.loads(self.rfile.read(n).decode("utf-8"))
                log(f"HWPX 변환 요청 받음 ({report.get('start','?')}~{report.get('end','?')})")
                data = make_hwpx(report)
                label = report.get("weekLabel", "주간보고서")
                fname = f"{label}_정부정책_{report.get('start','')}_{report.get('end','')}.hwpx"
                log(f"HWPX 완료: {fname} ({len(data)//1024}KB, {time.time()-t0:.1f}초)")
                self.send_response(200)
                self.send_header("Content-Type", "application/hwp+zip")
                # RFC 5987 (한글 파일명)
                self.send_header("Content-Disposition",
                                 "attachment; filename*=UTF-8''" + _urlq(fname))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                log(f"HWPX 실패: {str(e)[:200]}")
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


class _BaseServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # 브라우저 새로고침/탭 닫기로 끊긴 연결은 정상 상황 — traceback 소음 제거
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError,
                            BrokenPipeError, TimeoutError)):
            return
        log(f"요청 처리 오류 ({client_address[0]}): {exc!r}")

    def server_bind(self):
        # HTTPServer.server_bind 대체 — 구형 파이썬 + 한글 PC이름 조합에서
        # getfqdn()이 UnicodeDecodeError로 죽는 것을 방어
        socketserver.TCPServer.server_bind(self)
        host, port = self.socket.getsockname()[:2]
        try:
            self.server_name = socket.getfqdn(host)
        except Exception:
            self.server_name = "localhost"
        self.server_port = port


class Server(_BaseServer):
    """IPv6+IPv4 겸용(dualstack) — 브라우저의 localhost(::1) 접속도 처리."""
    address_family = socket.AF_INET6

    def server_bind(self):
        try:
            # Windows용 Python 3.7 이하에는 IPPROTO_IPV6 상수가 없음 → AttributeError
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except (AttributeError, OSError):
            pass
        super().server_bind()


def _lan_ip():
    """팀 접속 안내용 내부 IP (오프라인이면 None)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


if __name__ == "__main__":
    ai_on = bool(hasa_ai and os.environ.get("HASA_API_KEY"))
    lan = _lan_ip()
    print("─" * 50)
    print("  주간 정책동향 보고서 서버  (Ctrl+C로 종료)")
    print(f"   · 이 PC    : http://localhost:{PORT}/report.html")
    if lan:
        print(f"   · 팀 접속  : http://{lan}:{PORT}/report.html (같은 네트워크)")
    print(f"   · HWPX 저장: 가능(한글 필요)   AI 요약: {'가능' if ai_on else '키 없음 → 규칙 기반'}")
    print("─" * 50)
    try:
        srv = Server(("::", PORT), Handler)            # IPv6+IPv4 동시 수신
    except (AttributeError, OSError, ValueError):
        srv = _BaseServer(("0.0.0.0", PORT), Handler)  # IPv6 미지원 환경 폴백
    srv.serve_forever()
