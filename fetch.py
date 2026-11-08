import urllib.request, urllib.error, gzip, io, os, sys, time

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
H = {
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'sec-ch-ua': '"Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'Connection': 'keep-alive',
}


def fetch(url, out=None, timeout=60, retries=2, headers=None):
    hh = dict(H)
    if headers:
        hh.update(headers)
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=hh)
            r = urllib.request.urlopen(req, timeout=timeout)
            data = r.read()
            if r.headers.get('Content-Encoding') == 'gzip' or data[:2] == b'\x1f\x8b':
                try:
                    data = gzip.decompress(data)
                except Exception:
                    pass
            if out:
                os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
                open(out, 'wb').write(data)
            return r.status, data, dict(r.headers)
        except urllib.error.HTTPError as e:
            body = b''
            try:
                body = e.read()
            except Exception:
                pass
            return e.code, body, dict(e.headers or {})
        except Exception as e:
            last = e
            time.sleep(2)
    return None, str(last).encode(), {}


if __name__ == '__main__':
    for u in sys.argv[1:]:
        s, d, hd = fetch(u)
        print(s, len(d), u)
        print(d[:200])
