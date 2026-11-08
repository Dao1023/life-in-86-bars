"""so.com 搜索，取真实 URL（绕开 link?m= 混淆）。"""
import re
import json
import urllib.parse
from search import fetch, clean


def sreal(q, n=10):
    u = 'https://www.so.com/s?q=' + urllib.parse.quote(q)
    b = fetch(u).decode('utf-8', 'replace')
    out = []
    seen = set()
    for m in re.finditer(r'"url":"(https?:[^"]*)"', b):
        raw = m.group(1)
        url = json.loads('"' + raw + '"')
        head = b[max(0, m.start() - 400):m.start()]
        t = re.findall(r'"title":"((?:[^"\\]|\\.)*)"', head)
        title = ''
        if t:
            try:
                title = json.loads('"' + t[-1] + '"')
            except Exception:
                title = t[-1]
        if url in seen:
            continue
        host = url.split('/')[2] if url.count('/') >= 2 else ''
        if 'so.com' in host or '360' in host:
            continue
        seen.add(url)
        out.append({'title': clean(title), 'url': url})
        if len(out) >= n:
            break
    return out


if __name__ == '__main__':
    import sys
    for r in sreal(' '.join(sys.argv[1:])):
        print(r['title'][:70], '|', r['url'][:110])
