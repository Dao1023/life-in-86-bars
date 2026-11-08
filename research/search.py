import urllib.request, urllib.parse, re, sys, json, time

UA = {'User-Agent': 'Mozilla/5.0',
      'Accept-Language': 'zh-CN,zh;q=0.9',
      'Accept': 'text/html,application/xhtml+xml'}


def fetch(u, timeout=25, headers=None):
    h = dict(UA)
    if headers:
        h.update(headers)
    r = urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=timeout)
    return r.read()


def clean(s):
    s = re.sub(r'<script.*?</script>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<style.*?</style>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&amp;', '&', s)
    s = re.sub(r'&quot;', '"', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def so360(q, n=10):
    u = 'https://www.so.com/s?q=' + urllib.parse.quote(q)
    b = fetch(u)
    t = b.decode('utf-8', errors='replace')
    out = []
    for m in re.finditer(r'<h3[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        url, title = m.group(1), clean(m.group(2))
        tail = t[m.end():m.end() + 1200]
        desc = clean(re.search(r'<p[^>]*>(.*?)</p>', tail, re.S).group(1)) if re.search(r'<p[^>]*>(.*?)</p>', tail, re.S) else ''
        out.append({'title': title, 'url': url, 'desc': desc[:300]})
        if len(out) >= n:
            break
    return out


def sogou(q, n=10):
    u = 'https://www.sogou.com/web?query=' + urllib.parse.quote(q)
    b = fetch(u)
    t = b.decode('utf-8', errors='replace')
    out = []
    for m in re.finditer(r'<h3[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        out.append({'title': clean(m.group(2)), 'url': m.group(1), 'desc': ''})
        if len(out) >= n:
            break
    return out


def bing(q, n=10):
    u = 'https://cn.bing.com/search?q=' + urllib.parse.quote(q) + '&mkt=zh-CN&setlang=zh-Hans'
    b = fetch(u)
    t = b.decode('utf-8', errors='replace')
    out = []
    for m in re.finditer(r'<li class="b_algo".*?</li>', t, re.S):
        blk = m.group(0)
        a = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not a:
            continue
        p = re.search(r'<p[^>]*>(.*?)</p>', blk, re.S)
        out.append({'title': clean(a.group(2)), 'url': a.group(1),
                    'desc': clean(p.group(1))[:300] if p else ''})
        if len(out) >= n:
            break
    return out


def show(name, res):
    print('\n#### %s (%d)' % (name, len(res)))
    for r in res:
        print('- %s\n  %s\n  %s' % (r['title'][:120], r['url'][:180], r['desc'][:240]))


if __name__ == '__main__':
    q = ' '.join(sys.argv[1:])
    for fn in (so360, sogou, bing):
        try:
            show(fn.__name__, fn(q))
        except Exception as e:
            print('##', fn.__name__, 'ERR', str(e)[:100])


def so360_real(q, n=10):
    """so.com 搜索，从内嵌 JSON 里取真实 URL（绕过 link?m= 混淆）。"""
    import urllib.parse, re, json as _j
    u = 'https://www.so.com/s?q=' + urllib.parse.quote(q)
    b = fetch(u).decode('utf-8', errors='replace')
    out, seen = [], set()
    for m in re.finditer(r'\{[^{}]*?"url":"(https?:[^"]+)"[^{}]*?\}', b):
        blk = m.group(0)
        url = _j.loads('"' + m.group(1) + '"')
        tt = re.search(r'"title":"(.*?)","url"', blk)
        title = ''
        if tt:
            try:
                title = _j.loads('"' + tt.group(1) + '"')
            except Exception:
                title = tt.group(1)
        if url in seen or 'so.com' in url or '360' in url.split('/')[2]:
            continue
        seen.add(url)
        out.append({'title': clean(re.sub(r'<[^>]+>', '', title)), 'url': url, 'desc': ''})
        if len(out) >= n:
            break
    return out
