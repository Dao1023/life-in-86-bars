#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_lifecycle.py — 上海 0–85 岁逐岁消费结构（2024 价）

确定性、无随机数、无网络。输入仅限 data/ 下的已核实文件：
  data/china_age_consumption.csv   上海 2024 城镇八大类金额（A 级官方）
  data/china_age_bands_wide_s1.csv 倪红福等 2014 表2（CHIPS 2007，户主年龄，占比）
  data/us_singleyear.csv           BLS CE 2023 微观逐岁（per consumer unit）
  data/intl_age_consumption.csv    日本 2024 家計調査 年龄阶级别
  data/shanghai_pop_age.csv        2025 常住单岁人口（默认人口权重；P1 构造权重为 fallback）

输出：
  data/shanghai_lifecycle.csv
  data/shanghai_lifecycle.json
  data/shanghai_lifecycle_scenarios.csv

方法：三段拼接 + 两段固定 + 成人段 IPF(RAS) 标定到 2024 上海官方八大类金额。
详见 notes/model-spec.md。
"""

import csv
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

AGE_MIN, AGE_MAX = 0, 85
AGES = np.arange(AGE_MIN, AGE_MAX + 1)

CATS = ["food", "clothing", "housing", "durables",
        "transport", "education", "health", "other"]

CAT_LABEL = {
    "food": "食品烟酒", "clothing": "衣着", "housing": "居住",
    "durables": "生活用品及服务", "transport": "交通和通信",
    "education": "教育文化娱乐", "health": "医疗保健",
    "other": "其他用品和服务",
}

# ── A 级锚点：上海 2024 城镇居民人均消费支出（中国统计年鉴 2025 表 6-27 上海行，
#    与上海统计年鉴 2025 表 9.14 逐项一致） ────────────────────────────────
TARGET = {
    "food": 13877.0, "clothing": 2011.0, "housing": 18932.0,
    "durables": 2258.0, "transport": 5746.0, "education": 5733.0,
    "health": 4570.0, "other": 1853.0,
}
TOTAL_ANCHOR = 54980.0
assert abs(sum(TARGET.values()) - TOTAL_ANCHOR) < 1.0

# ── 0–17：育娲《中国生育成本报告 2022》分龄养育成本（2019 年全国价，元/孩/年）
#    来源：research/A2-china.md §4（原文已读）。
#    0-2 = 当年全国居民人均消费支出；3-5 = +幼儿园 12,000；6-14 = +教育 2,513；
#    15-17 = +住校 2,000；18-21(大学) = 学费 10,000 + 住宿 1,500 + 生活费 24,000。
YUHUA = {"0-2": 21559.0, "3-5": 33559.0, "6-14": 24072.0,
         "15-17": 26072.0, "18-21": 35500.0}

# 上海/全国倍数：育娲 2026 版给出上海 4,751 元/月（0–18 岁均值）、城镇 3,127 元/月、
# 全国 58.0 万元。以「0–17 岁 18 年均值」为约束反解倍数，同时吸收 2019→2024 价格。
SH_MONTHLY = 4751.0

# 4 个年龄段的八大类结构（育娲 2026 版：0-2 饮食/居住/医疗各约 25%；
# 3 岁以上饮食约 25%、居住约 20%，教育 3-14 约 25%、15-17 约 35%。
# 余量按上海 2024 全年龄结构的相对比例分摊 → 见 child_shares()）。
CHILD_BANDS = [(0, 2, "0-2"), (3, 5, "3-5"), (6, 14, "6-14"), (15, 17, "15-17")]

# ── 18–22：上海公办本科在校生成本（构造，见 model-spec §4.3） ──────────────
UNI_TOTAL = 43500.0
UNI_SHARES = {  # 学费5,500 + 住宿1,200 + 生活费30,000 + 书本交通5,000 + 在家居住折算1,800
    "food": 0.333, "clothing": 0.069, "housing": 0.069, "durables": 0.057,
    "transport": 0.064, "education": 0.271, "health": 0.032, "other": 0.105,
}

# ── 老年段（85 岁）目标结构：石贝贝 2017（CHARLS 2013 城镇 60+）
#    food 45.1 / clothing 3.3 / housing 10.3 / durables 8.5 / transport 9.4 /
#    education 6.2 / health 17.2，按 2024 上海口径把居住上调、交通下调、其他恢复正常。
OLD85 = {"food": 0.395, "clothing": 0.045, "housing": 0.200, "durables": 0.050,
         "transport": 0.045, "education": 0.030, "health": 0.205, "other": 0.030}

# ── 居住年龄乘数（相对形状，IPF 会归一化到官方总额） ──────────────────────
# 依据：央行 2019 城镇家庭资产负债调查（26–35 岁负债参与率 73.1%，全国最高；
# 有负债家庭 76.8% 有房贷）。房贷利息进「居住」，首付不进当期消费。
HOUSING_MULT = {"peak_age": 33.0, "peak_add": 0.30, "width": 13.0,
                "decline_at_65": 0.10, "old_rise": 0.06}

# ── 中国老年段水平折减（假设 A5） ────────────────────────────────────────
OLD_DAMP = {"start": 58.0, "end": 85.0, "factor_at_end": 0.72}


# ══════════════════════════════════════════════════════════════════════════
# 工具
# ══════════════════════════════════════════════════════════════════════════
def smooth1d(x, sigma):
    """高斯平滑（边缘复制），sigma 单位为岁。"""
    if sigma <= 0:
        return np.asarray(x, dtype=float).copy()
    r = max(1, int(math.ceil(3 * sigma)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    xp = np.pad(np.asarray(x, float), r, mode="edge")
    return np.convolve(xp, k, mode="valid")


def smooth2d(X, sigma):
    return np.column_stack([smooth1d(X[:, j], sigma) for j in range(X.shape[1])])


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def interp_by_knots(x, knots_x, knots_y):
    return np.interp(x, knots_x, knots_y)


# ══════════════════════════════════════════════════════════════════════════
# 1. 人口权重 fallback（假设 P1：模型构造，非观测表）
#    仅在 --constructed-pop / POP_WEIGHTS=constructed 时启用；默认走 1b 的 2025 实测口径。
#    校准目标：0–14 = 9.4%、60+ = 25.0%（2020 七普 9.8% / 23.4%，按老龄化速度外推），
#    由 child_base 与 old_tau 两个参数二分求解，使两个分档占比同时命中。
# ══════════════════════════════════════════════════════════════════════════
POP_TARGET = {"0-14": 0.094, "60+": 0.250}
POP_FIXED = {"mig_peak": 31.0, "mig_sd": 9.5, "boom_age": 58.0, "boom_sd": 4.6,
             "echo_age": 36.0, "echo_sd": 3.2, "old_start": 68.0}


def population_weights(child_base=0.62, old_tau=11.5):
    a = AGES.astype(float)
    child = np.where(a <= 17, child_base + (1.0 - child_base) * a / 17.0, 1.0)
    mig = 0.95 + 0.55 * np.exp(-0.5 * ((a - POP_FIXED["mig_peak"]) / POP_FIXED["mig_sd"]) ** 2)
    boom = (1.0
            + 0.30 * np.exp(-0.5 * ((a - POP_FIXED["boom_age"]) / POP_FIXED["boom_sd"]) ** 2)
            + 0.16 * np.exp(-0.5 * ((a - POP_FIXED["echo_age"]) / POP_FIXED["echo_sd"]) ** 2))
    old = np.where(a >= POP_FIXED["old_start"],
                   np.exp(-(a - POP_FIXED["old_start"]) / old_tau), 1.0)
    w = child * mig * boom * old
    return w / w.sum()


def _share(w, lo, hi):
    return float(w[lo:hi + 1].sum())


def calibrate_population():
    """嵌套二分：外层 child_base 命中 0–14，内层 old_tau 命中 60+。"""
    cb_lo, cb_hi = 0.15, 1.00
    for _ in range(60):
        cb = 0.5 * (cb_lo + cb_hi)
        # 内层：给定 cb，解 old_tau 使 60+ 命中
        t_lo, t_hi = 4.0, 40.0
        for _ in range(60):
            tau = 0.5 * (t_lo + t_hi)
            if _share(population_weights(cb, tau), 60, 85) < POP_TARGET["60+"]:
                t_lo = tau          # 需要更慢的衰减 → 更大 tau
            else:
                t_hi = tau
        tau = 0.5 * (t_lo + t_hi)
        if _share(population_weights(cb, tau), 0, 14) > POP_TARGET["0-14"]:
            cb_hi = cb              # 少儿太多 → 降低 baseline
        else:
            cb_lo = cb
    cb = 0.5 * (cb_lo + cb_hi)
    return cb, tau


# ══════════════════════════════════════════════════════════════════════════
# 1b. 真实人口权重（默认，见 notes/pop-source.md 与 model-spec §4）
#     data/shanghai_pop_age.csv：2025-11-01 上海常住分年龄人口（单岁 0–100，
#     由七普单岁 + 5 年存活率队列推移 + 2025 年 1% 抽样调查四段控制数配平）。
#     86 岁以上并入 85 岁档，归一化到 0–85（模型序列终点）。
#     默认走本路径；`--constructed-pop`（或 POP_WEIGHTS=constructed）切回上面的 P1。
#     换权重后 23–85 岁水平整体 -1.305%，0–22 岁与 headline 54,980 不变。
# ══════════════════════════════════════════════════════════════════════════
POP_CSV = "shanghai_pop_age.csv"


def load_pop_weights():
    """从 data/shanghai_pop_age.csv 读单岁人口，返回 (0–85 权重向量, 元信息)。"""
    with open(DATA / POP_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    p = {int(r["age"]): float(r["population"]) for r in rows}
    v = np.array([p.get(int(a), 0.0) for a in AGES], dtype=float)
    v[-1] += sum(p.get(a, 0.0) for a in range(86, 101))
    return v / v.sum(), {"source": POP_CSV, "total": float(sum(p.values())),
                         "year": int(rows[0]["year"]), "n_ages": len(rows)}


def get_pop_weights():
    """返回 (w, pop_params)：默认 2025 实测权重；构造 P1 为显式 fallback。

    默认：无参数 / POP_WEIGHTS=real / --real-pop。
    fallback：--constructed-pop / POP_WEIGHTS=constructed（审计旧口径，可复现）。
    """
    mode = os.environ.get("POP_WEIGHTS", "").strip().lower()
    if mode == "constructed" or "--constructed-pop" in sys.argv:
        cb, tau = calibrate_population()
        return population_weights(cb, tau), {"child_base": cb, "old_tau": tau}
    return load_pop_weights()


# ══════════════════════════════════════════════════════════════════════════
# 2. 0–17 岁：育娲分龄成本 × 上海倍数
# ══════════════════════════════════════════════════════════════════════════
def yuhua_scale(kindergarten_addon=12000.0):
    """反解上海倍数：使 0–17 岁 18 年均值 = 4,751 元/月。

    kindergarten_addon 是 3–5 岁段内已含的幼儿园/学前加项（育娲口径 12,000）。
    敏感性变体只改这一项，仍以 18 年均值 57,012 反解 k，故与 base 同标定。
    """
    vals = []
    for a, b, key in CHILD_BANDS:
        v = YUHUA[key]
        if key == "3-5":
            # 育娲 3–5 = 0–2 人均消费 + 幼儿园加项；不是额外再加一次。
            v = YUHUA["0-2"] + float(kindergarten_addon)
        vals.extend([v] * (b - a + 1))
    vals = np.asarray(vals, dtype=float)
    base_avg = vals.mean()
    target_avg = SH_MONTHLY * 12.0
    return target_avg / base_avg, vals, target_avg


def child_profile(kindergarten_addon=12000.0):
    k, vals, target_avg = yuhua_scale(kindergarten_addon)
    level = vals * k                     # 0..17
    level = smooth1d(level, 1.10)        # 抹平段间台阶（保留 3–5 岁学前峰）
    level *= target_avg / level.mean()   # 平滑后仍锁定 18 年均值

    # 结构：表格见 model-spec §4.2
    share = np.zeros((18, 8))
    tbl = {
        "0-2":   {"food": .25, "housing": .25, "health": .25, "education": .02,
                  "clothing": .08, "durables": .06, "transport": .05, "other": .04},
        "3-5":   {"food": .25, "housing": .20, "education": .25, "health": .07,
                  "clothing": .08, "durables": .06, "transport": .05, "other": .04},
        "6-14":  {"food": .25, "housing": .20, "education": .25, "health": .07,
                  "clothing": .06, "durables": .05, "transport": .07, "other": .05},
        "15-17": {"food": .25, "housing": .20, "education": .35, "health": .05,
                  "clothing": .04, "durables": .03, "transport": .05, "other": .03},
    }
    for i, (lo, hi, key) in enumerate(CHILD_BANDS):
        for j, c in enumerate(CATS):
            share[lo:hi + 1, j] = tbl[key][c]
    share = smooth2d(share, 0.9)
    share /= share.sum(1, keepdims=True)
    return level, share


# ══════════════════════════════════════════════════════════════════════════
# 3. 18–22 岁：大学阶段
# ══════════════════════════════════════════════════════════════════════════
def university_profile():
    level = np.full(5, UNI_TOTAL)
    share = np.tile([UNI_SHARES[c] for c in CATS], (5, 1))
    return level, share


# ══════════════════════════════════════════════════════════════════════════
# 4. 成年人（23–85）的水平形状
# ══════════════════════════════════════════════════════════════════════════
def read_us_profile():
    """BLS CE 2023：8 类合计（剔除 personal insurance & pensions）/ 家庭人数。"""
    keep = {"food", "housing", "transport", "healthcare",
            "entertainment", "education", "apparel", "other"}
    per_age = {}
    with open(DATA / "us_singleyear.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            # 文件同时含 per_consumer_unit 与 per_person 两套 measure，只取前者
            if r["measure"] != "per_consumer_unit":
                continue
            if r["category"] not in keep:
                continue
            a = int(r["age"])
            per_age.setdefault(a, {})[r["category"]] = float(r["mean_usd_cal"])
            per_age[a]["_n"] = float(r["cu_size_mean"])
    ages = sorted(per_age)
    tot = np.array([sum(v for k, v in per_age[a].items() if not k.startswith("_"))
                    for a in ages])
    n = np.array([per_age[a]["_n"] for a in ages])
    pp = tot / n
    pp = smooth1d(pp, 1.5)
    return np.array(ages, float), pp / pp.mean()


def read_jp_profile():
    """日本 2024 家計調査：二人以上世帯、世帯主年齢階級別、1 人世帯員当たり。"""
    rows = []
    with open(DATA / "intl_age_consumption.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["country"] == "JP" and r["category_harmonized"] == "TOTAL" \
                    and r["age_band"] != "all":
                rows.append((r["age_band"], float(r["mean_value"]) / float(r["hh_size_people"])))
    mid = {"~29": 25.0, "30-39": 34.5, "40-49": 44.5, "50-59": 54.5,
           "60-69": 64.5, "70+": 73.0}
    rows = [(mid[b], v) for b, v in rows if b in mid]
    rows.sort()
    x = np.array([r[0] for r in rows])
    y = np.array([r[1] for r in rows])
    y = y / y.mean()
    return x, y


def adult_level_shape(a5_factor=0.72):
    """23–85 的水平形状 = 美/日 per-person 曲线中位形态 × 中国老年段折减。

    a5_factor=1.0 关闭 A5 老年折减（敏感性 a5_100）；默认 0.72。
    """
    ua, uy = read_us_profile()
    jx, jy = read_jp_profile()

    ages = np.arange(23, 86).astype(float)
    us = np.interp(ages, ua, uy, left=uy[0], right=np.nan)
    # 80 岁以上 US 尾部样本 n<50，按 82 岁水平每年 -2% 线性外推
    us = np.where(np.isnan(us),
                  uy[-1] * (1 - 0.02 * (ages - ua[-1])), us)

    jp = np.interp(ages, jx, jy, left=jy[0])
    jp = np.where(ages > 73, jy[-1] * (1 - 0.012 * (ages - 73)), jp)

    blend = 0.5 * (us + jp)                      # 两源中位（n=2 → 均值）
    blend /= np.average(blend, weights=None)

    damp = 1.0 - (1.0 - float(a5_factor)) * \
        smoothstep(OLD_DAMP["start"], OLD_DAMP["end"], ages)
    shape = blend * damp
    shape /= shape.mean()
    return ages, us, jp, blend, damp, shape


# ══════════════════════════════════════════════════════════════════════════
# 5. 成年人份额先验：S1 年龄梯度 + 居住重设 + 70+ 外推
# ══════════════════════════════════════════════════════════════════════════
def read_s1():
    bands, mat = [], []
    with open(DATA / "china_age_bands_wide_s1.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            bands.append(r["age_group"])
            mat.append([float(r[CAT_LABEL[c]]) for c in CATS])
    mat = np.array(mat)
    mat /= mat.sum(1, keepdims=True)          # 原表 99.99–100.01，归一
    mid = np.array([float(b.split("-")[0]) + 2.0 for b in bands])
    return mid, mat


def adult_share_prior():
    mid, s1 = read_s1()
    ages = np.arange(23, 86).astype(float)

    share = np.zeros((len(ages), 8))
    for j in range(8):
        share[:, j] = np.interp(ages, mid, s1[:, j])
    # 23–24 用 25–29 段值；67–69 之后先按 65–69 平推，稍后被老年目标覆盖
    share = smooth2d(share, 1.2)
    share /= share.sum(1, keepdims=True)

    # (a) 居住：丢弃 S1 的噪声梯度，改用显式驼峰
    hm = (1.0
          + HOUSING_MULT["peak_add"] * np.exp(-0.5 * ((ages - HOUSING_MULT["peak_age"])
                                                      / HOUSING_MULT["width"]) ** 2)
          - HOUSING_MULT["decline_at_65"] * smoothstep(45, 68, ages)
          + HOUSING_MULT["old_rise"] * smoothstep(72, 85, ages))
    h = 0.344 * hm
    h = h / np.average(h) * 0.344          # 相对形状，绝对水平交给 IPF
    nonh = share[:, [j for j, c in enumerate(CATS) if c != "housing"]]
    nonh = nonh / nonh.sum(1, keepdims=True) * (1 - h)[:, None]
    share[:, [j for j, c in enumerate(CATS) if c != "housing"]] = nonh
    share[:, CATS.index("housing")] = h

    # (b) 70–85：向 OLD85 平滑外推
    t = smoothstep(69.0, 85.0, ages) ** 1.35
    tgt = np.array([OLD85[c] for c in CATS])
    share = (1 - t)[:, None] * share + t[:, None] * tgt[None, :]
    share /= share.sum(1, keepdims=True)
    return ages, share


# ══════════════════════════════════════════════════════════════════════════
# 6. IPF / RAS
# ══════════════════════════════════════════════════════════════════════════
def ipf(X, row_tot, col_tot, w, iters=5000, tol=1e-12):
    """标准 RAS：行、列交替缩放，直到行和与列和同时收敛。

    旧实现只在列约束上判收敛，循环结束后又做一次行缩放，会把刚满足的
    列约束重新破坏（首次调用列相对误差可达 3.4e-3）。这里改为每次
    行列缩放后同时检查两个约束，不再做破坏列约束的尾部行缩放。
    """
    X = X.copy()
    for _ in range(iters):
        X *= (row_tot / X.sum(1))[:, None]
        cur = (X * w[:, None]).sum(0)
        X *= (col_tot / cur)[None, :]
        row_err = np.max(np.abs(X.sum(1) / row_tot - 1.0))
        col_err = np.max(np.abs((X * w[:, None]).sum(0) / col_tot - 1.0))
        if max(row_err, col_err) < tol:
            break
    return X


def build(pop=None, kindergarten_addon=12000.0, a5_factor=0.72):
    """构建一条曲线。pop=(w, params) 可复用；敏感性变体只改加项/A5。"""
    if pop is None:
        pop = get_pop_weights()
    w, pop_params = pop

    # ── 固定段 ─────────────────────────────────────────────────────────
    child_lvl, child_sh = child_profile(kindergarten_addon)
    uni_lvl, uni_sh = university_profile()
    fixed = np.vstack([child_lvl[:, None] * child_sh, uni_lvl[:, None] * uni_sh])

    # ── 成人段 ─────────────────────────────────────────────────────────
    ages, us, jp, blend, damp, shape = adult_level_shape(a5_factor)
    _, prior = adult_share_prior()

    adult_w = w[23:]
    fixed_contrib = (fixed * w[:23, None]).sum(0)
    resid = np.array([TARGET[c] for c in CATS]) - fixed_contrib
    if (resid <= 0).any():
        raise SystemExit(f"残差类别为负：{dict(zip(CATS, resid))}")

    level = shape * (resid.sum() / np.sum(adult_w * shape))

    X = level[:, None] * prior
    X = ipf(X, level, resid, adult_w)

    # 轻度平滑 → 重新 IPF，压掉 5 岁组边界的折角
    for _ in range(3):
        sh = X / X.sum(1, keepdims=True)
        sh = smooth2d(sh, 0.8)
        sh /= sh.sum(1, keepdims=True)
        X = ipf(sh * X.sum(1, keepdims=True), X.sum(1), resid, adult_w)

    full = np.vstack([fixed, X])
    row_targets = np.concatenate([child_lvl, uni_lvl, level])
    return full, w, dict(us=us, jp=jp, blend=blend, damp=damp, shape=shape,
                         level=level, prior=prior, resid=resid, ages=ages,
                         row_targets=row_targets,
                         pop_params=pop_params)


# ══════════════════════════════════════════════════════════════════════════
# 7. 校验 + 输出
# ══════════════════════════════════════════════════════════════════════════
STAGES = [
    (0, 2, "婴幼儿", "0-17 家庭代付"),
    (3, 5, "学前", "0-17 家庭代付"),
    (6, 11, "小学", "0-17 家庭代付"),
    (12, 14, "初中", "0-17 家庭代付"),
    (15, 17, "高中", "0-17 家庭代付"),
    (18, 22, "大学", "18-22 大学"),
    (23, 29, "初入职场", "23-69 标定"),
    (30, 39, "成家育儿", "23-69 标定"),
    (40, 49, "中年", "23-69 标定"),
    (50, 59, "空巢前", "23-69 标定"),
    (60, 69, "退休过渡", "23-69 标定"),
    (70, 79, "高龄", "70-85 外推"),
    (80, 85, "耄耋", "70-85 外推"),
]
BASIS = {0: "估算-B 育娲分龄成本×上海倍数（家庭代付）",
         18: "估算-C 上海公办本科成本构造",
         23: "估算-B S1(2007)形状 × IPF 标定(2024上海)",
         70: "外推-C S1末段+CHARLS60+ + 美日校准"}


def stage_of(a):
    for lo, hi, name, _ in STAGES:
        if lo <= a <= hi:
            return name
    raise ValueError(a)


def checks(full, w, row_targets):
    out = {}
    tot = full.sum(1)
    # 旧实现把 full.sum(1) 与它自己比较，row_err_max 恒为 0；这里对真实的
    # 分段行目标（育儿成本 / 大学 43,500 / 成人 level）计算相对误差。
    row_err = np.abs(full.sum(1) - row_targets) / np.maximum(row_targets, 1.0)
    out["row_err_max"] = float(row_err.max())
    out["row_err_argmax"] = int(row_err.argmax())
    out["weighted_total"] = float((w * tot).sum())
    out["weighted_total_err_pct"] = float((out["weighted_total"] / TOTAL_ANCHOR - 1) * 100)
    out["cat"] = {}
    for j, c in enumerate(CATS):
        v = float((w * full[:, j]).sum())
        out["cat"][c] = {"model": v, "target": TARGET[c],
                         "err_pct": (v / TARGET[c] - 1) * 100}
    d = np.abs(np.diff(tot)) / tot[:-1] * 100
    # 阶段边界：允许台阶（育儿成本→学费、学生→就业），其余年份不得 >15%
    boundaries = {hi for _, hi, _, _ in STAGES[:-1]}
    jumps = [(int(i), float(v)) for i, v in enumerate(d) if v > 15.0]
    out["jumps"] = jumps
    out["jumps_at_boundary"] = [(i, round(v, 1)) for i, v in jumps if i in boundaries]
    out["jumps_unexplained"] = [(i, round(v, 1)) for i, v in jumps if i not in boundaries]
    out["jump_max"] = float(d.max())
    out["jump_max_age"] = int(np.argmax(d))
    out["negative"] = int((full < 0).sum())
    out["peak_age"] = int(np.argmax(tot))
    out["peak"] = float(tot.max())
    out["trough_age"] = int(np.argmin(tot[1:]) + 1)
    out["trough"] = float(tot.min())
    out["peak_to_trough"] = out["peak"] / out["trough"]
    adult_tot = tot[23:]
    out["adult_peak_age"] = int(np.argmax(adult_tot) + 23)
    out["adult_peak"] = float(adult_tot.max())
    out["total"] = tot
    return out


def _variant_payload(full, w, chk, label, kindergarten_addon, a5_factor):
    """敏感性变体的统一输出结构（仍锁 54,980）。"""
    tot = full.sum(1)
    return {
        "label": label,
        "kindergarten_addon": float(kindergarten_addon),
        "a5_factor": float(a5_factor),
        "total": [round(float(v), 1) for v in tot],
        "absolute": {c: [round(float(full[a, j]), 1) for a in AGES]
                     for j, c in enumerate(CATS)},
        "weighted_mean": round(float((w * tot).sum()), 1),
        "peak_age": chk["peak_age"],
        "peak_value": round(chk["peak"], 1),
        "adult_peak_age": chk["adult_peak_age"],
        "adult_peak_value": round(chk["adult_peak"], 1),
    }


def build_sensitivity(pop, fallback_pop=None):
    """幼儿园加项与 A5 两组敏感性；均用同一人口权重、同一 54,980 标定。"""
    kg = {}
    for key, addon, label in [
        ("private_12000", 12000.0, "现行 base：幼儿园 12,000 元/年"),
        ("public_5000", 5000.0, "公办口径：幼儿园 5,000 元/年"),
    ]:
        full, w, dbg = build(pop=pop, kindergarten_addon=addon, a5_factor=0.72)
        chk = checks(full, w, dbg["row_targets"])
        kg[key] = _variant_payload(full, w, chk, label, addon, 0.72)

    a5 = {}
    for key, factor, label in [
        ("a5_072", 0.72, "A5=0.72：现行老年段折减"),
        ("a5_100", 1.00, "A5=1.00：不做老年段折减"),
    ]:
        full, w, dbg = build(pop=pop, kindergarten_addon=12000.0, a5_factor=factor)
        chk = checks(full, w, dbg["row_targets"])
        a5[key] = _variant_payload(full, w, chk, label, 12000.0, factor)

    summary = {
        "kindergarten_12000_peak_age": kg["private_12000"]["peak_age"],
        "kindergarten_5000_peak_age": kg["public_5000"]["peak_age"],
        "a5_removed_85yo": a5["a5_100"]["total"][85],
        "a5_removed_global_peak_age": a5["a5_100"]["peak_age"],
        "conclusion": "4 岁最贵仅在 12,000 元/年幼儿园假设下成立",
    }
    if fallback_pop is not None:
        f, _, _ = build(pop=fallback_pop, kindergarten_addon=12000.0, a5_factor=1.0)
        summary["a5_removed_85yo_constructed_reference"] = round(float(f.sum(1)[85]), 1)
    return {"kindergarten": kg, "a5": a5, "summary": summary}


def main():
    pop = get_pop_weights()
    full, w, dbg = build(pop=pop)
    chk = checks(full, w, dbg["row_targets"])
    chk["pop_params"] = dbg["pop_params"]
    tot = full.sum(1)

    # ── CSV ───────────────────────────────────────────────────────────
    csv_path = DATA / "shanghai_lifecycle.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["age", "stage", "segment"] + [f"cat_{c}" for c in CATS] +
                    ["total"] + [f"share_{c}" for c in CATS] + ["basis", "note"])
        for a in AGES:
            seg = ("0-17 家庭代付" if a <= 17 else "18-22 大学" if a <= 22
                   else "23-69 标定" if a <= 69 else "70-85 外推")
            b = BASIS[0] if a <= 17 else BASIS[18] if a <= 22 else BASIS[23] if a <= 69 else BASIS[70]
            note = ""
            if a == 0:
                note = "出生；按家庭代付口径计入育儿成本，非个人独立消费"
            elif a == 3:
                note = "学前教育加项（育娲口径每年 12,000 元幼儿园）"
            elif a == 15:
                note = "高中：教育占育儿成本约 35%，为 0-17 段最高"
            elif a == 18:
                note = "台阶：家庭代付→学费+住宿+生活费，总投入下降"
            elif a == 23:
                note = "就业；进入 S1 年龄梯度标定段"
            elif a == 30:
                note = "房贷利息/租金高峰；首付不计入当期消费"
            elif a == 45:
                note = "S1 教育文娱占比峰值（2007 户主 45-49 岁 17.3%）"
            elif a == 60:
                note = "退休；医疗占比加速上行"
            elif a == 70:
                note = "S1 止于 69 岁，此后为 CHARLS+美日校准外推"
            elif a == 85:
                note = "序列终点"
            wr.writerow([a, stage_of(a), seg] + [round(float(full[a, j]), 1) for j in range(8)] +
                        [round(float(tot[a]), 1)] +
                        [round(float(full[a, j] / tot[a]), 4) for j in range(8)] +
                        [b, note])

    # ── scenarios ─────────────────────────────────────────────────────
    scen_def = {
        "low":  {"edu": 0.8, "housing": 0.8, "health": 0.8},
        "base": {"edu": 1.0, "housing": 1.0, "health": 1.0},
        "high": {"edu": 1.4, "housing": 1.2, "health": 1.3},
    }
    scen_path = DATA / "shanghai_lifecycle_scenarios.csv"
    scen_store = {}
    with open(scen_path, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["scenario", "age"] + [f"cat_{c}" for c in CATS] + ["total"])
        for name, p in scen_def.items():
            X = full.copy()
            X[:, CATS.index("education")] *= p["edu"]
            X[25:46, CATS.index("housing")] *= p["housing"]
            X[60:, CATS.index("health")] *= p["health"]
            scen_store[name] = X
            for a in AGES:
                wr.writerow([name, a] + [round(float(X[a, j]), 1) for j in range(8)] +
                            [round(float(X[a].sum()), 1)])

    # ── 敏感性数据集（页面用；仍锁 54,980）─────────────────────────────
    cb_fb, tau_fb = calibrate_population()
    fallback_pop = (population_weights(cb_fb, tau_fb),
                    {"child_base": cb_fb, "old_tau": tau_fb})
    sens = build_sensitivity(pop, fallback_pop)
    (DATA / "sensitivity_kindergarten.json").write_text(
        json.dumps(sens["kindergarten"], ensure_ascii=False, indent=1), encoding="utf-8")
    (DATA / "sensitivity_a5.json").write_text(
        json.dumps(sens["a5"], ensure_ascii=False, indent=1), encoding="utf-8")

    # ── JSON ──────────────────────────────────────────────────────────
    meta_extra = {
        "edu_multiplier": {k: v["edu"] for k, v in scen_def.items()},
        "housing_multiplier_25_45": {k: v["housing"] for k, v in scen_def.items()},
        "health_multiplier_60plus": {k: v["health"] for k, v in scen_def.items()},
    }
    doc = build_json(full, w, chk, dbg, scen_store, meta_extra, sens)
    (DATA / "shanghai_lifecycle.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── 控制台报告 ────────────────────────────────────────────────────
    print("=" * 78)
    print("上海 0–85 岁消费结构 — 构建完成")
    print("=" * 78)
    print(f"育娲倍数 k = {yuhua_scale()[0]:.4f}")
    print(f"0–17 均值 = {yuhua_scale()[2]:.0f} 元/年/孩")
    pp = dbg["pop_params"]
    if "child_base" in pp:
        print(f"人口权重参数（二分求解）：child_base={pp['child_base']:.4f}  old_tau={pp['old_tau']:.3f}")
    else:
        print(f"人口权重：实测单岁表 {pp['source']}（{pp['year']} 年，{pp['total']:,.0f} 人）")
    print(f"人口权重分档：0-14 {w[:15].sum()*100:.2f}%  15-59 {w[15:60].sum()*100:.2f}%  "
          f"60+ {w[60:].sum()*100:.2f}%  65+ {w[65:].sum()*100:.2f}%")
    print(f"\n成人水平形状（归一化，均值=1）：")
    for a in [23, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85]:
        print(f"  {a:2d}: US {np.interp(a, dbg['ages'], dbg['us']):.3f}  "
              f"JP {np.interp(a, dbg['ages'], dbg['jp']):.3f}  "
              f"blend {np.interp(a, dbg['ages'], dbg['blend']):.3f}  "
              f"damp {np.interp(a, dbg['ages'], dbg['damp']):.3f}  "
              f"final {np.interp(a, dbg['ages'], dbg['shape']):.3f}")
    print(f"\n行和误差 max = {chk['row_err_max']:.2e}")
    print(f"人口加权总额 = {chk['weighted_total']:.2f}（目标 {TOTAL_ANCHOR:.0f}，"
          f"偏差 {chk['weighted_total_err_pct']:+.4f}%）")
    print("\n分类校验：")
    for c in CATS:
        d = chk["cat"][c]
        print(f"  {CAT_LABEL[c]:8s} 模型 {d['model']:9.1f}  目标 {d['target']:9.0f}  偏差 {d['err_pct']:+.4f}%")
    print(f"\n峰值：{chk['peak_age']} 岁，{chk['peak']:.0f} 元；谷值：{chk['trough_age']} 岁，"
          f"{chk['trough']:.0f} 元；峰谷比 {chk['peak_to_trough']:.2f}")
    print(f"成年段峰：{chk['adult_peak_age']} 岁，{chk['adult_peak']:.0f} 元")
    print(f"最大相邻变化 {chk['jump_max']:.1f}% @ {chk['jump_max_age']}→{chk['jump_max_age']+1}")
    print(f"  >15% 且位于阶段边界（允许）：{chk['jumps_at_boundary']}")
    print(f"  >15% 且不在阶段边界（应为空）：{chk['jumps_unexplained']}")
    print(f"负值单元格：{chk['negative']}")
    print("\n分段均值：")
    for lo, hi, name, _ in STAGES:
        print(f"  {name:6s} {lo:2d}-{hi:2d}: {tot[lo:hi+1].mean():8.0f} 元/年")
    print("\n年龄段结构（%）:")
    for a in [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85]:
        s = full[a] / tot[a] * 100
        print(f"  {a:2d} " + " ".join(f"{v:4.1f}" for v in s) + f" | {tot[a]:7.0f}")
    print("\n情景：")
    for name in ["low", "base", "high"]:
        X = scen_store[name]
        t = X.sum(1)
        print(f"  {name:4s} 峰 {int(np.argmax(t))} 岁 {t.max():.0f}；"
              f"人口加权均值 {(w*t).sum():.0f}；0 岁 {t[0]:.0f}；85 岁 {t[85]:.0f}")
    print("\n敏感性（均锁 54,980）：")
    for key, v in sens["kindergarten"].items():
        print(f"  {key:14s} 幼儿园 {v['kindergarten_addon']:>6.0f}  "
              f"峰 {v['peak_age']} 岁 {v['peak_value']:.0f}；"
              f"成年峰 {v['adult_peak_age']} 岁 {v['adult_peak_value']:.0f}")
    for key, v in sens["a5"].items():
        print(f"  {key:14s} A5 {v['a5_factor']:.2f}  "
              f"峰 {v['peak_age']} 岁 {v['peak_value']:.0f}；85 岁 {v['total'][85]:.0f}")
    print(f"\n0–17 加权贡献 = {(w[:18] * tot[:18]).sum():.1f} 元/人/年  "
          f"（{(w[:18] * tot[:18]).sum() / chk['weighted_total'] * 100:.2f}% of 54,980）")
    print("\n输出：" + ", ".join(str(DATA / ("shanghai_lifecycle" + s))
                                 for s in [".csv", ".json", "_scenarios.csv"]))


def dbg_pop_source(chk):
    """人口权重的来源描述（构造 / 实测）。"""
    pp = chk.get("pop_params", {})
    if "child_base" in pp:
        return "假设 P1：模型构造（无官方单岁表）"
    return f"实测：data/{pp.get('source', '')}（{pp.get('year', '')} 年，单岁）"


def build_json(full, w, chk, dbg, scen_store, extra, sensitivity=None):
    tot = chk["total"]
    ages = [int(a) for a in AGES]

    active_shares = {
        "0-14": round(float(w[:15].sum()), 4),
        "15-59": round(float(w[15:60].sum()), 4),
        "60+": round(float(w[60:].sum()), 4),
        "65+": round(float(w[65:].sum()), 4),
    }
    # fallback P1 的两套分档始终保留在 meta 里，页面可对照。
    cb_fb, tau_fb = calibrate_population()
    w_fb = population_weights(cb_fb, tau_fb)
    fallback_shares = {
        "0-14": round(float(w_fb[:15].sum()), 4),
        "15-59": round(float(w_fb[15:60].sum()), 4),
        "60+": round(float(w_fb[60:].sum()), 4),
        "65+": round(float(w_fb[65:].sum()), 4),
    }
    child_weighted_share = round(
        float((w[:18] * tot[:18]).sum() / chk["weighted_total"] * 100), 2)
    child_weighted_share_constructed = round(
        float((w_fb[:18] * tot[:18]).sum() / chk["weighted_total"] * 100), 2)
    active_params = chk.get("pop_params", {})
    stages = []
    palette = {"婴幼儿": "#E8C4B8", "学前": "#E3B7A5", "小学": "#D9A88F", "初中": "#CE9A7C",
               "高中": "#C08A6A", "大学": "#9B8EA8", "初入职场": "#8FA9B8",
               "成家育儿": "#6F9AA8", "中年": "#5B8797", "空巢前": "#4C7484",
               "退休过渡": "#7E8F7A", "高龄": "#93A18B", "耄耋": "#A8B39C"}
    for lo, hi, name, seg in STAGES:
        stages.append({"id": f"s{lo}", "label": name, "start": lo, "end": hi,
                       "segment": seg, "color": palette[name]})

    annotations = [
        {"age": 0, "type": "stage", "title": "出生", "text": "0–17 岁按「家庭代付」口径：这条柱子是家庭为一个孩子一年的支出，不是孩子自己的收入。"},
        {"age": 3, "type": "peak", "title": "学前教育加项", "text": "育娲口径每年加 12,000 元幼儿园费用；上海若读民办园，这一段还要高 30–60%。"},
        {"age": 15, "type": "peak", "title": "高中：教育占比最高", "text": "教育约占育儿成本 35%，是 0–17 岁的最高点；18 岁后家庭总投入反而下降。"},
        {"age": 18, "type": "step", "title": "口径切换", "text": "从「家庭代付」切换为「学费+住宿+生活费」，柱子出现台阶式下降。"},
        {"age": 30, "type": "peak", "title": "房贷利息高峰", "text": "央行 2019 调查：26–35 岁家庭负债参与率 73.1%，全国最高。首付是资产交易，不计入当期消费；只有利息和租金进「居住」。"},
        {"age": 35, "type": "note", "title": "家庭规模最大的年份", "text": "30–40 岁人均消费反而略低于 25 岁：家里人多、分母大。这正是用「人均」口径（家庭消费÷家庭人数，与 NBS 定义一致）的结果。"},
        {"age": 45, "type": "peak", "title": "教育文娱占比峰值", "text": "S1（CHIPS 2007）中 45–49 岁户主的教育文娱占比 17.3%，为全年龄最高。"},
        {"age": 60, "type": "note", "title": "退休", "text": "医疗占比自 55 岁起加速上行；60 岁后收入端换轨，消费水平随年龄缓降。"},
        {"age": 70, "type": "note", "title": "外推段起点", "text": "S1 只到 69 岁；70 岁后用 CHARLS 60+ 结构 + 美日年龄曲线校准。"},
    ]

    sources = [
        {"id": "NBS-YB2025-T6-27-SH", "level": "A",
         "label": "中国统计年鉴 2025 表 6-27 上海行（2024 城镇八大类，元/人/年）",
         "url": "https://www.stats.gov.cn/sj/ndsj/2025/html/C06-27.jpg",
         "use": "总量与八大类金额锚点（54,980）"},
        {"id": "SH-TJNJ2025-T9.14", "level": "A",
         "label": "上海统计年鉴 2025 表 9.14 城镇常住居民人均消费支出及构成（2021–2024）",
         "url": "https://tjj.sh.gov.cn/tjnj/2025tjnj/C0914.htm",
         "use": "与表 6-27 交叉核对，逐项一致"},
        {"id": "S1", "level": "B",
         "label": "倪红福、李善同、何建武 (2014)，人口与发展 20(5):25-34，表2（第28页）",
         "url": "https://ccj.pku.edu.cn/Article/DownLoad?id=331122480&type=ArticleFile",
         "use": "23–69 岁八大类占比的年龄梯度（CHIPS 2007 城镇，n≈4,904，户主年龄）"},
        {"id": "S2", "level": "B",
         "label": "石贝贝 (2017)，人口研究 41(3):53-64，表3（第58页）",
         "url": "https://rkyj.ruc.edu.cn/EN/article/downloadArticleFile.do?attachType=PDF&id=3469",
         "use": "60+ 老年段结构锚点（CHARLS 2013 城镇）"},
        {"id": "YUHUA-2022", "level": "B",
         "label": "育娲人口《中国生育成本报告 2022 版》（199IT 全文转载，含分年龄段方法）",
         "url": "https://www.199it.com/archives/1392623.html",
         "use": "0–17 分龄育儿成本、大学成本"},
        {"id": "YUHUA-2026", "level": "B",
         "label": "育娲人口《中国生育成本报告 2026 版》（新浪财经转载）",
         "url": "https://cj.sina.com.cn/articles/view/1704103183/65928d0f0200aos0k",
         "use": "上海 4,751 元/月、教育占比 25%/35%、三大项结构"},
        {"id": "BLS-CE-2023", "level": "A",
         "label": "BLS Consumer Expenditure Survey 2023（PUMD 微观，逐岁）",
         "url": "https://www.bls.gov/cex/pumd_data.htm",
         "use": "成人段水平形状（per consumer unit / 家庭人数）"},
        {"id": "JP-KAKEI-2024", "level": "A",
         "label": "日本总务省 家計調査 2024 年報 第3表（世帯主年齢階級別）",
         "url": "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040297516&fileKind=4",
         "use": "成人段水平形状的第二个来源"},
        {"id": "PBoC-2019", "level": "B",
         "label": "中国人民银行城镇居民家庭资产负债调查（2019-10）",
         "url": "https://tech.sina.com.cn/roll/2020-04-25/doc-iircuyvh9753649.shtml",
         "use": "26–35 岁负债参与率 73.1%、房贷占比，用于居住驼峰"},
        {"id": "P1", "level": "C", "label": "上海 2024 常住人口年龄结构（模型构造）",
         "url": "", "use": "人口权重；非官方单岁表，见 model-spec §3"},
    ]

    return {
        "meta": {
            "title": "一个上海人的一生：0–85 岁逐年消费结构",
            "city": "上海", "year": 2024, "currency": "CNY", "unit": "元/人/年",
            "price_base": "2024 年上海价",
            "basis": "模型估算，非官方观测",
            "disclaimer": "上海 2024 官方只发布全年龄八大类；本数据集的年龄形状来自 CHIPS 2007 年龄梯度 + 育娲育儿成本 + 美日年龄曲线，经 IPF 标定到 2024 上海官方总额。任何一格都不是「官方分年龄观测值」。",
            "weighted_mean": round(chk["weighted_total"], 1),
            "anchor_total": TOTAL_ANCHOR,
            "peak_age": chk["peak_age"],
            "peak_value": round(chk["peak"], 1),
            "trough_age": chk["trough_age"],
            "trough_value": round(chk["trough"], 1),
            "peak_to_trough": round(chk["peak_to_trough"], 2),
            "adult_peak_age": chk["adult_peak_age"],
            "adult_peak_value": round(chk["adult_peak"], 1),
            "range_min": round(float(tot.min()), 1),
            "range_max": round(float(tot.max()), 1),
            "calibration": {
                "row_error_max": chk["row_err_max"],
                "weighted_total_error_pct": round(chk["weighted_total_err_pct"], 4),
                "category_error_pct_max": round(
                    max(abs(v["err_pct"]) for v in chk["cat"].values()), 4),
                "max_adjacent_change_pct": round(chk["jump_max"], 2),
                "adjacent_change_over_15pct_at_stage_boundary":
                    [{"from": j, "to": j + 1, "pct": round(v, 1)}
                     for j, v in chk["jumps_at_boundary"]],
                "adjacent_change_over_15pct_elsewhere":
                    [{"from": j, "to": j + 1, "pct": round(v, 1)}
                     for j, v in chk["jumps_unexplained"]],
                "passed": bool(chk["row_err_max"] < 1e-6
                               and abs(chk["weighted_total_err_pct"]) < 1.0
                               and max(abs(v["err_pct"]) for v in chk["cat"].values()) < 2.0
                               and chk["negative"] == 0
                               and not chk["jumps_unexplained"]),
            },
            "population_weights": {
                "active": {
                    "source": (dbg_pop_source(chk)),
                    "band_shares": active_shares,
                    "params": {k: (round(float(v), 4) if isinstance(v, float) else v)
                               for k, v in active_params.items()},
                    "balancing": (
                        "child_base/old_tau 嵌套二分；目标 0–14 9.4%、60+ 25.0%"
                        if "child_base" in active_params else
                        "2025 1% 抽样公报四段控制数 raking；配平系数 "
                        "0-14 1.0012 / 15-59 1.0099 / 60-64 0.9861 / 65+ 0.9973"),
                },
                "fallback_constructed": {
                    "source": "假设 P1：模型构造（无官方单岁表）",
                    "band_shares": fallback_shares,
                    "params": {"child_base": round(float(cb_fb), 4),
                               "old_tau": round(float(tau_fb), 4),
                               "targets": dict(POP_TARGET)},
                    "balancing": "child_base/old_tau 嵌套二分；目标 0–14 9.4%、60+ 25.0%",
                },
                # 兼容旧页面：顶层仍给 active 一套。
                "source": (dbg_pop_source(chk)),
                "band_shares": active_shares,
                "params": {k: (round(float(v), 4) if isinstance(v, float) else v)
                           for k, v in active_params.items()},
            },
            "sensitivity_summary": (sensitivity or {}).get("summary"),
            "zero_to_17_share_of_weighted_total": child_weighted_share,
            "zero_to_17_share_of_weighted_total_constructed_reference":
                child_weighted_share_constructed,
            "calibration_shape_constraint":
                "54,980 只约束水平（整体缩放），不约束年龄形状",
            "scenario_def": extra,
            "generated_by": "build_lifecycle.py",
        },
        "categories": [{"id": c, "label": CAT_LABEL[c],
                        "color": {"food": "#C4553B", "clothing": "#D9A441",
                                  "housing": "#2F5D62", "durables": "#7FA6A0",
                                  "transport": "#4A6FA5", "education": "#8B5E83",
                                  "health": "#A64253", "other": "#B9B3A8"}[c]}
                       for c in CATS],
        "ages": ages,
        "absolute": {c: [round(float(full[a, j]), 1) for a in AGES]
                     for j, c in enumerate(CATS)},
        "share": {c: [round(float(full[a, j] / tot[a]), 4) for a in AGES]
                  for j, c in enumerate(CATS)},
        "total": [round(float(v), 1) for v in tot],
        "stages": stages,
        "annotations": annotations,
        "sources": sources,
        "scenarios": {
            name: {"total": [round(float(v), 1) for v in X.sum(1)],
                   "absolute": {c: [round(float(X[a, j]), 1) for a in AGES]
                                for j, c in enumerate(CATS)},
                   "weighted_mean": round(float((w * X.sum(1)).sum()), 1)}
            for name, X in scen_store.items()
        },
    }


if __name__ == "__main__":
    main()
