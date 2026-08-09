# -*- coding: utf-8 -*-
"""아카이브 항목에 포항 관련도 점수·숨김·중복 표시를 부여한다.

- 관련도 점수(pt_score, 0~100): docs/data/profile.json 의 그룹별 키워드 매칭 합산.
  그룹당 1회 가산, 제목에서 매칭되면 title_bonus 추가. 근거는 pt_reasons에 그룹명으로 기록.
- 숨김(muted): docs/data/mute_rules.json 패턴이 제목에 있으면 true.
- 중복(dup_of): 제목 토큰 유사도(자카드) 0.75 이상 + 수집일 5일 이내면 나중 항목에 원본 id 기록.

기본은 미처리 항목만 갱신하며, 규칙 변경 후에는 --all 로 전체 재계산.
사용: python scripts/score.py [--all]
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "docs" / "data" / "archive.json"
PROFILE = ROOT / "docs" / "data" / "profile.json"
MUTE = ROOT / "docs" / "data" / "mute_rules.json"

SCHEMA_VER = 1  # 채점 로직/규칙 스키마 버전 (pt_ver로 저장)


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def score_item(item, profile):
    title = item.get("title") or ""
    desc = (item.get("description") or "")[:1500]
    body = title + "\n" + desc
    score, reasons = 0, []
    for g in profile.get("groups", []):
        hit_title = any(t in title for t in g["terms"])
        hit = hit_title or any(t in desc for t in g["terms"])
        if hit:
            score += g["weight"] + (profile.get("title_bonus", 0) if hit_title else 0)
            reasons.append(g["label"])
    return min(score, profile.get("cap", 100)), reasons


def is_muted(item, rules):
    if not rules.get("enabled", True):
        return False
    fields = rules.get("fields", ["title"])
    hay = " ".join(item.get(f) or "" for f in fields)
    for p in rules.get("patterns", []):
        if p.startswith("re:"):  # 정규식 패턴 (예: "re:축사$")
            if re.search(p[3:], hay):
                return True
        elif p in hay:
            return True
    return False


_norm_re = re.compile(r"[\s\[\](){}<>『』「」〈〉·ㆍ,.\-–—:;!?'\"“”‘’…※★]+")


def tokens(title):
    return set(t for t in _norm_re.split(title or "") if len(t) >= 2)


def mark_dups(items):
    """수집일 기준 정렬 후, 5일 창 안에서 제목 자카드 유사도 0.75↑ 항목을 중복으로 표시."""
    seq = sorted(items, key=lambda x: x.get("collected_at") or "")
    toks = {it["id"]: tokens(it.get("title")) for it in seq}
    days = {it["id"]: (it.get("collected_at") or "")[:10] for it in seq}
    dup_count = 0
    window = []  # (id, item) 최근 항목들
    for it in seq:
        it.pop("dup_of", None)
        d = days[it["id"]]
        window = [(i, w) for i, w in window if _day_diff(days[i], d) <= 5]
        tk = toks[it["id"]]
        if tk:
            for pid, _ in window:
                pt = toks[pid]
                if not pt:
                    continue
                inter = len(tk & pt)
                union = len(tk | pt)
                if union and inter / union >= 0.75:
                    it["dup_of"] = pid
                    dup_count += 1
                    break
        if "dup_of" not in it:
            window.append((it["id"], it))
    return dup_count


def _day_diff(a, b):
    from datetime import date
    try:
        ya, ma, da = map(int, a.split("-"))
        yb, mb, db = map(int, b.split("-"))
        return abs((date(yb, mb, db) - date(ya, ma, da)).days)
    except Exception:
        return 999


THREADS_OUT = ROOT / "docs" / "data" / "threads.json"
_quote_re = re.compile(r"[「『]([^」』]{2,30})[」』]")


def build_threads(items):
    """제목의 「정책명」 인용구가 같은 발표들을 하나의 '정책 스레드'로 묶는다.
    (예: 「반도체특별법」 발표→시행령→시행 — 타임라인 추적의 기반)"""
    from collections import defaultdict
    groups = defaultdict(list)
    for it in items:
        if it.get("muted") or it.get("dup_of"):
            continue
        for m in _quote_re.finditer(it.get("title") or ""):
            key = re.sub(r"\s+", "", m.group(1))
            groups[key].append(it)
    threads = []
    for key, its in groups.items():
        uniq = {i["id"]: i for i in its}.values()
        if len(uniq) < 2:
            continue
        entries = sorted(({
            "title": i["title"], "link": i["link"],
            "date": (i.get("collected_at") or "")[:10],
            "score": i.get("pt_score", 0),
        } for i in uniq), key=lambda x: x["date"])
        threads.append({
            "phrase": key, "count": len(entries),
            "first": entries[0]["date"], "last": entries[-1]["date"],
            "max_score": max(e["score"] for e in entries),
            "items": entries,
        })
    threads.sort(key=lambda t: (t["max_score"] >= 40, t["last"], t["count"]), reverse=True)
    THREADS_OUT.write_text(json.dumps(
        {"generated_at": __import__("datetime").datetime.now().isoformat(),
         "threads": threads[:60]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return len(threads)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="전체 항목 재계산 (규칙 변경 후)")
    args = ap.parse_args()

    archive = load(ARCHIVE, {"items": []})
    profile = load(PROFILE, {"groups": []})
    rules = load(MUTE, {"patterns": []})
    items = archive.get("items", [])

    updated = 0
    for it in items:
        if not args.all and it.get("pt_ver") == SCHEMA_VER:
            continue
        s, reasons = score_item(it, profile)
        it["pt_score"] = s
        it["pt_reasons"] = reasons
        it["muted"] = is_muted(it, rules)
        it["pt_ver"] = SCHEMA_VER
        updated += 1

    dups = mark_dups(items)
    threads = build_threads(items)

    ARCHIVE.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    scored = [it for it in items if it.get("pt_score", 0) >= 70]
    muted = sum(1 for it in items if it.get("muted"))
    print(f"채점 {updated}건 갱신 / 관련도 70+ {len(scored)}건 / 숨김 {muted}건 / 중복 {dups}건 / 스레드 {threads}개")


if __name__ == "__main__":
    main()
