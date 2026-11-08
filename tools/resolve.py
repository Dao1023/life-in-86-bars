import sys, requests, warnings
warnings.filterwarnings("ignore")
H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

def resolve(u):
    r=requests.get(u,headers=H,allow_redirects=True,timeout=30,verify=False)
    return r.url, r

if __name__=='__main__':
    for u in sys.argv[1:]:
        try:
            final,r=resolve(u)
            print(r.status_code, r.headers.get('content-type','')[:30], final)
        except Exception as e:
            print("ERR", u[:60], type(e).__name__, str(e)[:100])
