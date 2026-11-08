"""Download a PDF and dump text by page. Usage: python tools/pdf.py <url|path> [--pages 1-6] [--grep 关键词] [--tables] [--out file]"""
import sys, os, re, urllib.parse, urllib.request, json
import fitz

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'}


def fetch_pdf(src, dest):
    if os.path.exists(src):
        return src
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(src, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r, open(dest, 'wb') as f:
        f.write(r.read())
    return dest


def main():
    args = sys.argv[1:]
    src = args[0]
    pages = None
    grep = None
    show_tables = False
    out = None
    i = 1
    while i < len(args):
        if args[i] == '--pages':
            a, b = args[i + 1].split('-'); pages = (int(a), int(b)); i += 2
        elif args[i] == '--grep':
            grep = args[i + 1]; i += 2
        elif args[i] == '--tables':
            show_tables = True; i += 1
        elif args[i] == '--out':
            out = args[i + 1]; i += 2
        else:
            i += 1
    stem = re.sub(r'[^A-Za-z0-9_.-]', '_', src.split('/')[-1])[:60] or 'doc'
    dest = os.path.join('raw', 'pdf', stem if stem.lower().endswith('.pdf') else stem + '.pdf')
    path = fetch_pdf(src, dest)
    doc = fitz.open(path)
    print(f'# {path}  pages={doc.page_count}  size={os.path.getsize(path)}')
    lines = []
    rng = range(doc.page_count)
    if pages:
        rng = range(max(0, pages[0] - 1), min(doc.page_count, pages[1]))
    for pno in rng:
        page = doc[pno]
        txt = page.get_text('text')
        if show_tables:
            try:
                tabs = page.find_tables()
                for ti, t in enumerate(tabs.tables):
                    lines.append(f'--- p{pno+1} TABLE {ti+1} ---')
                    for row in t.extract():
                        lines.append(' | '.join('' if c is None else str(c).replace('\n', ' ') for c in row))
            except Exception as e:
                lines.append(f'[table err {e}]')
        if grep:
            for ln in txt.split('\n'):
                if grep in ln:
                    lines.append(f'[p{pno+1}] {ln.strip()}')
        else:
            lines.append(f'\n===== p{pno+1} =====')
            lines.append(txt)
    text = '\n'.join(lines)
    if out:
        os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
        open(out, 'w', encoding='utf-8').write(text)
        print(f'saved {len(text)} chars -> {out}')
    else:
        print(text[:20000])


if __name__ == '__main__':
    main()
