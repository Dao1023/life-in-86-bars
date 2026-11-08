import pandas as pd, csv

MAP = {  # row label prefix -> bucket
 "1.食品及非酒精飲料":"food", "11.餐廳及住宿":"food",
 "3.衣著鞋襪及服飾用品":"apparel",
 "4.住宅服務、水電瓦斯及其他燃料":"housing",
 "7.交通":"transport", "8.資通訊":"transport",
 "6.醫療保健":"healthcare",
 "10.教育":"education",
 "9.休閒、運動與文化":"entertainment",
 "2.菸酒及檳榔":"other", "5.家具設備及家務維護":"other",
 "12.保險及金融服務":"other", "13.其他":"other",
}
BANDS = ["<30","30-34","35-39","40-44","45-54","55-64","65+"]

def parse(path, year):
    df = pd.read_excel(path, header=None)
    # header row 6 (or 47): col1..8 labels
    hdr = df.iloc[6, 1:9].tolist()
    out = {}
    total = None
    for i in range(len(df)):
        lab = df.iat[i, 0]
        if not isinstance(lab, str): continue
        lab = lab.replace("\u3000","").strip()
        if lab.startswith("四、消費支出") or lab == "消費支出":
            vals = [float(df.iat[i, c]) for c in range(1, 9)]
            if total is None and lab.startswith("四"):
                total = vals
            continue
        for k, b in MAP.items():
            if lab.startswith(k):
                out.setdefault(k, [float(df.iat[i, c]) for c in range(1, 9)])
    return hdr, total, out

rows = []
for path, year in [("../raw/tw113_age159-164.xls", 2024), ("../raw/tw114_age159-164.xls", 2025)]:
    hdr, total, out = parse(path, year)
    assert total, path
    # aggregate
    agg = {b: [0.0]*8 for b in ["food","housing","transport","healthcare","education","apparel","entertainment","other"]}
    for k, vals in out.items():
        b = MAP[k]
        agg[b] = [a+v for a, v in zip(agg[b], vals)]
    for col, band in enumerate(["ALL"]+BANDS):
        tot = total[col]
        for b in ["food","housing","transport","healthcare","education","apparel","entertainment","other"]:
            v = agg[b][col]
            rows.append(dict(region="Taiwan", year=year, age_band=band, category=b,
                             value=round(v,0), share_pct=round(100*v/tot,2),
                             unit="NTD/household/year",
                             source_url="https://www.stat.gov.tw/News_Content.aspx?n=3911&s=" + ("235199" if year==2024 else "236589")))
    print(year, "total(ALL)=%.0f"%total[0], {b: round(100*agg[b][0]/total[0],1) for b in agg})

with open("../data/eastasia_age_consumption.csv","w",newline="",encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["region","year","age_band","category","value","share_pct","unit","source_url"])
    w.writeheader(); w.writerows(rows)
print("rows", len(rows))
