"""抓取上海统计年鉴表的工具：python tools/shfetch.py C0217 [C0218 ...]
表页结构：C02xx.htm 是 frameset -> C02/C02xxB.htm 是 Excel 导出的 HTML 表。
"""
import sys, os, re
import requests
from bs4 import BeautifulSoup

BASE = "https://tjj.sh.gov.cn/tjnj/2025tjnj"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
OUT = os.path.join(os.path.dirname(__file__), "..", "raw", "tjnj2025")
os.makedirs(OUT, exist_ok=True)


def get(url):
    r = requests.get(url, headers=H, timeout=30)
    r.raise_for_status()
    raw = r.content
    # 年鉴页多为 gb2312/gb18030，先试 utf-8 再退 gb18030
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("gb18030", "replace")


def table_text(html):
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True).replace("\xa0", " ")
                 for c in tr.find_all(["td", "th"])]
        # 去掉尾部全空
        while cells and not cells[-1]:
            cells.pop()
        if cells:
            rows.append(cells)
    return rows


def dump(code):
    url = f"{BASE}/{code}.htm"
    page = get(url)
    m = re.search(r'src="([^"]*?%sB?\.htm)"' % code, page)
    if not m:
        m = re.search(r'src="([^"]+\.htm)"', page)
    path = m.group(1) if m else None
    if not path:
        print(f"[{code}] 非 frameset，直接解析")
        html, real = page, url
    else:
        real = f"{BASE}/{path}"
        html = get(real)
    rows = table_text(html)
    fn = os.path.join(OUT, f"{code}.txt")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(f"# {real}\n")
        for r in rows:
            f.write(" | ".join(r) + "\n")
    print(f"===== {code}  {real}  rows={len(rows)} -> {fn}")
    for r in rows[:6]:
        print("   ", " | ".join(r)[:200])
    return fn


if __name__ == "__main__":
    for c in sys.argv[1:]:
        try:
            dump(c)
        except Exception as e:
            print(f"[{c}] ERR {type(e).__name__}: {e}")
