# -*- coding: utf-8 -*-
"""주간 보고서 JSON → 양식(정책 동향 양식.hwp) 스타일 HTML 렌더.

report.html 의 report-area 마크업/CSS와 동일한 구조를 서버측에서 재현한다.
이 HTML을 한글(HWP) COM으로 열어 .hwpx / .pdf 로 저장하면 네이티브 한글 문서가 된다.

사용:
  python scripts/render_report_html.py docs/data/weekly/2026-07-27_2026-08-09.json out.html
  python scripts/render_report_html.py <weekly.json> <out.html> [--ai ai.json]
"""
import argparse
import html
import json
from pathlib import Path

CSS = """
body{font-family:'Malgun Gothic','맑은 고딕',sans-serif;font-size:10pt;line-height:1.5;color:#000;margin:0;}
.rpt-head{text-align:center;font-weight:bold;font-size:11pt;margin-bottom:1pt;}
.rpt-title{text-align:center;font-weight:bold;font-size:18pt;margin:0 0 10pt;}
.rpt-title .date{font-size:12pt;}
.rpt-kwbox{border:1px solid #000;padding:8pt 11pt;margin-bottom:4pt;}
.rpt-kw{font-size:10pt;margin:2pt 0;}
.rpt-src{font-size:8.5pt;color:#333;text-align:right;margin:0 0 12pt;}
.rpt-dept{font-weight:bold;font-size:13pt;margin:14pt 0 6pt;border-left:6px solid #1F3864;padding-left:7pt;}
.rpt-cnt{font-weight:normal;font-size:8pt;color:#888;}
.rpt-o{font-weight:bold;font-size:10.5pt;margin:8pt 0 2pt;}
.rpt-o .meta{font-weight:normal;font-size:8.5pt;color:#888;}
.rpt-dash{font-size:9.5pt;margin:2pt 0 2pt 14pt;}
.rpt-bul{font-size:9.5pt;margin:2pt 0 2pt 28pt;}
.rpt-dot{font-size:9.5pt;font-weight:bold;margin:3pt 0 6pt 14pt;background:#f0f4fa;padding:3pt 7pt;}
.rpt-cat{font-size:7.5pt;color:#4338CA;}
.rpt-tbl{border-collapse:collapse;margin:4pt 0 6pt 14pt;width:92%;}
.rpt-tbl th{border:1px solid #333;background:#dfe6f2;font-weight:bold;font-size:9pt;padding:3pt 6pt;text-align:center;}
.rpt-tbl td{border:1px solid #333;font-size:9pt;padding:3pt 6pt;vertical-align:top;}
.rpt-tbl td.c0{font-weight:bold;text-align:center;background:#f5f7fb;width:22%;}
.rpt-tbl td .ci{display:block;}
.rpt-others{border-collapse:collapse;width:100%;}
.rpt-others td{border:1px solid #333;padding:3pt 6pt;font-size:9pt;vertical-align:top;}
.rpt-others .dept{font-weight:bold;background:#f5f5f5;white-space:nowrap;}
a{color:#000;text-decoration:none;}
"""

E = lambda s: html.escape(str(s or ""))


def short_d(s):
    if not s or "-" not in s:
        return s or ""
    y, m, d = s.split("-")
    return f"{y[2:]}.{int(m)}.{int(d)}."


def cut(s, n):
    s = s or ""
    return s[:n - 1] + "…" if len(s) > n else s


def cats(cs, catmap):
    return "".join(f'<span class="rpt-cat">{E(catmap.get(c, c))}</span>' for c in (cs or []))


def render_table(t):
    if not t or not t.get("rows"):
        return ""
    cols = t.get("cols") or ["분야", "주요내용"]
    head = "".join(f"<th>{E(c)}</th>" for c in cols)
    body = ""
    for row in t["rows"]:
        field = row.get("field") if isinstance(row, dict) else (row[0] if row else "")
        content = row.get("content") if isinstance(row, dict) else (row[1] if len(row) > 1 else [])
        if not isinstance(content, list):
            content = [content]
        cells = "".join(f'<span class="ci">• {E(c)}</span>' for c in content)
        body += f'<tr><td class="c0">{E(field)}</td><td>{cells}</td></tr>'
    return f'<table class="rpt-tbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def rich_item(base, rep):
    h = (f'<p class="rpt-o">○ {E(base["title"])} '
         f'<span class="meta">({short_d(base["date"])})</span> '
         f'<a href="{E(base["link"])}">[원문]</a>{cats(base.get("categories"), rich_item.catmap)}</p>')
    if rep.get("lead"):
        h += f'<p class="rpt-dash">- {E(rep["lead"])}</p>'
    for p in rep.get("points", []):
        if isinstance(p, str):
            h += f'<p class="rpt-dash">- {E(p)}</p>'
        elif "table" in p:
            h += render_table(p["table"])
        elif p.get("h") or p.get("header"):
            h += f'<p class="rpt-dash">- {E(p.get("h") or p.get("header"))}</p>'
            for s in (p.get("items") or p.get("sub") or []):
                h += f'<p class="rpt-bul">• {E(s)}</p>'
    if rep.get("insight"):
        h += f'<p class="rpt-dot">· {E(rep["insight"])}</p>'
    return h
