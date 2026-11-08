# -*- coding: utf-8 -*-
"""build_household.py — 上海「家庭口径」（元/户/年，户主年龄 22–85）构建脚本。

输入（运行时读取，不硬编码人均曲线）：
  data/shanghai_lifecycle.csv            人均口径 86 行（审计更新后重跑即同步）
  data/shanghai_lifecycle_scenarios.csv  人均三情景（low/base/high）
  data/shanghai_lifecycle.json           类别 id/label/color、人均锚点 54,980
  data/shanghai_pop_age_2020_census.csv  七普上海单岁常住人口（户主年龄权重的分母）
  data/shanghai_household_by_age.csv     七普一人户分年龄（仅作参照列）

输出：
  data/shanghai_lifecycle_household.csv
  data/shanghai_lifecycle_household.json
  data/household_size_by_age.csv

构造规则（用户已确认的「标准家庭生命周期」）：
  22–27 单身户        1.0 人   [本人]
  28–29 新婚无孩      2.0 人   [本人, 配偶 = a-2]
  30–52 有孩期        3.0 人   [本人, 配偶 = a-2, 子女 = a-30]
  53–69 空巢          2.0 人   [本人, 配偶 = a-2]
  70–85 老年          1.4 人   [本人 + 0.4×配偶(a-2)，0.4 = 丧偶期望]

每户消费 = Σ 成员在人均表中的消费（0–17 岁的人均表数值本身即「家庭为一个孩子
一年的支出」，直接相加，不再乘系数）。

户主年龄权重：构造值 W_a ∝ 2020 七普 22–85 岁单岁常住人口（中性假设：该年龄段
每个人等概率为户主）。该权重不含任何消费信息，因此锚点校验不是自我实现。

无随机数；重跑逐字节一致（除浮点末位）。
"""
from __future__ import annotations

import csv
import json
import os
from collections import OrderedDict

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")

CATS = ["food", "clothing", "housing", "durables", "transport", "education", "health", "other"]
CAT_COLS = ["cat_" + c for c in CATS]

# ---- 实测锚点（七普，2020）------------------------------------------------
CENSUS_HOUSEHOLDS = 9_644_628          # 表1-8 上海 家庭户户数
CENSUS_HH_POPULATION = 22_345_063      # 表1-8 各规模户×人数 推算
CENSUS_HH_SIZE_EXACT = CENSUS_HH_POPULATION / CENSUS_HOUSEHOLDS  # 2.316737...
# 家庭口径锚点用 2.32（七普家庭户口径，上游确认）；2.3167 为精确值，2.24 为
# 2025 年 1% 抽样口径（敏感性用），2.63 为 2024 户籍含集体户口径（不可混用）。
ANCHOR_HH_SIZE = 2.32
HH_SIZE_SENSITIVITY = 2.24

# ---- 家庭生命周期构成规则 --------------------------------------------------
# (lo, hi, size, composition, members: [(offset, weight), ...])
STAGES = [
    (22, 27, 1.0, "1A", [(0, 1.0)]),
    (28, 29, 2.0, "2A", [(0, 1.0), (-2, 1.0)]),
    (30, 52, 3.0, "2A+1C", [(0, 1.0), (-2, 1.0), (-30, 1.0)]),
    (53, 69, 2.0, "2A", [(0, 1.0), (-2, 1.0)]),
    (70, 85, 1.4, "1.4A", [(0, 1.0), (-2, 0.4)]),
]
STAGE_META = [
    {"id": "h22", "label": "单身户", "start": 22, "end": 27, "segment": "22-85 家庭口径", "color": "#9B8EA8", "household_size": 1.0},
    {"id": "h28", "label": "新婚无孩", "start": 28, "end": 29, "segment": "22-85 家庭口径", "color": "#8FA9B8", "household_size": 2.0},
    {"id": "h30", "label": "有孩期", "start": 30, "end": 52, "segment": "22-85 家庭口径", "color": "#C4553B", "household_size": 3.0},
    {"id": "h53", "label": "空巢", "start": 53, "end": 69, "segment": "22-85 家庭口径", "color": "#2F5D62", "household_size": 2.0},
    {"id": "h70", "label": "老年（含丧偶）", "start": 70, "end": 85, "segment": "22-85 家庭口径", "color": "#7FA6A0", "household_size": 1.4},
]
AGE_LO, AGE_HI = 22, 85


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fnum(x):
    return float(str(x).replace(",", "").strip())


