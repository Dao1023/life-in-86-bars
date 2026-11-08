"""Search: Baidu + 360 + Bing, tolerant HTML parsing (h3 anchors)."""
import sys, re, html, os, urllib.parse, importlib.util

_here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("f", os.path.join(_here, "fetch.py"))
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)

B64 = re.compile(r"u=a1([A-Za-z0-9_\-=]+)")

def _abs(u):
    if u.startswith("//"):
        return "https:" + u
    return u

def extract(h, link_re=r"(/link\?url=|^https?://)"):
    res, seen = [], set()
    for m in re.finditer(r"<h3[^>]*>(.*?)</h3>", h, re.S):
        blk = m.group(1)
        a = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not a:
            continue
        url, title = _abs(html.unescape(a.group(1))), f.strip_html(a.group(2))
        if not title or len(title) < 4:
            continue
        # snippet: text right after the h3 block
        tail = h[m.end():m.end() + 2500]
        tail = re.sub(r"(?s)<h3.*", "", tail)
        snip = f.strip_html(tail)
        snip = re.sub(r"\s+", " ", snip)[:280]
        key = title[:40]
        if key in seen:
            continue
        seen.add(key)
        res.append((title, url, snip))
    return res

def baidu(q, n=12):
    u = "https://www.baidu.com/s?" + urllib.parse.urlencode({"wd": q, "rn": n, "ie": "utf-8"})
    st, _, h = f.get(u)
    out = extract(h)
    return out

def so360(q, n=12):
    u = "https://www.so.com/s?" + urllib.parse.urlencode({"q": q, "pn": 1})
    st, _, h = f.get(u)
    return extract(h)

def bing(q, n=12):
    u = "https://www.bing.com/search?" + urllib.parse.urlencode(
        {"q": q, "count": n, "setlang": "en", "cc": "US", "ensearch": "1"})
    st, _, h = f.get(u)
    out = []
    for m in re.finditer(r'<li class="b_algo".*?</li>', h, re.S):
        blk = m.group(0)
        t = re.search(r"<h2[^>]*>(.*?)</h2>", blk, re.S)
        a = re.search(r'<a[^>]+href="([^"]+)"', blk)
        sn = re.search(r'<p[^>]*>(.*?)</p>', blk, re.S)
        if not (t and a):
            continue
        url = html.unescape(a.group(1))
        mm = B64.search(url)
        if mm:
            try:
                pad = mm.group(1) + "=" * (-len(mm.group(1)) % 4)
                import base64
                url = base64.urlsafe_b64decode(pad).decode("utf-8", "replace")
            except Exception:
                pass
        out.append((f.strip_html(t.group(1)), url, f.strip_html(sn.group(1))[:280] if sn else ""))
    return out

if __name__ == "__main__":
    engine = "baidu"
    for flag in ("--baidu", "--360", "--bing"):
        if flag in sys.argv:
            engine = flag[2:]
    q = " ".join(a for a in sys.argv[1:] if not a.startswith("--"))
    fn = {"baidu": baidu, "360": so360, "bing": bing}[engine]
    try:
        res = fn(q)
    except Exception as e:
        print("ERR", e); sys.exit(1)
    print(f"[{engine}] {len(res)} hits: {q}")
    for i, (t, u, s) in enumerate(res, 1):
        print(f"\n{i}. {t}\n   {u}\n   {s}")
