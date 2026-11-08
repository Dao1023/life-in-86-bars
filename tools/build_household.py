"""从七普年鉴 Excel 生成家庭结构附表：分年龄段独居率 + 家庭户规模分布。

来源：
  表5-2 各地区分年龄、性别的一人户      ANJ-5-02.xls（其中「总计」行的 5 岁组）
  表1-8 各地区家庭户规模                ANJ-1-08.xls（其中「总计」行）
输出：
  data/shanghai_household_by_age.csv
"""
import csv
import os

import xlrd

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(ROOT, "raw", "rkpc2020")
DATA = os.path.join(ROOT, "data")

BANDS = [(0, 14), (15, 19), (20, 24), (25, 29), (30, 34), (35, 39), (40, 44),
         (45, 49), (50, 54), (55, 59), (60, 64), (65, 100)]

s = xlrd.open_workbook(os.path.join(RAW, "ANJ-5-02.xls")).sheet_by_index(0)
row = [s.cell_value(4, j) for j in range(s.ncols)]
alone = {bd: row[4 + 3 * k] for k, bd in enumerate(BANDS)}

P = {int(r["age"]): float(r["population"])
     for r in csv.DictReader(open(os.path.join(DATA, "shanghai_pop_age_2020_census.csv"),
                                  encoding="utf-8-sig"))}

out = os.path.join(DATA, "shanghai_household_by_age.csv")
with open(out, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["band", "age_lo", "age_hi", "population", "one_person_households",
                "living_alone_pct", "year", "source_id", "note"])
    for lo, hi in BANDS:
        pop = sum(P.get(a, 0.0) for a in range(lo, hi + 1))
        n = alone[(lo, hi)]
        lab = f"{lo}-{hi}" if hi < 100 else f"{lo}+"
        w.writerow([lab, lo, hi, int(pop), int(n), round(n / pop * 100, 2), 2020,
                    "CENSUS2020-SH-T5-2",
                    "独居率=该年龄一人户数/该年龄常住人口；一人户指单人组成的家庭户"])
print("written", out)

# 家庭户规模（2020 七普，全市）
s8 = xlrd.open_workbook(os.path.join(RAW, "ANJ-1-08.xls")).sheet_by_index(0)
r8 = [s8.cell_value(4, j) for j in range(s8.ncols)]
hh = r8[1]
sizes = [(1, r8[2]), (2, r8[4]), (3, r8[6]), (4, r8[8]), (5, r8[10]),
         (6, r8[12]), (7, r8[14]), (8, r8[16]), (9, r8[18]), (10, r8[20])]
totp = sum(k * v for k, v in sizes)
print(f"家庭户 {hh:,.0f} 户，推算家庭户人口 {totp:,.0f}，户均 {totp/hh:.3f}")
for k, v in sizes:
    print(f"  {k:2d}人户 {v:9,.0f}  {v/hh*100:5.2f}%")
