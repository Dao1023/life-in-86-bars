"""抓页面纯文本并高亮关键词上下文。用法: python grab.py URL kw1 kw2 ..."""
import sys
import re
import urllib.request
from search import UA, clean


def text_of(u, limit=None):
    h = dict(UA)
    h['Accept-Encoding'] = 'identity'
    raw = urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=30).read()
    for enc in ('utf-8', 'gb18030'):
        try:
            t = raw.decode(enc)
            break
        except Exception:
            t = raw.decode('utf-8', 'replace')
    t = re.sub(r'<(script|style).*?</\1>', ' ', t, flags=re.S | re.I)
    t = re.sub(r'</t[dh]>', ' | ', t)
    t = re.sub(r'</tr>', '\n', t)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'&nbsp;', ' ', t)
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n\s*\n+', '\n', t)
    return t.strip()


if __name__ == '__main__':
    u = sys.argv[1]
    kws = sys.argv[2:]
    t = text_of(u)
    print('#LEN', len(t))
    if not kws:
        print(t[:3000])
    for kw in kws:
        for m in re.finditer(re.escape(kw), t):
            a = max(0, m.start() - 160)
            print('---', kw, '---')
            print(t[a:m.start() + 260].replace('\n', ' '))
