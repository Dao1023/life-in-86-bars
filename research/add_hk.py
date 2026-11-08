import csv
# HK 2019/20 Table 14, HK$/household/month, all households (n=2,395,000), total 30,230
vals = {
 "food":        3087 + 5084,   # food & non-alc bev + restaurants & accommodation
 "housing":     12504,         # housing, water, electricity, gas & other fuels
 "transport":   2013 + 1145,   # transport + information & communication
 "healthcare":  936,
 "education":   1159,
 "apparel":     750,
 "entertainment": 809,
 "other":       157 + 1213 + 476 + 897,  # alcohol/tobacco + furnishings + insurance/financial + personal care/misc
}
tot = 30230
url = "https://www.censtatd.gov.hk/en/data/stat_report/product/B1060008/att/B10600082020XXXXB0100.pdf"
rows = []
for k, v in vals.items():
    rows.append(dict(region="Hong Kong", year="2019/20", age_band="ALL", category=k,
                     value=v, share_pct=round(100*v/tot,2), unit="HKD/household/month", source_url=url))
with open("../data/eastasia_age_consumption.csv","a",newline="",encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["region","year","age_band","category","value","share_pct","unit","source_url"])
    w.writerows(rows)
print("sum check", sum(vals.values()), "vs", tot, round(100*sum(vals.values())/tot,1))