def stage_of(age):
    for lo, hi, size, comp, members in STAGES:
        if lo <= age <= hi:
            return size, comp, members
    raise ValueError(age)


def fmt1(x):
    return round(x + 0.0, 1)


def main():
    pc_rows = {int(r["age"]): r for r in read_csv(os.path.join(DATA, "shanghai_lifecycle.csv"))}
    pc = {a: {c: fnum(r["cat_" + c]) for c in CATS} for a, r in pc_rows.items()}
    pc_total = {a: fnum(r["total"]) for a, r in pc_rows.items()}

    with open(os.path.join(DATA, "shanghai_lifecycle.json"), encoding="utf-8") as f:
        pc_json = json.load(f)
    per_capita_anchor = float(pc_json["meta"]["anchor_total"])
    categories = pc_json["categories"]  # 与人均口径完全同 id/label/color
    assert [c["id"] for c in categories] == CATS

    # 户主年龄权重：2020 七普 22–85 岁人口占比（构造值）
    pop = {int(r["age"]): fnum(r["population"])
           for r in read_csv(os.path.join(DATA, "shanghai_pop_age_2020_census.csv"))}
    raw_w = {a: pop[a] for a in range(AGE_LO, AGE_HI + 1)}
    wsum = sum(raw_w.values())
    weight = {a: raw_w[a] / wsum for a in raw_w}

    # 七普一人户分年龄独居率（参照列）
    lone = {}
    for r in read_csv(os.path.join(DATA, "shanghai_household_by_age.csv")):
        lo, hi = int(r["age_lo"]), int(r["age_hi"])
        for a in range(max(lo, AGE_LO), min(hi, AGE_HI) + 1):
            lone[a] = (fnum(r["living_alone_pct"]), r["band"])

    # ---- 逐岁构造 ---------------------------------------------------------
    rows = []
    abs_by_cat = {c: [] for c in CATS}
    share_by_cat = {c: [] for c in CATS}
    totals, sizes = [], []
    for a in range(AGE_LO, AGE_HI + 1):
        size, comp, members = stage_of(a)
        cat_vals = {c: 0.0 for c in CATS}
        for off, w in members:
            src = pc[a + off]
            for c in CATS:
                cat_vals[c] += w * src[c]
        cat_vals = {c: fmt1(v) for c, v in cat_vals.items()}
        total = fmt1(sum(cat_vals.values()))
        shares = {c: round(cat_vals[c] / total, 4) if total else 0.0 for c in CATS}
        rows.append(dict(age=a, size=size, comp=comp, cat=cat_vals, total=total, share=shares))
        for c in CATS:
            abs_by_cat[c].append(cat_vals[c])
            share_by_cat[c].append(shares[c])
        totals.append(total)
        sizes.append(size)

    # ---- 校验 -------------------------------------------------------------
    row_err = max(abs(sum(r["cat"].values()) - r["total"]) for r in rows)
    weighted = sum(weight[r["age"]] * r["total"] for r in rows)
    anchor = per_capita_anchor * ANCHOR_HH_SIZE
    dev_pct = (weighted / anchor - 1.0) * 100.0
    cons_size = sum(weight[r["age"]] * r["size"] for r in rows)

    neg = [r["age"] for r in rows if r["total"] < 0 or any(v < 0 for v in r["cat"].values())]
    lo_row, hi_row = rows[0], rows[-1]
    bounds_ok = (lo_row["total"] > 0.2 * anchor) and (hi_row["total"] > 0.2 * anchor) \
                and (max(totals) < 2.0 * anchor) and not neg

    # 与人均口径的对照
    def pc_at(age):
        return pc_total[age]

    # 七普家庭户规模构成（表1-8，实测）
    census_size_shares = {"1": 0.2837, "2": 0.3455, "3": 0.2239, "4+": 0.1469}
    w_single = sum(weight[a] for a in range(22, 28))
    w_couple = sum(weight[a] for a in range(28, 30)) + sum(weight[a] for a in range(53, 70))
    w_family = sum(weight[a] for a in range(30, 53))
    w_elder = sum(weight[a] for a in range(70, 86))
    cons_size_shares = {"1": round(w_single, 4), "2": round(w_couple, 4),
                        "3": round(w_family, 4), "1.4(老年)": round(w_elder, 4)}

    checks = {
        "row_sum_max_abs_error": round(row_err, 10),
        "row_sum_pass": row_err < 0.01,
        "weighted_household_mean": round(weighted, 2),
        "anchor_household": round(anchor, 2),
        "anchor_deviation_pct": round(dev_pct, 4),
        "anchor_pass_1pct": abs(dev_pct) < 1.0,
        "anchor_sensitivity_2.24_dev_pct": round((weighted / (per_capita_anchor * HH_SIZE_SENSITIVITY) - 1) * 100, 3),
        "constructed_mean_household_size": round(cons_size, 4),
        "census_mean_household_size": round(ANCHOR_HH_SIZE, 4),
        "census_mean_household_size_exact": round(CENSUS_HH_SIZE_EXACT, 4),
        "size_deviation_pct": round((cons_size / ANCHOR_HH_SIZE - 1) * 100, 4),
        "constructed_size_shares": cons_size_shares,
        "census_size_shares": census_size_shares,
        "census_1p_share_gap_pp": round((w_single - census_size_shares["1"]) * 100, 2),
        "census_65plus_living_alone_pct": 12.48,
        "negative_values": neg,
        "bounds_pass": bounds_ok,
        "single_26_equal_per_capita": round(abs(rows[26 - AGE_LO]["total"] - pc_at(26)), 2),
        "hh33_total": round(rows[33 - AGE_LO]["total"], 1),
        "pc33_total": round(pc_at(33), 1),
        "hh33_over_pc33": round(rows[33 - AGE_LO]["total"] / pc_at(33), 3),
        "peak_age": max(rows, key=lambda r: r["total"])["age"],
        "peak_value": max(r["total"] for r in rows),
        "trough_age": min(rows, key=lambda r: r["total"])["age"],
        "trough_value": min(r["total"] for r in rows),
    }

    # ---- CSV --------------------------------------------------------------
    out_csv = os.path.join(DATA, "shanghai_lifecycle_household.csv")
    header = (["age"] + CAT_COLS + ["total"] +
              ["share_" + c for c in CATS] +
              ["household_size", "composition", "basis", "note"])
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            a = r["age"]
            if a <= 27:
                note = "单身户：仅本人"
            elif a <= 29:
                note = f"新婚无孩：本人{a} + 配偶{a - 2}"
            elif a <= 47:
                note = f"三口之家：本人{a} + 配偶{a - 2} + 子女{a - 30}"
            elif a <= 52:
                note = (f"三口之家：本人{a} + 配偶{a - 2} + 子女{a - 30}"
                        f"（子女已{a - 30}岁，属18–22岁高等教育/初入社会段，见口径张力）")
            elif a <= 69:
                note = f"空巢：本人{a} + 配偶{a - 2}"
            else:
                note = f"老年户：本人{a} + 0.4×配偶{a - 2}（丧偶期望 1.4 人）"
            w.writerow([a] + [r["cat"][c] for c in CATS] + [r["total"]] +
                       [r["share"][c] for c in CATS] +
                       [r["size"], r["comp"], "构造-家庭口径·成员加总", note])

    # ---- household_size_by_age.csv ---------------------------------------
    out_size = os.path.join(DATA, "household_size_by_age.csv")
    with open(out_size, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["age", "stage", "household_size", "composition", "size_source",
                    "head_weight", "head_weight_source",
                    "census_living_alone_pct_2020", "census_band_2020", "note"])
        for r in rows:
            a = r["age"]
            st = next(s["label"] for s in STAGE_META if s["start"] <= a <= s["end"])
            lp, band = lone.get(a, ("", ""))
            if a <= 27:
                note = "构造 1.0 人；22–27 岁户主权重占 11.1%，七普 20–29 岁一人户仅占全部家庭户 6.6%"
            elif a <= 29:
                note = "构造 2.0 人；新婚无孩"
            elif a <= 52:
                note = "构造 3.0 人；七普四人及以上户占 14.7%，本模型无 4 人户"
            elif a <= 69:
                note = "构造 2.0 人；空巢；七普 30–64 岁一人户占全部家庭户 16.5%，本模型记为 0"
            else:
                note = "构造 1.4 人（1+0.4 配偶）；七普 65+ 独居率 12.48%，低于台湾 65+ 的 1.90 人"
            w.writerow([a, st, r["size"], r["comp"], "构造-标准家庭生命周期",
                        round(weight[a], 8), "构造-七普22-85岁人口等比",
                        lp, band, note])

    # ---- 三情景 -----------------------------------------------------------
    scen_rows = read_csv(os.path.join(DATA, "shanghai_lifecycle_scenarios.csv"))
    scen = {}
    for sc in ("low", "base", "high"):
        d = {int(r["age"]): r for r in scen_rows if r["scenario"] == sc}
        s_abs = {c: [] for c in CATS}
        s_tot = []
        for a in range(AGE_LO, AGE_HI + 1):
            size, comp, members = stage_of(a)
            cv = {c: 0.0 for c in CATS}
            for off, wt in members:
                for c in CATS:
                    cv[c] += wt * fnum(d[a + off]["cat_" + c])
            cv = {c: fmt1(v) for c, v in cv.items()}
            t = fmt1(sum(cv.values()))
            for c in CATS:
                s_abs[c].append(cv[c])
            s_tot.append(t)
        scen[sc] = {
            "total": s_tot,
            "absolute": s_abs,
            "weighted_mean": round(sum(weight[a] * s_tot[a - AGE_LO] for a in range(AGE_LO, AGE_HI + 1)), 1),
        }

    # ---- JSON -------------------------------------------------------------
    peak = max(rows, key=lambda r: r["total"])
    trough = min(rows, key=lambda r: r["total"])
    comparison_ages = [22, 26, 28, 30, 33, 40, 47, 52, 53, 65, 70, 85]
    comparison = [{
        "age": a,
        "per_capita": round(pc_at(a), 1),
        "household": rows[a - AGE_LO]["total"],
        "household_size": rows[a - AGE_LO]["size"],
        "ratio": round(rows[a - AGE_LO]["total"] / pc_at(a), 3),
    } for a in comparison_ages]

    sources = list(pc_json["sources"]) + [
        {"id": "CENSUS2020-SH-T1-8", "level": "A",
         "label": "中国人口普查年鉴2020 表1-8 各地区家庭户规模（上海行）",
         "url": "https://www.stats.gov.cn/sj/pcsj/rkpc/7rp/zk/indexch.htm",
         "use": "家庭户 9,644,628 户、家庭户人口 22,345,063 人 → 户均 2.3167（实测锚点）"},
        {"id": "CENSUS2020-SH-T5-1", "level": "A",
         "label": "中国人口普查年鉴2020 表5-1 全市不同规模的家庭户类别",
         "url": "https://www.stats.gov.cn/sj/pcsj/rkpc/7rp/zk/indexch.htm",
         "use": "一人户 28.37%、二人户 34.55%、三人户 22.39%、四人及以上 14.69%；一代户 59.35%"},
        {"id": "CENSUS2020-SH-T5-2", "level": "A",
         "label": "中国人口普查年鉴2020 表5-2 各地区分年龄、性别的一人户（上海）",
         "url": "https://www.stats.gov.cn/sj/pcsj/rkpc/7rp/zk/indexch.htm",
         "use": "分年龄独居率参照列（25–29 岁 19.11%、65+ 12.48%）"},
        {"id": "CENSUS2020-SH-T3-1", "level": "A",
         "label": "中国人口普查年鉴2020 表3-1 上海市分年龄人口",
         "url": "https://www.stats.gov.cn/sj/pcsj/rkpc/7rp/zk/indexch.htm",
         "use": "户主年龄权重分母（22–85 岁单岁常住人口）"},
        {"id": "CONSTRUCT-HH-COMP", "level": "D",
         "label": "家庭构成规则（模型构造，用户确认的标准家庭生命周期）",
         "url": "",
         "use": "1 / 2 / 3 / 2 / 1.4 人五阶段；非官方观测"},
        {"id": "CONSTRUCT-HH-WEIGHT", "level": "D",
         "label": "户主年龄权重（构造：22–85 岁人口等比）",
         "url": "",
         "use": "无官方「按户主年龄分的家庭户」表时的中性构造；不含消费信息"},
    ]

    out_json = os.path.join(DATA, "shanghai_lifecycle_household.json")
    doc = OrderedDict([
        ("meta", OrderedDict([
            ("title", "上海一个家庭的一生：户主 22–85 岁逐年家庭消费"),
            ("city", "上海"), ("year", 2024), ("currency", "CNY"),
            ("unit", "元/户/年"),
            ("price_base", "2024 年上海价"),
            ("basis", "模型估算：人均表成员加总，非官方分年龄观测"),
            ("disclaimer",
             "横轴是户主年龄，不是家庭成员年龄。每户消费 = 各成员在人均表中的消费之和；"
             "家庭构成按户主年龄分五阶段。官方从未发布「户主年龄 × 消费」交叉表，"
             "任何一格都不是官方观测值。"),
            ("household_size_source",
             "构成 1/2/3/2/1.4 人为【构造】（标准家庭生命周期，用户确认）；"
             "锚点户均 2.32 为【实测】七普 2020 表1-8（9,644,628 户 / 22,345,063 人，精确 2.3167）；"
             "2025 年 1% 抽样 2.24、2024 户籍含集体户 2.63 为不同口径，不混用"),
            ("anchor_household", round(anchor, 2)),
            ("anchor_household_size", ANCHOR_HH_SIZE),
            ("anchor_household_size_exact_census", round(CENSUS_HH_SIZE_EXACT, 4)),
            ("anchor_household_size_sensitivity", {
                "2025_1pct_sample": HH_SIZE_SENSITIVITY,
                "note": "若改用 2.24，加权户均消费相对锚点偏离见 calibration.anchor_sensitivity_2.24_dev_pct"}),
            ("household_size_benchmarks", {
                "constructed_mean_size": round(cons_size, 4),
                "census_mean_size_2020": round(CENSUS_HH_SIZE_EXACT, 4),
                "constructed_size_shares": cons_size_shares,
                "census_size_shares_2020": census_size_shares,
                "note": "构造的一人户占比 11.1% 远低于七普 28.37%：标准生命周期无 4 人户/"
                        "三代户，且把 30–69 岁的单身者一律记为二人户；这是锚点能成立的隐性约束。",
            }),
            ("per_capita_anchor", per_capita_anchor),
            ("weighted_mean", round(weighted, 2)),
            ("constructed_mean_household_size", round(cons_size, 4)),
            ("peak_age", peak["age"]), ("peak_value", peak["total"]),
            ("trough_age", trough["age"]), ("trough_value", trough["total"]),
            ("peak_to_trough", round(peak["total"] / trough["total"], 3)),
            ("range_min", min(totals)), ("range_max", max(totals)),
            ("calibration", checks),
            ("composition_rules", [
                {"head_age": "22-27", "household_size": 1.0, "composition": "1A",
                 "members": ["本人"], "note": "单身户"},
                {"head_age": "28-29", "household_size": 2.0, "composition": "2A",
                 "members": ["本人", "配偶(a-2)"], "note": "新婚无孩"},
                {"head_age": "30-52", "household_size": 3.0, "composition": "2A+1C",
                 "members": ["本人", "配偶(a-2)", "子女(a-30)"],
                 "note": "有孩期；48–52 岁时子女已 18–22 岁，属高等教育/初入社会段"},
                {"head_age": "53-69", "household_size": 2.0, "composition": "2A",
                 "members": ["本人", "配偶(a-2)"], "note": "空巢"},
                {"head_age": "70-85", "household_size": 1.4, "composition": "1.4A",
                 "members": ["本人", "0.4×配偶(a-2)"],
                 "note": "1.4 人 = 1 + 0.4 丧偶期望；消费按 0.4 权重加总"},
            ]),
            ("head_weight_source", "构造：2020 七普 22–85 岁单岁常住人口等比（无消费信息）"),
            ("comparison_per_capita", comparison),
            ("generated_by", "build_household.py"),
        ])),
        ("categories", categories),
        ("ages", list(range(AGE_LO, AGE_HI + 1))),
        ("absolute", abs_by_cat),
        ("share", share_by_cat),
        ("total", totals),
        ("stages", STAGE_META),
        ("annotations", [
            {"age": 22, "type": "stage", "title": "起点：单身户",
             "text": "户均 1 人，家庭口径 = 人均口径。"},
            {"age": 30, "type": "stage", "title": "进入育儿期",
             "text": "家庭从 2 人变 3 人；子女 0 岁，户均支出跳升约 50%。"},
            {"age": 33, "type": "example", "title": "典型三口之家",
             "text": "户主 33 + 配偶 31 + 子女 3；户均约 16.5 万元/年。"},
            {"age": peak["age"], "type": "peak",
             "title": f"户均峰值：户主 {peak['age']} 岁（子女 {peak['age'] - 30} 岁）",
             "text": f"户均 {peak['total'] / 10000:.1f} 万元/年；0–4 岁育儿支出最贵，叠加户主住房成本高峰，"
                     "略高于 47 岁（子女 17 岁）的次峰。"},
            {"age": 47, "type": "note", "title": "次峰：子女 17 岁",
             "text": "高中阶段教育支出高，但低于子女 4 岁时的托育/用品支出；两峰相差不到 1%。"},
            {"age": 52, "type": "note", "title": "口径张力",
             "text": "子女已 22 岁；模型仍按「有孩期」计入，53 岁起转为空巢。"},
            {"age": 53, "type": "stage", "title": "空巢断点",
             "text": "子女离户，户均支出下降约四分之一。"},
            {"age": 70, "type": "stage", "title": "老年户 1.4 人",
             "text": "含丧偶期望；户均支出低于空巢，但医疗占比升高。"},
        ]),
        ("sources", sources),
        ("scenarios", scen),
    ])
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    print(f"written {out_csv}")
    print(f"written {out_size}")
    print(f"written {out_json}")
    print(f"rows={len(rows)}  anchor={anchor:,.2f}  weighted={weighted:,.2f}  dev={dev_pct:+.3f}%")
    print(f"constructed size={cons_size:.4f}  census size={ANCHOR_HH_SIZE:.4f}")
    print(f"peak={peak['age']} {peak['total']:,.1f}  trough={trough['age']} {trough['total']:,.1f}")
    print(f"hh33={checks['hh33_total']:,.1f}  pc33={checks['pc33_total']:,.1f}  ratio={checks['hh33_over_pc33']}")
    print("checks:", json.dumps(checks, ensure_ascii=False))


if __name__ == "__main__":
    main()