rich_item.catmap = {}


def simple_item(i):
    h = (f'<p class="rpt-o">○ {E(i["title"])} <span class="meta">({short_d(i["date"])})</span> '
         f'<a href="{E(i["link"])}">[원문]</a>{cats(i.get("categories"), rich_item.catmap)}</p>')
    for b in i.get("bullets", []):
        h += f'<p class="rpt-dash">- {E(b)}</p>'
    return h


def render(report, ai=None, catmap=None):
    rich_item.catmap = catmap or {}
    ai = ai or report.get("ai")

    if ai and ai.get("keywords"):
        kw = "".join(f'<p class="rpt-kw">○ <b>{E(d)}</b> : {E(", ".join(k) if isinstance(k, list) else k)}</p>'
                     for d, k in ai["keywords"].items())
    else:
        kw = "".join(f'<p class="rpt-kw">○ <b>{E(g["dept"])}</b> : '
                     + " / ".join(E(cut(i["title"], 34)) for i in g["items"][:3]) + "</p>"
                     for g in report["groups"])

    secs = ""
    for g in report["groups"]:
        secs += f'<div class="rpt-dept">{E(g["dept"])} <span class="rpt-cnt">({len(g["items"])}건)</span></div>'
        reports = (ai or {}).get("reports", {}).get(g["dept"]) if ai else None
        if reports:
            used = set()
            for rep in reports:
                idx = rep.get("idx")
                base = g["items"][idx] if isinstance(idx, int) and 0 <= idx < len(g["items"]) else None
                if base is None:
                    base = next((x for x in g["items"] if x["title"] == rep.get("title")), None)
                if base is None:
                    continue
                used.add(base["title"])
                secs += rich_item(base, rep)
            rest = [i for i in g["items"] if i["title"] not in used]
            if rest:
                secs += ("<div style='font-size:8.5pt;color:#777;margin:3pt 0 3pt 14pt'>그 외 "
                         + f"{len(rest)}건</div>")
        else:
            for i in g["items"][:6]:
                secs += simple_item(i)

    others = ""
    if report.get("others"):
        rows = ""
        for g in report["others"]:
            links = "<br>".join(
                f'<a href="{E(i["link"])}">{E(i["title"])}</a> '
                f'<span style="color:#999">({short_d(i["date"])})</span>'
                for i in g["items"][:4])
            extra = f' <span style="color:#999">외 {len(g["items"]) - 4}건</span>' if len(g["items"]) > 4 else ""
            rows += (f'<tr><td class="dept">{E(g["dept"])} ({len(g["items"])})</td>'
                     f'<td>{links}{extra}</td></tr>')
        others = ('<div class="rpt-dept">기타 부처</div>'
                  f'<table class="rpt-others"><tbody>{rows}</tbody></table>')

    src = (f'(출처 : 대한민국 정책브리핑 · KDI 경제정보센터 수집자료 {report["total"]}건, '
           f'{E(report["start"])}~{E(report["end"])}' + (" / AI 요약 적용" if ai else "") + ")")

    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<p class="rpt-head">2026 포항테크노파크 미래전략팀</p>
<h2 class="rpt-title">{E(report["weekLabel"])} 정부정책 발표 주요 내용 <span class="date">({E(report["period"])})</span></h2>
<div class="rpt-kwbox">{kw}</div>
<p class="rpt-src">{src}</p>
{secs}{others}
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("weekly")
    ap.add_argument("out")
    ap.add_argument("--ai")
    ap.add_argument("--categories", default=str(Path(__file__).parent.parent / "docs" / "data" / "categories.json"))
    args = ap.parse_args()

    report = json.loads(Path(args.weekly).read_text(encoding="utf-8"))
    ai = json.loads(Path(args.ai).read_text(encoding="utf-8")) if args.ai else None
    catmap = {}
    try:
        cj = json.loads(Path(args.categories).read_text(encoding="utf-8"))
        for c in (cj.get("categories") or cj):
            catmap[c["id"]] = c["label"]
    except Exception:
        pass

    Path(args.out).write_text(render(report, ai, catmap), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
