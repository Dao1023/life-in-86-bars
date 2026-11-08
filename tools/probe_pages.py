# -*- coding: utf-8 -*-
"""Probe real project pages and extract structural signals for landing-page research.

Output: notes/probe/<slug>.json  +  a compact digest on stdout.
"""
import html as htmllib
import io
import json
import os
import re
import sys
import time

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

URLS = [
    # The Pudding (confirmed live from index)
    "https://pudding.cool/2025/04/birthday-effect/",
    "https://pudding.cool/2018/08/pockets/",
    "https://pudding.cool/2017/03/hamilton/",
    "https://pudding.cool/2026/02/happy-map/",
    "https://pudding.cool/2026/05/similes/",
    "https://pudding.cool/2025/10/walk/",
    # Reuters / NYT / FT / SCMP
    "https://www.reuters.com/graphics/",
    "https://ig.ft.com/",
    "https://multimedia.scmp.com/infographics/",
    "https://www.nytimes.com/section/upshot",
    # Distill
    "https://distill.pub/2016/misread-tsne/",
    "https://distill.pub/2019/visual-exploration-gaussian-processes/",
    "https://distill.pub/2020/circuits/zoom-in/",
    # Independent viz people
    "https://www.visualcinnamon.com/",
    "https://wattenberger.com/",
    "https://shirleywu.studio/",
    "https://bost.ocks.org/mike/",
    "https://observablehq.com/@d3/gallery",
    # Open data / OSS landing pages
    "https://ourworldindata.org/co2-emissions",
    "https://ourworldindata.org/life-expectancy",
    "https://blog.datawrapper.de/",
    # Viral interactive / HN-class
    "https://ncase.me/polygons/",
    "https://neal.fun/spend/",
    "https://neal.fun/size-of-space/",
    "https://www.washingtonpost.com/graphics/2020/world/corona-simulator/",
    # Chinese-language data viz
    "https://datanews.caixin.com/",
    "https://www.thepaper.cn/list_25635",
    "https://www.sixthtone.com/",
]


def clean_html(raw: str):
    head_end = raw.find("</head>")
    head = raw[:head_end] if head_end > 0 else raw
    body = raw[head_end:] if head_end > 0 else raw
    body = re.sub(r"<script\b.*?</script>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<style\b.*?</style>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<noscript\b.*?</noscript>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    body = re.sub(r"<br\s*/?>|</p>|</h\d>|</li>|</div>", "\n", body, flags=re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    body = htmllib.unescape(body)
    body = re.sub(r"[ \t\u00a0]+", " ", body)
    body = re.sub(r"\n\s*\n+", "\n", body)
    return head, body.strip()


def meta_map(head: str):
    out = {}
    for m in re.finditer(r"<meta\b[^>]*>", head, flags=re.I):
        tag = m.group(0)
        k = re.search(r'(?:property|name)\s*=\s*["\']([^"\']+)["\']', tag, flags=re.I)
        v = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag, flags=re.I)
        if k and v:
            out.setdefault(k.group(1).lower(), v.group(1))
    return out


def jsonld_dates(head: str):
    dates = []
    for m in re.finditer(r'"date(?:Published|Modified)"\s*:\s*"([^"]+)"', head):
        dates.append(m.group(1))
    return sorted(set(dates))[:4]


def texts(html_text: str, tag: str):
    return [re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", "", x))).strip()
            for x in re.findall(r"<%s\b[^>]*>(.*?)</%s>" % (tag, tag), html_text, flags=re.S | re.I)]


KEYWORDS = {
    "method": [r"methodolog", r"how we (?:did|made|built)", r"our (?:method|approach)", r"方法论", r"我们如何", r"做法"],
    "source": [r"data source", r"\bsources?\b", r"data from", r"数据来源", r"来源", r"基于"],
    "caveat": [r"caveat", r"limitation", r"not (?:official|observed)", r"known issue", r"局限", r"不足", r"误差", r"估算", r"模型"],
    "credit": [r"credits?\b", r"\bby [A-Z]", r"作者", r"设计[:：]", r"contact"],
}


