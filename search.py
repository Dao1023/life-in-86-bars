import urllib.request, urllib.parse, re, html, sys, base64, json

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def _decode(href):
    m = re.search(r'[?&]u=a1([A-Za-z0-9_\-]+)', href)
    if not m:
        return href
    s = m.group(1).replace('-', '+').replace('_', '/')
    s += '=' * (-len(s) % 4)
    try:
        return base64.b64decode(s).decode('utf-8', 'ignore')
    except Exception:
        return href


def bing(q, n=10):
    u = 'https://www.bing.com/search?q=' + urllib.parse.quote(q)
    try:
        d = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': UA}), timeout=40).read().decode('utf-8', 'ignore')
    except Exception as e:
        print('ERR', e)
        return []
    out, seen = [], set()
    for m in re.finditer(r'<h2><a[^>]*href="([^"]+)"[^>]*>(.*?)</a></h2>', d, re.S):
        href = _decode(html.unescape(m.group(1)))
        t = html.unescape(re.sub(r'<[^>]+>', '', m.group(2))).strip()
        if href in seen:
            continue
        seen.add(href)
        out.append((t, href))
    return out[:n]


if __name__ == '__main__':
    for q in sys.argv[1:]:
        print('###', q)
        for t, u in bing(q):
            print('  -', t[:90], '|', u[:180])
