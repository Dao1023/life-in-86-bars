"""Read any URL as markdown via r.jina.ai reader proxy.

Usage: python tools/jina.py <url> [--out file] [--max N]
Falls back to direct fetch if the proxy fails.
"""
import sys, os, time, importlib.util, urllib.parse

_here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("f", os.path.join(_here, "fetch.py"))
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)

def read(url, timeout=60, tries=2):
    last = None
    for i in range(tries):
        try:
            st, final, t = f.get("https://r.jina.ai/" + url, timeout=timeout)
            if "Markdown Content:" in t or len(t) > 800:
                return t
            last = t
        except Exception as e:
            last = f"ERR {type(e).__name__}: {e}"
        time.sleep(2)
    return str(last)

if __name__ == "__main__":
    args = sys.argv[1:]
    out = None
    if "--out" in args:
        i = args.index("--out"); out = args[i + 1]; del args[i:i + 2]
    mx = 30000
    if "--max" in args:
        i = args.index("--max"); mx = int(args[i + 1]); del args[i:i + 2]
    t = read(args[0])[:mx]
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        open(out, "w", encoding="utf-8").write(t)
        print(f"saved {len(t)} chars -> {out}")
    else:
        print(t)
