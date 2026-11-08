"""Read a URL via r.jina.ai and print only lines matching keywords.

Usage: python tools/grab.py <url> --grep "kw1,kw2" [--lines 20] [--save name] [--chars 400]
"""
import sys, os, re, importlib.util

_here = os.path.dirname(os.path.abspath(__file__))
def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_here, fn))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
j = _load("j", "jina.py")

if __name__ == "__main__":
    args = sys.argv[1:]
    def opt(flag, default=None):
        if flag in args:
            i = args.index(flag); v = args[i + 1]; del args[i:i + 2]; return v
        return default
    kws = [k for k in (opt("--grep", "") or "").split(",") if k]
    n = int(opt("--lines", "20"))
    save = opt("--save")
    clen = int(opt("--chars", "400"))
    url = args[0]
    t = j.read(url)
    if save:
        os.makedirs(os.path.join(os.path.dirname(_here), "research", "_raw"), exist_ok=True)
        open(os.path.join(os.path.dirname(_here), "research", "_raw", save + ".md"), "w", encoding="utf-8").write(t)
    print(f"# {url}  ({len(t)} chars)")
    shown = 0
    for line in t.split("\n"):
        p = line.strip()
        if len(p) < 40:
            continue
        if kws and not any(k.lower() in p.lower() for k in kws):
            continue
        print("•", re.sub(r"\s+", " ", p)[:clen])
        shown += 1
        if shown >= n:
            break
    if shown == 0:
        print("(no matches) first 600 chars:\n", t[:600])