def analyse(url: str):
    rec = {"url": url}
    t0 = time.time()
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en,zh-CN;q=0.8"},
                         timeout=30, allow_redirects=True)
    except Exception as e:
        rec["error"] = "%s: %s" % (type(e).__name__, e)
        return rec
    rec.update(final_url=r.url, status=r.status_code, bytes=len(r.content),
               elapsed=round(time.time() - t0, 1), encoding=r.encoding)
    if r.status_code >= 400 or not r.content:
        rec["error"] = "http %s" % r.status_code
        return rec
    raw = r.content.decode(r.apparent_encoding or "utf-8", "replace")
    head, body = clean_html(raw)
    rec["meta"] = {k: v[:300] for k, v in meta_map(head).items()}
    rec["dates"] = jsonld_dates(head)
    rec["h1"] = [t for t in texts(raw, "h1") if t][:4]
    rec["h2_count"] = len([t for t in texts(raw, "h2") if t])
    rec["h2"] = [t for t in texts(raw, "h2") if t][:12]
    rec["text_chars"] = len(body)
    rec["text_words"] = len(re.findall(r"[A-Za-z']+", body)) + len(re.findall(r"[\u4e00-\u9fff]", body)) // 2
    rec["lead"] = body[:700]

    styles = " ".join(re.findall(r"<style\b[^>]*>(.*?)</style>", raw, flags=re.S | re.I))
    fonts = re.findall(r"font-family\s*:\s*([^;\"'}]+)", styles, flags=re.I)
    seen, fontlist = set(), []
    for f in fonts:
        f = re.sub(r"\s+", " ", f).strip()[:80]
        if f.lower() not in seen:
            seen.add(f.lower())
            fontlist.append(f)
    rec["fonts"] = fontlist[:8]
    rec["font_face"] = len(re.findall(r"@font-face", styles, flags=re.I))
    rec["sticky"] = len(re.findall(r"position\s*:\s*sticky", styles, flags=re.I))
    rec["fixed"] = len(re.findall(r"position\s*:\s*fixed", styles, flags=re.I))
    rec["sheets"] = len(re.findall(r'<link[^>]+rel=["\']stylesheet', raw, flags=re.I))

    srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', raw, flags=re.I)
    rec["script_count"] = len(re.findall(r"<script\b", raw, flags=re.I))
    rec["script_hosts"] = sorted({re.sub(r"^(https?:)?//([^/]+).*", r"\2", s) if s.startswith(("http", "//")) else "inline/rel" for s in srcs})[:10]
    blob = raw.lower()
    libs = {
        "d3": r"d3(?:\.v\d)?(?:\.min)?\.js|/d3@|d3-selection",
        "gsap": r"gsap",
        "scrollama": r"scrollama",
        "intersectionObserver": r"intersectionobserver",
        "svelte": r"svelte",
        "react": r"react(?:-dom)?[.\-/]",
        "vue": r"vue(?:\.min)?\.js",
        "next": r"_next/",
        "three": r"three(?:\.min)?\.js",
        "p5": r"p5(?:\.min)?\.js",
        "mapbox": r"mapbox",
        "leaflet": r"leaflet",
        "chartjs": r"chart(?:\.min)?\.js",
        "scrollTrigger": r"scrolltrigger",
        "chartable": r"charted|chartability",
    }
    rec["libs"] = [k for k, p in libs.items() if re.search(p, blob)]
    rec["viewport"] = bool(re.search(r'name=["\']viewport', head, flags=re.I))

    # keyword placement as ratio of body text position
    low = body.lower()
    cred = {}
    for k, pats in KEYWORDS.items():
        hits = []
        for p in pats:
            for m in re.finditer(p, low):
                hits.append(round(m.start() / max(1, len(low)), 2))
        hits = sorted(hits)
        cred[k] = {"n": len(hits), "first_at": hits[0] if hits else None}
    rec["cred"] = cred
    rec["has_author_by"] = bool(re.search(r"\bby [A-Z][a-z]+ [A-Z][a-z]+", body))
    return rec


def main():
    outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notes", "probe")
    os.makedirs(outdir, exist_ok=True)
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    results = []
    for u in URLS:
        if only and not any(o in u for o in only):
            continue
        rec = analyse(u)
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", u.replace("https://", ""))[:70].strip("-")
        with open(os.path.join(outdir, slug + ".json"), "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        results.append(rec)
        m = rec.get("meta", {})
        print("\n=== %s  [%s] %sB" % (u, rec.get("status"), rec.get("bytes")))
        if rec.get("error"):
            print("  ERROR", rec["error"]); continue
        print("  og:title  :", (m.get("og:title") or "")[:110])
        print("  og:desc   :", (m.get("og:description") or "")[:130])
        print("  og:image  :", (m.get("og:image") or "")[:110])
        print("  twitter   :", (m.get("twitter:card") or "-"), "|", (m.get("twitter:creator") or "-"))
        print("  dates     :", rec["dates"], "| viewport", rec["viewport"])
        print("  h1        :", rec["h1"])
        print("  text      : %d chars / ~%d words | h2 %d" % (rec["text_chars"], rec["text_words"], rec["h2_count"]))
        print("  fonts     :", rec["fonts"][:5], "| @font-face", rec["font_face"])
        print("  layout    : sticky", rec["sticky"], "fixed", rec["fixed"], "| sheets", rec["sheets"], "| scripts", rec["script_count"], rec["script_hosts"])
        print("  libs      :", rec["libs"])
        print("  cred      :", rec["cred"])
        print("  lead      :", rec["lead"][:260].replace("\n", " "))
    print("\n\nTOTAL", len(results))


if __name__ == "__main__":
    main()
