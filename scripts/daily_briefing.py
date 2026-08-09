# -*- coding: utf-8 -*-
"""조간 브리핑 생성기 — 어제(24h) 수집분을 요약해 docs/data/briefing.json 저장.

- HASA_API_KEY 있으면 exaone으로 포항 관점 3줄 요약, 없으면 관련도 상위 규칙 기반.
- (선택) SMTP_HOST/SMTP_USER/SMTP_PASS/MAIL_TO 설정 시 이메일 발송.
- (선택) KAKAOWORK_WEBHOOK 설정 시 카카오워크 채널로 발송.

사용: python scripts/daily_briefing.py [--hours 24] [--no-send]
"""
import argparse
import json
import os
import re
import smtplib
import urllib.request
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.header import Header
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "docs" / "data" / "archive.json"
OUT = ROOT / "docs" / "data" / "briefing.json"
KST = timezone(timedelta(hours=9))


def recent_items(hours):
    data = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    cutoff = (datetime.now(KST) - timedelta(hours=hours)).isoformat()
    items = [it for it in data.get("items", [])
             if (it.get("collected_at") or "") >= cutoff
             and not it.get("muted") and not it.get("dup_of")]
    items.sort(key=lambda x: -x.get("pt_score", 0))
    return items


def ai_bullets(items):
    """HASA API로 포항 관점 3줄 브리핑. 실패/키 없음 → None."""
    key = os.environ.get("HASA_API_KEY", "").strip()
    if not key or not items:
        return None, None
    base = os.environ.get("HASA_API_BASE", "https://open.hasa.re.kr/v1").rstrip("/")
    model = os.environ.get("HASA_MODEL", "exaone-4.0-32b")
    digest = "\n".join(
        f"- [{it.get('pt_score',0)}점] {it['title']}: {(it.get('description') or '')[:200]}"
        for it in items[:12])
    body = {
        "model": model, "temperature": 0.3, "max_tokens": 700,
        "messages": [
            {"role": "system", "content": "너는 포항테크노파크 미래전략팀의 정책분석가다. 반드시 유효한 JSON 배열만 출력한다."},
            {"role": "user", "content":
             "다음은 어제 수집된 정부 정책자료다(관련도 점수 포함). 포항·경북 산업(이차전지·철강·수소·AI·소부장) "
             "관점에서 가장 중요한 것 3가지를 골라 각각 한 문장으로 요약하라.\n"
             '출력 형식: ["요약1", "요약2", "요약3"] (JSON 배열만)\n\n' + digest},
        ],
    }
    try:
        req = urllib.request.Request(
            base + "/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            out = json.loads(r.read().decode())
        txt = out["choices"][0]["message"]["content"].strip()
        txt = re.sub(r"^```json?\s*|```\s*$", "", txt).strip()
        m = re.search(r"\[.*\]", txt, re.S)
        bullets = json.loads(m.group(0) if m else txt)
        bullets = [str(b).strip() for b in bullets if str(b).strip()][:3]
        return (bullets or None), model
    except Exception as e:
        print(f"AI 요약 실패(규칙 기반으로 대체): {str(e)[:100]}")
        return None, None


def rule_bullets(items):
    out = []
    for it in items[:3]:
        reasons = ", ".join(it.get("pt_reasons", [])[:3])
        tail = f" (관련: {reasons})" if reasons else ""
        out.append(f"{it['title']}{tail}")
    return out


def send_email(subject, html):
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    pw = os.environ.get("SMTP_PASS", "").strip()
    to = [a.strip() for a in os.environ.get("MAIL_TO", "").split(",") if a.strip()]
    if not (host and user and pw and to):
        return False
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = user
    msg["To"] = ", ".join(to)
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls()
        s.login(user, pw)
        s.sendmail(user, to, msg.as_string())
    return True


def send_kakaowork(text):
    url = os.environ.get("KAKAOWORK_WEBHOOK", "").strip()
    if not url:
        return False
    req = urllib.request.Request(
        url, data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=20)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--no-send", action="store_true", help="파일 생성만, 발송 생략")
    args = ap.parse_args()

    items = recent_items(args.hours)
    today = datetime.now(KST).strftime("%Y-%m-%d")

    bullets, model = ai_bullets(items)
    if not bullets:
        bullets, model = rule_bullets(items), "rule-based"

    top = [{
        "title": it["title"], "link": it["link"],
        "score": it.get("pt_score", 0), "reasons": it.get("pt_reasons", []),
    } for it in items[:5]]

    briefing = {
        "date": today,
        "generated_at": datetime.now(KST).isoformat(),
        "window_hours": args.hours,
        "item_count": len(items),
        "model": model,
        "bullets": bullets,
        "top": top,
    }
    OUT.write_text(json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"브리핑 저장: {len(items)}건 중 요약 {len(bullets)}줄 (모델: {model})")

    if args.no_send or not items:
        return

    subject = f"[정책브리핑] {today} — 신규 {len(items)}건"
    lines_html = "".join(f"<li>{b}</li>" for b in bullets)
    top_html = "".join(
        f'<li><a href="{t["link"]}">{t["title"]}</a> <b>({t["score"]}점)</b></li>' for t in top)
    html = (f"<h3>{today} 조간 정책브리핑</h3><ul>{lines_html}</ul>"
            f"<p><b>관련도 상위</b></p><ol>{top_html}</ol>"
            f"<p style='color:#888;font-size:12px'>포항TP 정책레이더 자동 발송 · 신규 {len(items)}건</p>")
    text = f"[{today} 조간 정책브리핑]\n" + "\n".join(f"· {b}" for b in bullets) + \
           "\n\n관련도 상위:\n" + "\n".join(f"{i+1}. {t['title']} ({t['score']}점)\n{t['link']}" for i, t in enumerate(top))

    try:
        if send_email(subject, html):
            print("이메일 발송 완료")
    except Exception as e:
        print(f"이메일 발송 실패: {str(e)[:100]}")
    try:
        if send_kakaowork(text):
            print("카카오워크 발송 완료")
    except Exception as e:
        print(f"카카오워크 발송 실패: {str(e)[:100]}")


if __name__ == "__main__":
    main()
