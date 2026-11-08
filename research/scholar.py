import sys, re, urllib.parse
from search import fetch, clean


def scholar(q, n=10, start=0):
    u = 'https://scholar.google.com/scholar?q=' + urllib.parse.quote(q) + '&hl=zh-CN&start=%d' % start
    t = fetch(u, timeout=30).decode('utf-8', 'replace')
    out = []
    for m in re.finditer(r'<div class="gs_r gs_or gs_scl".*?</div>\s*</div>', t, re.S):
        blk = m.group(0)
        h = re.search(r'<h3 class="gs_rt".*?</h3>', blk, re.S)
        title = clean(h.group(0)) if h else ''
        a = re.search(r'<div class="gs_a">(.*?)</div>', blk, re.S)
        meta = clean(a.group(1)) if a else ''
        s = re.search(r'<div class="gs_rs">(.*?)</div>', blk, re.S)
        snip = clean(s.group(1)) if s else ''
        pdf = re.search(r'href="([^"]+\.pdf[^"]*)"', blk)
        out.append({'title': title, 'meta': meta, 'snippet': snip, 'pdf': pdf.group(1) if pdf else ''})
        if len(out) >= n:
            break
    return out


if __name__ == '__main__':
    q = ' '.join(sys.argv[1:])
    for r in scholar(q):
        print('- %s\n  %s\n  %s\n  PDF:%s' % (r['title'][:160], r['meta'][:120], r['snippet'][:260], r['pdf'][:120]))
