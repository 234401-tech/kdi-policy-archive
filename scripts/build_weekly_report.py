# -*- coding: utf-8 -*-
"""주간 정책동향 보고서 데이터 생성기.

아카이브(docs/data/archive.json)에서 기간 내 항목을 부처별로 분류해
docs/data/weekly/<start>_<end>.json 을 생성한다. report.html 이 이 파일을 렌더링한다.

HASA_API_KEY 환경변수가 있으면 open.hasa.re.kr(OpenAI 호환 API)로
부처별 키워드·시사점·핵심선별(ai 필드)을 생성해 포함한다.

사용:
  python scripts/build_weekly_report.py                  # 지난주 월~일
  python scripts/build_weekly_report.py --start 2026-07-27 --end 2026-08-09
"""
import argparse
import json
import os
import re
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
WEEKLY = DATA / "weekly"

CORE_DEPTS = ["재정경제부", "기획예산처", "산업통상부", "중소벤처기업부",
              "과학기술정보통신부", "기후에너지환경부"]
DEPT_PATTERNS = [
    ("재정경제부", ["재정경제부", "재경부"]),
    ("기획예산처", ["기획예산처"]),
    ("산업통상부", ["산업통상부", "산업부"]),
    ("중소벤처기업부", ["중소벤처기업부", "중기부"]),
    ("과학기술정보통신부", ["과학기술정보통신부", "과기정통부", "과기부"]),
    ("기후에너지환경부", ["기후에너지환경부", "기후부"]),
    ("금융위원회", ["금융위원회", "금융위"]),
    ("국세청", ["국세청"]),
    ("농림축산식품부", ["농림축산식품부", "농식품부"]),
    ("국토교통부", ["국토교통부", "국토부"]),
    ("고용노동부", ["고용노동부", "노동부"]),
    ("보건복지부", ["보건복지부", "복지부"]),
    ("행정안전부", ["행정안전부", "행안부"]),
    ("해양수산부", ["해양수산부", "해수부"]),
    ("교육부", ["교육부"]), ("국방부", ["국방부"]), ("외교부", ["외교부"]),
    ("법무부", ["법무부"]), ("통일부", ["통일부"]),
    ("공정거래위원회", ["공정거래위원회", "공정위"]),
    ("국가데이터처", ["국가데이터처"]), ("지식재산처", ["지식재산처"]),
    ("기상청", ["기상청"]), ("관세청", ["관세청"]), ("조달청", ["조달청"]),
    ("질병관리청", ["질병관리청"]), ("소방청", ["소방청"]),
    ("식품의약품안전처", ["식품의약품안전처", "식약처"]),
    ("산림청", ["산림청"]), ("경찰청", ["경찰청"]),
]


def detect_dept(item):
    hay = (item.get("title") or "") + "|" + (item.get("description") or "")[:300]
    for name, pats in DEPT_PATTERNS:
        if any(p in hay for p in pats):
            return name
    return "기타"


def bullets(desc):
    if not desc:
        return []
    lines = [l.strip() for l in desc.split("\n") if l.strip()]
    out = [re.sub(r"^[-ㆍ·•]\s*", "", l) for l in lines if re.match(r"^[-ㆍ·•]", l)]
    if not out:
        out = lines[:2]
    out = [l for l in out if not re.match(r"^[<(\[]?(참고|붙임|별첨)", l)]
    return [(l[:128] + "…") if len(l) > 130 else l for l in out[:3]]


def short_d(s):
    y, m, d = s.split("-")
    return f"{y[2:]}.{int(m)}.{int(d)}."


