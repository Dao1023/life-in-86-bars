import sys
import re
import json
import urllib.parse
from search import fetch

q = ' '.join(sys.argv[1:])
url = 'https://www.so.com/s?q=' + urllib.parse.quote(q)
b = fetch(url).decode('utf-8', 'replace')
open('notes/last_serp.html', 'w', encoding='utf-8').write(b)

print('len', len(b))
for pat in ['"url":"', '"url": "', 'data-mdurl=', 'link?m=', 'data-url']:
    print(repr(pat), b.count(pat))

found = []
for pat in [r'"url":"(https?:[^"]*)"', r'"url": "(https?:[^"]*)"']:
    for m in re.finditer(pat, b):
        try:
            found.append(json.loads('"' + m.group(1) + '"'))
        except Exception:
            found.append(m.group(1))
for pat in [r'data-mdurl="([^"]+)"', r'data-mdurl=\'([^\']+)\'']:
    found += re.findall(pat, b)
seen = set()
for f in found:
    h = f.split('/')[2] if f.count('/') >= 2 else ''
    if f in seen or 'so.com' in h or '360' in h:
        continue
    seen.add(f)
    print('URL', f[:130])
