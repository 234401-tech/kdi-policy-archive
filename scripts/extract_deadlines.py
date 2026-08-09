# -*- coding: utf-8 -*-
"""보도자료 본문에서 마감·시행 일정을 추출해 docs/data/deadlines.json 생성.

최근 60일 수집분을 대상으로 정규식 기반 날짜 추출:
  "8.31.(월)까지" / "8월 31일까지" / "~8.14" / "9.1일부터 시행" 류.
근거 문장(source)을 함께 저장해 캘린더에서 원문 확인 가능(추출 오류 대비).
사용: python scripts/extract_deadlines.py
"""
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "docs" / "data" / "archive.json"
OUT = ROOT / "docs" / "data" / "deadlines.json"
KST = timezone(timedelta(hours=9))

# 날짜 패턴: (그룹: 월, 일)
DATE_PATS = [
    re.compile(r"(\d{1,2})\s?\.\s?(\d{1,2})\s?\.?\s?\(?[월화수목금토일]?\)?\s?까지"),
    re.compile(r"(\d{1,2})월\s?(\d{1,2})일\s?\(?[월화수목금토일]?\)?\s?까지"),
    re.compile(r"[~∼]\s?(\d{1,2})\s?\.\s?(\d{1,2})"),
    re.compile(r"[~∼]\s?(\d{1,2})월\s?(\d{1,2})일"),
    re.compile(r"(\d{1,2})\s?\.\s?(\d{1,2})\s?\.?\s?\(?[월화수목금토일]?\)?\s?(?:일?부터)?\s?(?:본격\s?)?시행"),
    re.compile(r"(\d{1,2})월\s?(\d{1,2})일\s?\(?[월화수목금토일]?\)?\s?(?:부터)?\s?시행"),
]
TYPE_RULES = [
    ("접수마감", ["접수", "신청", "공모", "모집", "제출", "응모"]),
    ("의견제출", ["입법예고", "행정예고", "의견"]),
    ("신고·납부", ["신고", "납부"]),
    ("시행", ["시행"]),
]


def infer_year(m, d, base):
    """월·일만 있는 날짜의 연도 추정: 기준일에서 -2~+10개월 창."""
    for y in (base.year - 1, base.year, base.year + 1):
        try:
            cand = date(y, m, d)
        except ValueError:
            continue
        if -60 <= (cand - base).days <= 300:
            return cand
    return None


def classify(ctx):
    for label, kws in TYPE_RULES:
        if any(k in ctx for k in kws):
            return label
    return "마감"


def main():
    data = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    today = datetime.now(KST).date()
    cutoff = (today - timedelta(days=60)).isoformat()
    events, seen = [], set()

    for it in data.get("items", []):
        if (it.get("collected_at") or "") < cutoff or it.get("muted") or it.get("dup_of"):
            continue
        text = (it.get("title") or "") + "\n" + (it.get("description") or "")
        base = datetime.fromisoformat(it["collected_at"]).date() if it.get("collected_at") else today
        for pat in DATE_PATS:
            for m in pat.finditer(text):
                mo, dy = int(m.group(1)), int(m.group(2))
                if not (1 <= mo <= 12 and 1 <= dy <= 31):
                    continue
                d = infer_year(mo, dy, base)
                if not d or d < today - timedelta(days=3) or d > today + timedelta(days=210):
                    continue
                s, e = max(0, m.start() - 45), min(len(text), m.end() + 25)
                ctx = re.sub(r"\s+", " ", text[s:e]).strip()
                etype = classify(ctx)
                key = (d.isoformat(), it["id"], etype)
                if key in seen:
                    continue
                seen.add(key)
                events.append({
                    "date": d.isoformat(),
                    "type": etype,
                    "title": it["title"],
                    "link": it["link"],
                    "score": it.get("pt_score", 0),
                    "source": ctx,
                })
    # 같은 자료의 같은 날짜 유형 중복 제거 후 날짜순
    events.sort(key=lambda x: (x["date"], -x["score"]))
    OUT.write_text(json.dumps({
        "generated_at": datetime.now(KST).isoformat(),
        "events": events,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    upcoming = [e for e in events if e["date"] >= today.isoformat()]
    print(f"일정 {len(events)}건 추출 (다가오는 일정 {len(upcoming)}건)")


if __name__ == "__main__":
    main()
