"""Baidu search via browser-use harness (renders, bypasses bot check).
Usage (in browser-use script):
    exec(open('tools/baidu.py').read())
    res = baidu('分年龄 消费结构 表', n=12)
"""
import json, time, urllib.parse

JS = r"""JSON.stringify([...document.querySelectorAll('div.result, div.result-op, div.c-container')].map(d=>{
  const a=d.querySelector('h3 a')||d.querySelector('a');
  const t=a?a.innerText.trim():'';
  const h=a?a.href:'';
  const s=(d.innerText||'').replace(/\s+/g,' ').slice(0,300);
  const src=(d.querySelector('.c-color-gray, .siteLink_9TPP3, .c-showurl')||{}).innerText||'';
  return {t,h,s,src};
}).filter(x=>x.t))"""


def baidu(q, n=12, page=0, wait=2.5):
    url = "https://www.baidu.com/s?wd=" + urllib.parse.quote(q) + ("&pn=%d" % (page * 10) if page else "")
    goto_url(url)
    wait_for_load()
    time.sleep(wait)
    raw = js(JS)
    try:
        items = json.loads(raw)
    except Exception:
        items = []
    out = []
    for it in items[:n]:
        out.append(it)
    return out


def show(q, n=12, page=0, snippet=True):
    print("\n### QUERY:", q)
    for i, it in enumerate(baidu(q, n=n, page=page)):
        print("[%d] %s" % (i, it['t'][:100]))
        print("    src:", (it.get('src') or '')[:80])
        print("    url:", it['h'][:160])
        if snippet:
            print("    txt:", it['s'][:200])
