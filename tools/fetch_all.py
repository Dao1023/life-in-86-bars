"""Resolve baidu redirect links, download PDFs, extract text, score for age x category tables."""
import sys, os, json, re, warnings
import requests
warnings.filterwarnings("ignore")
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'}
OUT = 'raw/pdf/auto'
os.makedirs(OUT, exist_ok=True)


def resolve(u, maxhop=6):
    for _ in range(maxhop):
        r = requests.get(u, headers=H, timeout=35, verify=False, allow_redirects=False)
        if r.status_code in (301, 302, 303, 307, 308):
            loc = r.headers.get('Location') or r.headers.get('location')
            if not loc:
                return u
            loc = loc.encode('latin-1', 'ignore').decode('utf-8', 'ignore') if any(ord(c) > 127 for c in loc) else loc
            if loc.startswith('/'):
                from urllib.parse import urljoin
                loc = urljoin(u, loc)
            u = loc
            continue
        return u
    return u


def grab(url, name):
    try:
        final = resolve(url)
        r = requests.get(final, headers=H, timeout=60, verify=False)
        ct = r.headers.get('content-type', '')
        if 'pdf' in ct or r.content[:4] == b'%PDF':
            p = os.path.join(OUT, name + '.pdf')
            open(p, 'wb').write(r.content)
            return p, final
        p = os.path.join(OUT, name + '.html')
        open(p, 'wb').write(r.content)
        return p, final
    except Exception as e:
        return None, 'ERR ' + type(e).__name__ + ':' + str(e)[:80]


KEY = ['分年龄', '年龄段', '年龄组', '八大类', '消费结构']


def score(path):
    try:
        import fitz
    except Exception:
        return ''
    if not path or not path.endswith('.pdf'):
        return ''
    try:
        doc = fitz.open(path)
    except Exception:
        return ''
    txt = '\n'.join(p.get_text('text') for p in doc)
    open(path[:-4] + '.txt', 'w', encoding='utf-8').write(txt)
    hits = {k: txt.count(k) for k in KEY}
    ntables = len(re.findall(r'表\s?\d', txt))
    return 'pages=%d chars=%d tables=%d %s' % (doc.page_count, len(txt), ntables, hits)


if __name__ == '__main__':
    links = json.load(open('raw/baidu_pdf_links.json', encoding='utf-8'))
    items = list(links.items())[:int(sys.argv[1]) if len(sys.argv) > 1 else 30]
    for i, (h, t) in enumerate(items):
        name = 'a%02d' % i
        p, final = grab(h, name)
        s = score(p)
        print('%s | %s | %s' % (name, t[:40], final if p else 'FAIL'))
        print('     ->', p, s)
