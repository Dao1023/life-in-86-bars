"""解析 2020 上海人口普查年鉴 表3-1 单岁人口 -> csv"""
import xlrd, csv, os, re

SRC = os.path.join(os.path.dirname(__file__), "..", "raw", "rkpc2020", "ANJ-3-01.xls")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "shanghai_pop_age_2020_census.csv")

b = xlrd.open_workbook(SRC)
s = b.sheet_by_index(0)
rows = []
total = None
for i in range(s.nrows):
    lab = str(s.cell_value(i, 0)).strip()
    if lab == "总计":
        total = s.cell_value(i, 1)
        continue
    m = re.fullmatch(r"(\d{1,3})", lab.replace("  ", "").strip())
    if m:
        rows.append((int(m.group(1)), s.cell_value(i, 1)))
    elif "100岁及以上" in lab:
        rows.append((100, s.cell_value(i, 1)))

print("single-age rows:", len(rows), "ages", rows[0][0], "..", rows[-1][0])
sm = sum(p for _, p in rows)
print(f"官方总计 = {total:,.0f}")
print(f"单岁加总 = {sm:,.0f}")
print(f"差 = {sm-total:,.0f}  ({(sm/total-1)*100:+.6f}%)")

with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["age", "population", "share", "level", "source_id", "year", "note"])
    for a, p in rows:
        note = "七普时点 2020-11-01；常住人口" if a < 100 else "七普时点 2020-11-01；100岁及以上合并"
        w.writerow([a, int(p), round(p / total, 8), "single_year", "CENSUS2020-SH-T3-1", 2020, note])
print("written", OUT)