def build(start, end):
    data = json.loads((DATA / "archive.json").read_text(encoding="utf-8"))
    items = data.get("items", data if isinstance(data, list) else [])
    sel = [it for it in items if start <= (it.get("collected_at") or "")[:10] <= end]

    by_dept = {}
    for it in sel:
        by_dept.setdefault(detect_dept(it), []).append({
            "title": it.get("title"),
            "link": it.get("link"),
            "date": (it.get("collected_at") or "")[:10],
            "categories": it.get("matched_categories") or [],
            "bullets": bullets(it.get("description")),
            "desc": (it.get("description") or "")[:900],
        })
    for v in by_dept.values():
        v.sort(key=lambda x: x["date"], reverse=True)

    s = date.fromisoformat(start)
    week_label = f"{s.month}월 {(s.day - 1) // 7 + 1}주차"
    return {
        "start": start, "end": end,
        "weekLabel": week_label,
        "period": f"{short_d(start)}~{short_d(end)[3:]}",
        "total": len(sel),
        "groups": [{"dept": d, "items": by_dept[d]} for d in CORE_DEPTS if d in by_dept],
        "others": [{"dept": d, "items": v} for d, v in sorted(by_dept.items())
                   if d not in CORE_DEPTS],
        "ai": None,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def hasa_ai(report):
    """open.hasa.re.kr OpenAI 호환 API로 부처별 키워드/시사점/핵심선별 생성."""
    key = os.environ.get("HASA_API_KEY")
    if not key:
        return None
    base = os.environ.get("HASA_API_BASE", "https://open.hasa.re.kr/v1").rstrip("/")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def call(path, payload=None):
        req = urllib.request.Request(
            base + path, headers=headers,
            data=json.dumps(payload).encode() if payload else None,
            method="POST" if payload else "GET")
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())

    model = os.environ.get("HASA_MODEL")
    if not model:
        models = call("/models").get("data", [])
        if not models:
            raise RuntimeError("사용 가능한 모델 없음")
        model = models[0]["id"]

    SYS = ("너는 포항테크노파크 미래전략팀의 정책분석가다. 정부 보도자료를 팀 내부 보고서 양식에 맞춰 "
           "구조화한다. 반드시 유효한 JSON 객체 하나만 출력하고, 코드블록·설명 등 다른 텍스트는 절대 쓰지 않는다.")
    # 양식 예시(기획재정부 '성장전략 TF' — 표/‌(목적)(내용) 사용법 학습용)
    EXAMPLE = (
        '{\n'
        ' "keyword": "성장전략 TF 가동, 기업활력 제고, 한미 관세협상 대응",\n'
        ' "reports": [\n'
        '   {"idx": 0, "lead": "기존 \'비상경제점검 TF\' → \'성장전략 TF\'로 전환",\n'
        '    "points": [\n'
        '      {"h": "\'성장전략 TF\' 개요", "items": ["(목적) \'진짜성장\'을 위한 기업 활력 제고를 최우선 목표로 설정", "(내용) 기업부담 완화·규제 개선 등 종합 플랫폼 운영"]},\n'
        '      {"table": {"cols": ["분야","주요내용"], "rows": [\n'
        '        {"field": "기업지원·신산업", "content": ["투자애로 해소, 경제형벌 합리화", "AI·데이터 등 신산업 패키지 육성"]},\n'
        '        {"field": "한·미 관세협상", "content": ["자동차·상호관세 15% 인하", "3,500억불 금융패키지 조성"]}]}}\n'
        '    ],\n'
        '    "insight": "포항 철강·이차전지 기업의 대미 수출·투자 여건 변화 모니터링 필요"}\n'
        ' ]\n'
        '}')
    RULES = (
        "각 부처 자료에서 포항·경북 산업(이차전지·철강·수소·소재부품장비·AI·바이오)과 관련성이 높거나 "
        "중요한 발표를 **최대 3건**만 골라 구조화하라.\n"
        "- 각 항목: idx(위 [번호] 그대로), lead(한줄, 선택), points(배열), insight(포항·경북 시사점 한 문장, 선택).\n"
        "- points 원소는 3가지 중 하나: ① 문자열('- '항목) ② {\"h\":소제목,\"items\":[\"(목적)…\",\"(내용)…\"]} ③ {\"table\":{\"cols\":[\"분야\",\"주요내용\"],\"rows\":[{\"field\":…,\"content\":[…]}]}}.\n"
        "- 회의·대책·계획·업무보고는 소제목(h)+세부나 표를 적극 활용하고, 단순 동정·행사는 문자열 2~3개로 짧게.\n"
        "- 표는 '분야별 주요내용'이 뚜렷할 때만. 제목은 바꾸지 말고 idx로만 지정.\n"
        "- 출력 형식: {\"keyword\": \"핵심 키워드 한 줄\", \"reports\": [ ... ]}  (아래 예시와 동일 구조, 이 부처 것만)")

    keywords, reports = {}, {}
    for g in report["groups"]:
        items = g["items"][:12]
        if not items:
            continue
        digest = "\n".join(
            f"[{idx}] {i['title']}\n{(i.get('desc') or ' '.join(i['bullets'])).replace(chr(10), ' ')[:500]}"
            for idx, i in enumerate(items))
        usr = (f"[부처: {g['dept']}]  기간 {report['period']}\n{RULES}\n\n"
               f"### 예시(형식 참고용)\n{EXAMPLE}\n\n### 실제 자료\n{digest}")
        try:
            out = call("/chat/completions", {
                "model": model, "temperature": 0.2, "max_tokens": 2200,
                "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": usr}],
            })
            txt = out["choices"][0]["message"]["content"].strip()
            txt = re.sub(r"^```json?\s*|```\s*$", "", txt).strip()
            m = re.search(r"\{.*\}", txt, re.S)  # 앞뒤 잡음 제거
            data = json.loads(m.group(0) if m else txt)
            if data.get("keyword"):
                keywords[g["dept"]] = data["keyword"]
            reps = [r for r in (data.get("reports") or []) if isinstance(r.get("idx"), int)]
            if reps:
                reports[g["dept"]] = reps[:3]
            print(f"  · {g['dept']}: reports {len(reports.get(g['dept'], []))}건")
        except Exception as e:
            print(f"  · {g['dept']}: 실패({str(e)[:60]})")
    if not keywords and not reports:
        return None
    return {"keywords": keywords, "reports": reports}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start")
    ap.add_argument("--end")
    args = ap.parse_args()

    if args.start and args.end:
        start, end = args.start, args.end
    else:  # 지난주 월~일
        today = date.today()
        mon = today - timedelta(days=today.weekday() + 7)
        start, end = mon.isoformat(), (mon + timedelta(days=6)).isoformat()

    report = build(start, end)
    try:
        report["ai"] = hasa_ai(report)
        if report["ai"]:
            print("AI 요약 적용됨")
    except Exception as e:  # AI 실패는 치명적이지 않음
        print(f"AI 요약 건너뜀: {e}")

    # 저장 전 임시 desc 제거(용량 절약; AI 생성 후엔 불필요)
    for grp in (report["groups"] + report["others"]):
        for it in grp["items"]:
            it.pop("desc", None)

    WEEKLY.mkdir(parents=True, exist_ok=True)
    fname = f"{start}_{end}.json"
    (WEEKLY / fname).write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    # 인덱스 갱신
    idx_path = WEEKLY / "index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else []
    idx = [e for e in idx if e["file"] != fname]
    idx.append({
        "file": fname,
        "title": f"{report['weekLabel']} 정부정책 발표 주요 내용({report['period']})",
        "start": start, "end": end,
        "ai": bool(report["ai"]),
        "generated_at": report["generated_at"],
    })
    idx.sort(key=lambda e: e["start"])
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{fname}: {report['total']}건, 핵심부처 {len(report['groups'])}개 그룹")


if __name__ == "__main__":
    main()
