import requests, fitz, io, re, json, os
Q = ["consumption age profile China urban household",
     "age structure household consumption China categories",
     "life-cycle consumption China urban",
     "population aging consumption structure China micro data"]
seen={}
for q in Q:
    r=requests.get("https://api.openalex.org/works", params={"search":q,"per-page":15,
        "mailto":"research@example.org","filter":"has_oa_accepted_or_published_version:true"}, timeout=40)
    for w in r.json().get("results",[]):
        loc=(w.get("best_oa_location") or {})
        pdf=loc.get("pdf_url")
        if pdf: seen[w["id"]]=(w.get("title"), w.get("publication_year"), pdf)
print("candidates", len(seen))
os.makedirs("raw/pdf/oa", exist_ok=True)
rows=[]
for i,(k,(t,y,pdf)) in enumerate(seen.items()):
    try:
        resp=requests.get(pdf, timeout=60, verify=False, headers={"User-Agent":"Mozilla/5.0"})
        d=fitz.open(stream=resp.content, filetype="pdf")
        txt="\n".join(pg.get_text() for pg in d)
    except Exception as e:
        rows.append((t,y,pdf,"ERR "+str(e)[:60])); continue
    open(f"raw/pdf/oa/o{i:02d}.txt","w",encoding="utf-8").write(txt)
    low=txt.lower()
    score=sum(low.count(w) for w in ["food","clothing","housing","medical","education","transport"])
    bad=len(re.findall(r"\btable\s*\d", low))
    rows.append((t,y,pdf,f"pages={len(d)} score={score} tables={bad}"))
for r in rows: print(" |".join(str(x)[:90] for x in r))
