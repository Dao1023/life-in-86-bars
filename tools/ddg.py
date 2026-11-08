"""DuckDuckGo HTML search. Usage: python tools/ddg.py "query" [--n 10] [--json out.json]"""
import sys, re, json, os, time, urllib.parse, html
import urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
      'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      'Accept': 'text/html,application/xhtml+xml'}


def _get(u, timeout=30):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=timeout).read().decode('utf-8', 'ignore')


def _real(href):
    m = re.search(r'uddg=([^&]+)', href)
    if m:
        return urllib.parse.unquote(m.group(1))
    if href.startswith('//'):
        return 'https:' + href
    return href


def clean(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(s)
    return re.sub(r'\s+', ' ', s).strip()


def ddg(q, n=10):
    d = _get('https://html.duckduckgo.com/html/?q=' + urllib.parse.quote_plus(q))
    blocks = re.findall(r'<div class="result results_links.*?</div>\s*</div>', d, re.S)
    if not blocks:
        blocks = re.split(r'<div class="result results_links', d)[1:]
    out = []
    for blk in blocks:
        a = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not a:
            continue
        sn = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', blk, re.S)
        out.append({'title': clean(a.group(2)), 'url': _real(html.unescape(a.group(1))),
                    'snippet': clean(sn.group(1))[:300] if sn else ''})
        if len(out) >= n:
            break
    return out


if __name__ == '__main__':
    args = sys.argv[1:]
    n = 10
    if '--n' in args:
        i = args.index('--n'); n = int(args[i + 1]); del args[i:i + 2]
    outj = None
    if '--json' in args:
        i = args.index('--json'); outj = args[i + 1]; del args[i:i + 2]
    q = ' '.join(args)
    try:
        res = ddg(q, n)
    except Exception as e:
        print('ERR', type(e).__name__, str(e)[:150]); res = []
    print(f'### {q} -> {len(res)}')
    for r in res:
        print('-', r['title'][:110])
        print('  ', r['url'][:200])
        print('  ', r['snippet'][:220])
    if outj:
        os.makedirs(os.path.dirname(outj) or '.', exist_ok=True)
        json.dump({'query': q, 'results': res}, open(outj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
