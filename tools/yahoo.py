"""Yahoo search (Bing index, no key). Usage: python tools/yahoo.py "query" [--n 10] [--json out.json]"""
import sys, re, os, json, time, html, urllib.parse
import requests

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'}


def clean(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()


def yahoo(q, n=10):
    r = requests.get('https://search.yahoo.com/search?p=' + urllib.parse.quote(q), headers=UA, timeout=30)
    r.encoding = 'utf-8'
    blocks = re.findall(r'<div class="dd algo.*?</div>\s*</div>', r.text, re.S)
    out, seen = [], set()
    for b in blocks:
        u = re.search(r'RU=([^/]+)/RK=', b)
        url = urllib.parse.unquote(u.group(1)) if u else ''
        t = re.search(r'<h3[^>]*>.*?<span[^>]*>(.*?)</span>', b, re.S)
        title = clean(t.group(1)) if t else ''
        sn = re.search(r'class="compText[^"]*"[^>]*>(.*?)</div>', b, re.S)
        snippet = clean(sn.group(1)) if sn else ''
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({'title': title, 'url': url, 'snippet': snippet[:300]})
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
        res = yahoo(q, n)
    except Exception as e:
        print('ERR', type(e).__name__, str(e)[:150]); res = []
    print(f'### {q} -> {len(res)}')
    for r in res:
        print('-', r['title'][:110])
        print('  ', r['url'][:220])
        print('  ', r['snippet'][:200])
    if outj:
        os.makedirs(os.path.dirname(outj) or '.', exist_ok=True)
        json.dump({'query': q, 'results': res}, open(outj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
