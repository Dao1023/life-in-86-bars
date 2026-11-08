import sys, re, urllib.request, urllib.parse, gzip, io
from search import fetch, clean

def text_of(url, limit=20000):
    b = fetch(url, timeout=30)
    if b[:2] == b'\x1f\x8b':
        b = gzip.decompress(b)
    enc = 'utf-8'
    m = re.search(rb'charset=["\']?([\w-]+)', b[:3000], re.I)
    if m:
        enc = m.group(1).decode('ascii', 'ignore')
    try:
        t = b.decode(enc, errors='replace')
    except LookupError:
        t = b.decode('utf-8', errors='replace')
    # keep table structure hints
    t = re.sub(r'</t[dh]>', ' | ', t, flags=re.I)
    t = re.sub(r'</tr>', '\n', t, flags=re.I)
    t = re.sub(r'<br\s*/?>', '\n', t, flags=re.I)
    t = re.sub(r'</p>', '\n', t, flags=re.I)
    t = re.sub(r'<script.*?</script>', ' ', t, flags=re.S | re.I)
    t = re.sub(r'<style.*?</style>', ' ', t, flags=re.S | re.I)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = t.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
    lines = [re.sub(r'[ \t\u3000]+', ' ', ln).strip() for ln in t.split('\n')]
    lines = [ln for ln in lines if ln]
    return '\n'.join(lines)[:limit]

if __name__ == '__main__':
    u = sys.argv[1]
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
    try:
        print(text_of(u, lim))
    except Exception as e:
        print('ERR', e)
