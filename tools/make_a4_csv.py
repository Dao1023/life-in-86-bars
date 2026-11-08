# -*- coding: utf-8 -*-
import csv, os
os.makedirs('data', exist_ok=True)

NBS = ["食品烟酒","衣着","居住","生活用品及服务","医疗保健","交通和通信","教育文化娱乐","其他用品和服务"]

NI = {  # 倪红福、李善同、何建武 2014 表2, 2007 城镇, 户主年龄, %
 "25-29":[38.00,11.95,15.73,8.20,5.41,9.59,6.88,4.25],
 "30-34":[39.00,11.53,11.60,7.52,5.75,9.48,10.93,4.19],
 "35-39":[39.12,10.61,9.44,7.11,5.84,11.30,12.03,4.56],
 "40-44":[41.13,10.03,8.09,5.71,6.17,8.89,15.50,4.47],
 "45-49":[40.61,9.21,7.80,5.66,5.39,10.23,17.28,3.82],
 "50-54":[41.94,9.82,11.86,6.30,6.90,9.36,9.69,4.14],
 "55-59":[45.38,9.31,7.83,6.39,8.12,9.47,9.62,3.88],
 "60-64":[47.67,8.38,9.76,5.99,10.00,7.74,6.54,3.92],
 "65-69":[50.35,7.86,7.84,4.94,13.31,6.39,5.53,3.77],
}
SHI = {  # 石贝贝 2017 表3, CHARLS, 60+, %
 ("2011","城镇"):[54.6,4.4,11.5,8.1,11.2,7.9,1.6,0.7],
 ("2011","农村"):[54.2,4.6,14.7,8.4,11.7,5.6,0.5,0.3],
 ("2013","城镇"):[45.1,3.3,10.3,8.5,9.4,6.2,17.2,0.2],
 ("2013","农村"):[54.7,2.3,6.6,6.3,9.7,3.6,16.5,0.3],
}

rows=[]
for ag,vals in NI.items():
    lo,hi = ag.split('-')
    for c,v in zip(NBS,vals):
        rows.append(dict(source_id="S1", source="倪红福、李善同、何建武(2014)",
            title="人口结构变化对消费结构及储蓄率的影响分析",
            outlet="人口与发展 20(5):25-34", dataset="CHIPS 2007 (城镇住户)",
            year=2007, geography="全国城镇", unit_of_obs="家庭(按户主年龄分组)",
            age_basis="户主年龄", age_group=ag, age_lo=int(lo), age_hi=int(hi),
            category_nbs=c, value=v, unit="%", measure="样本描述统计-消费支出构成占比",
            table_ref="表2", page="28",
            url="https://ccj.pku.edu.cn/Article/DownLoad?id=331122480&type=ArticleFile",
            note="行内合计=100.00，原表保留两位小数；PDF 为旧字形，数值经 200dpi 页面图像逐格核对"))

for (yr,geo),vals in SHI.items():
    for c,v in zip(NBS,vals):
        rows.append(dict(source_id="S2", source="石贝贝(2017)",
            title="我国城乡老年人口消费的实证研究——兼论“退休—消费之谜”",
            outlet="人口研究 41(3):53-64", dataset="CHARLS 2011/2013 (60岁及以上)",
            year=int(yr), geography=geo, unit_of_obs="老年家庭(家庭人均消费)",
            age_basis="受访者/家户老年人年龄", age_group="60+", age_lo=60, age_hi="",
            category_nbs=c, value=v, unit="%", measure="样本描述统计-消费支出构成占比",
            table_ref="表3", page="58",
            url="https://rkyj.ruc.edu.cn/EN/article/downloadArticleFile.do?attachType=PDF&id=3469",
            note="2011年医疗保健占比1.6%(城镇)/0.5%(农村)，作者解释为两期调查口径侧重不同，疑低估"))

cols=["source_id","source","title","outlet","dataset","year","geography","unit_of_obs",
      "age_basis","age_group","age_lo","age_hi","category_nbs","value","unit","measure",
      "table_ref","page","url","note"]
with open('data/china_age_bands.csv','w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(rows)
print("rows",len(rows))

# wide pivot for S1
with open('data/china_age_bands_wide_s1.csv','w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f); w.writerow(["age_group"]+NBS+["total"])
    for ag,vals in NI.items():
        w.writerow([ag]+[f"{v:.2f}" for v in vals]+[f"{sum(vals):.2f}"])
print(open('data/china_age_bands_wide_s1.csv',encoding='utf-8-sig').read())
