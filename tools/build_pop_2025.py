"""用 2020 七普单岁 + 2025 全国1%人口抽样调查四段控制数，构造 2025-11-01 上海常住分年龄人口。

方法（全部可复算）：
  1. 队列推移：2020-11-01 年龄 a 的人，2025-11-01 为 a+5；用七普表 6-4
     的分年龄死亡率（2019.11-2020.10）算 5 年存活率。
  2. 0-4 岁（2021-2025 出生）用统计公报的常住出生人数（11.6/10.8/9.8/11.8/10.7 万）。
  3. 配平（raking）：四段互不重叠的官方控制数
       0-14 = 232 万、15-59 = 1567 万、60-64 = 168 万、65+ = 517 万
     （2025 年 1% 抽样调查公报，2025-11-01，合计 2484 万）。
"""
import csv, os
import xlrd

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(ROOT, "raw", "rkpc2020")

# ---------- 1. 2020 单岁人口 ----------
b = xlrd.open_workbook(os.path.join(RAW, "ANJ-3-01.xls"))
s = b.sheet_by_index(0)
import re
P0 = {}
TOT0 = None
for i in range(s.nrows):
    lab = str(s.cell_value(i, 0)).strip()
    if lab == "总计":
        TOT0 = s.cell_value(i, 1)
        continue
    m = re.fullmatch(r"(\d{1,3})", lab)
    if m:
        P0[int(m.group(1))] = s.cell_value(i, 1)
    elif "100岁及以上" in lab:
        P0[100] = s.cell_value(i, 1)
assert len(P0) == 101 and abs(sum(P0.values()) - TOT0) < 1

# ---------- 2. 死亡率 ----------
b2 = xlrd.open_workbook(os.path.join(RAW, "ANJ-6-04.xls"))
s2 = b2.sheet_by_index(0)
M = {}
for i in range(s2.nrows):
    lab = str(s2.cell_value(i, 0)).strip()
    m = re.fullmatch(r"(\d{1,3})", lab)
    if m:
        M[int(m.group(1))] = float(s2.cell_value(i, 7)) / 1000.0
M[100] = M.get(100, 0.375)

def surv(a, n=1):
    """从年龄 a 存活 n 年的概率（年死亡率视为中心死亡率，q=1-exp(-m)）"""
    p = 1.0
    for k in range(n):
        aa = min(a + k, 100)
        p *= (1.0 - (1.0 - __import__("math").exp(-M.get(aa, 0.38))))
    return p

# ---------- 3. 队列推移 5 年 ----------
P = {}
for a in range(0, 96):
    P[a + 5] = P0.get(a, 0.0) * surv(a, 5)
# 96-100 全部并入 100+
tail = sum(P0.get(a, 0.0) * surv(a, 5) for a in range(96, 101))
P[100] = P.get(100, 0.0) + tail

# ---------- 4. 0-4 岁：2021-2025 常住出生 ----------
BIRTHS = {4: 11.6e4, 3: 10.8e4, 2: 9.8e4, 1: 11.8e4, 0: 10.7e4}  # 万 -> 人
for a, n in BIRTHS.items():
    P[a] = n * surv(0, a)          # 出生后存活到 2025-11-01 约 a+0.5 年，近似按 a 年

tot_raw = sum(P.values())

# ---------- 5. 配平到官方四段 ----------
TARGET = {"0-14": 232e4, "15-59": 1567e4, "60-64": 168e4, "65+": 517e4}
GROUPS = {"0-14": range(0, 15), "15-59": range(15, 60), "60-64": range(60, 65),
          "65+": range(65, 101)}
fac = {}
for g, rng in GROUPS.items():
    cur = sum(P[a] for a in rng)
    fac[g] = TARGET[g] / cur
    for a in rng:
        P[a] *= fac[g]
TOT = sum(P.values())

print(f"2020 单岁加总      {TOT0:,.0f}")
print(f"队列推移后（配平前）{tot_raw:,.0f}")
for g in GROUPS:
    print(f"  {g:6s} 配平系数 {fac[g]:.4f}")
print(f"配平后总计         {TOT:,.0f}  (目标 24,840,000)")

rows = []
for a in range(0, 101):
    rows.append((a, int(round(P[a])), P[a] / TOT))

OUT = os.path.join(ROOT, "data", "shanghai_pop_age.csv")
with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["age", "population", "share", "level", "source_id", "year", "note"])
    for a, p, sh in rows:
        if a < 5:
            note = "0-4岁由2021-2025年常住出生数推算(11.6/10.8/9.8/11.8/10.7万)"
        elif a == 100:
            note = "100岁及以上合并"
        else:
            note = "2020七普单岁×5年存活率队列推移"
        w.writerow([a, p, round(sh, 8), "interpolated",
                    "CENSUS2020-T3-1+T6-4/2025-1PCT", 2025,
                    note + "；已配平至2025年1%抽样调查四段控制数"])

# 四段
def sh(a, b_):
    return sum(P[x] for x in range(a, b_ + 1)) / TOT * 100
print(f"0-14 {sh(0,14):.2f}%  15-59 {sh(15,59):.2f}%  60+ {sh(60,100):.2f}%  65+ {sh(65,100):.2f}%")
print("written", OUT)
