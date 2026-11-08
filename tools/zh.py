"""Baidu search with redirect resolution. Usage: python tools/zh.py "query" [--n 8] [--resolve]"""
import sys, re, json, os, importlib.util, time

_here = os.path.dirname(os.path.abspath(__file__))
def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_here, fn))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
f = _load("f", "fetch.py")
s = _load("s", "search.py")

def resolve(u):
    if ("baidu.com/link" not in u) and ("so.com/link" not in u):
        return u
    try:
        st, final, body = f.get(u, timeout=20)
        import re as _re
        m = _re.search(r'location\.replace\("([^"]+)"\)', body or "")
        if m:
            return m.group(1)
        return final
    except Exception:
        return u

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = 8
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
    q = " ".join(a for a in args if not a.isdigit())
    res = s.baidu(q, n)
    print(f"[baidu] {q} -> {len(res)}")
    for i, (t, u, sn) in enumerate(res[:n], 1):
        real = resolve(u)
        print(f"\n{i}. {t}\n   {real}\n   {sn[:200]}")
        time.sleep(0.6)
