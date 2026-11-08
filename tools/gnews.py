"""Google News RSS multi-query collector.

Usage: python tools/gnews.py [--zh] "q1" "q2" ...
Writes results to stdout and appends JSON to research/_evidence-news.json
"""
import sys, re, json, os, urllib.parse, importlib.util, hashlib, time

_here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("f", os.path.join(_here, "fetch.py"))
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)

def items(xml):
    out = []
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.S):
        b = m.group(1)
        def g(tag):
            mm = re.search(rf"<{tag}>(.*?)</{tag}>", b, re.S)
            return mm.group(1) if mm else ""
        title = f.strip_html(g("title"))
        src = re.search(r'<source url="([^"]+)"[^>]*>(.*?)</source>', b, re.S)
        out.append({
            "title": title,
            "link": f.strip_html(g("link")),
            "date": g("pubDate")[:16],
            "publisher": f.strip_html(src.group(2)) if src else "",
            "publisher_url": src.group(1) if src else "",
        })
    return out

def search(q, zh=False, n=25):
    p = {"q": q, "hl": "zh-CN" if zh else "en-US",
         "gl": "CN" if zh else "US", "ceid": "CN:zh-Hans" if zh else "US:en"}
    st, _, x = f.get("https://news.google.com/rss/search?" + urllib.parse.urlencode(p), timeout=30)
    return items(x)

if __name__ == "__main__":
    zh = "--zh" in sys.argv
    qs = [a for a in sys.argv[1:] if not a.startswith("--")]
    store = os.path.join(os.path.dirname(_here), "research", "_evidence-news.json")
    db = json.load(open(store, encoding="utf-8")) if os.path.exists(store) else {}
    for q in qs:
        try:
            res = search(q, zh)
        except Exception as e:
            print(f"\n## {q}\nERR {e}"); continue
        print(f"\n## {q}  ({len(res)} items)")
        for r in res[:14]:
            print(f" - [{r['date'][:16]}] {r['publisher']} | {r['title'][:110]}")
        db[q] = res
        time.sleep(0.5)
    json.dump(db, open(store, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[saved {len(db)} queries -> {store}]")
