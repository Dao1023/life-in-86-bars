"""East-Asia official stats fetcher (HK / TW / KR).

TLS on this host has an interception cert chain, so we use an unverified
context; browser-like headers are required by censtatd.gov.hk / stat.gov.tw.
"""
import gzip
import io
import os
import ssl
import time
import urllib.error
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36')

HEADERS = {
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
              'application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.'
              'spreadsheetml.sheet,application/pdf,*/*;q=0.8',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7,ko;q=0.6',
    'Accept-Encoding': 'gzip, deflate',
    'sec-ch-ua': '"Chromium";v="138", "Not)A;Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'Connection': 'keep-alive',
}

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def fetch(url, out=None, timeout=90, retries=2, referer=None):
    hh = dict(HEADERS)
    if referer:
        hh['Referer'] = referer
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=hh)
            r = urllib.request.urlopen(req, timeout=timeout, context=_CTX)
            data = r.read()
            if r.headers.get('Content-Encoding') == 'gzip' or data[:2] == b'\x1f\x8b':
                try:
                    data = gzip.decompress(data)
                except Exception:
                    pass
            if out:
                d = os.path.dirname(out)
                if d:
                    os.makedirs(d, exist_ok=True)
                with open(out, 'wb') as f:
                    f.write(data)
            return r.status, data, dict(r.headers)
        except urllib.error.HTTPError as e:
            body = b''
            try:
                body = e.read()
            except Exception:
                pass
            return e.code, body, dict(e.headers or {})
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + i * 2)
    return None, str(last).encode(), {}


def get_text(url, out=None, **kw):
    s, d, h = fetch(url, out=out, **kw)
    enc = 'utf-8'
    ct = (h.get('Content-Type') or '').lower()
    if 'big5' in ct:
        enc = 'big5'
    try:
        return s, d.decode(enc, 'replace'), h
    except Exception:
        return s, d.decode('latin-1', 'replace'), h


if __name__ == '__main__':
    import sys
    for u in sys.argv[1:]:
        s, d, h = fetch(u)
        print(s, len(d), u, (h or {}).get('Content-Type'))
        print(d[:300])
