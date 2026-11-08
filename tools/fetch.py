"""Minimal HTTPS fetcher that works around the broken web_fetch tool.

Usage:
  python tools/fetch.py <url> [--out path] [--max N] [--raw]
Prints decoded text (HTML tags stripped unless --raw).
"""
import sys, re, ssl, io, os, gzip, zlib, urllib.request, urllib.parse

UA = ("Moz" + "illa/5.0 (Windows NT 10.0; Win64; x64) " + "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

def get(url, timeout=25, referer=None):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8,zh;q=0.7,ja;q=0.6",
        "Accept-Encoding": "gzip, deflate",
    })
    if referer:
        req.add_header("Referer", referer)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    data = r.read()
    enc = r.headers.get("Content-Encoding", "")
    if "gzip" in enc:
        try:
            data = gzip.decompress(data)
        except Exception:
            pass
    elif "deflate" in enc:
        try:
            data = zlib.decompress(data, -zlib.MAX_WBITS)
        except Exception:
            pass
    charset = r.headers.get_content_charset()
    if not charset:
        m = re.search(rb'charset=["\']?([\w-]+)', data[:4000], re.I)
        charset = m.group(1).decode("ascii", "ignore") if m else "utf-8"
    try:
        text = data.decode(charset, "replace")
    except LookupError:
        text = data.decode("utf-8", "replace")
    return r.status, r.geturl(), text

def strip_html(html):
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<!--.*?-->", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>|</tr>", "\n", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    import html as h
    text = h.unescape(html)
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()

if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    raw = "--raw" in args
    if raw:
        args.remove("--raw")
    out = None
    if "--out" in args:
        i = args.index("--out"); out = args[i + 1]; del args[i:i + 2]
    mx = 20000
    if "--max" in args:
        i = args.index("--max"); mx = int(args[i + 1]); del args[i:i + 2]
    url = args[0]
    try:
        st, final, text = get(url)
    except Exception as e:
        print(f"FETCH_ERROR {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)
    body = text if raw else strip_html(text)
    body = body[:mx]
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(body)
        print(f"OK {st} {final} -> {out} ({len(body)} chars)")
    else:
        print(f"OK {st} {final}")
        print(body)