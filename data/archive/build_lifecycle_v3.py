#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上海 0–85 岁消费生命周期 —— v2 重建版（2026-11 审计后重写）

与 v1 的区别（详见 notes/REBUILD-LOG.md 与 notes/model-spec.md）：
  1. 0–17 岁不再把育娲总额四等分，改为「分项篮子」自下而上构造；
  2. 18 岁不再出现口径断崖（v1 −25.1% → 本版约 −8%）；
  3. 23–85 岁用「户均消费 × 成人份额调整 φ(a)」得到自身消费，而不是户均÷人数；
  4. 60 岁有可辨识的退休台阶（−10% 量级），不是平台；
  5. 校准改为「行和锁定（水平形状不动）+ 列和锁定（八类官方额）」的 IPF，
     逐带报告缩放率，任何一格超过 ±15% 直接报错。

运行：
    python build_lifecycle.py                 # 默认 2025 实测人口权重
    python build_lifecycle.py --constructed-pop  # 回退到 P1 构造权重
    python build_lifecycle.py --diag          # 打印每带缩放率与验收自检

输出：data/shanghai_lifecycle.csv / .json / _scenarios.csv、
      data/rebuild_diff.csv、data/sensitivity_kindergarten.json、
      data/sensitivity_a5.json、data/sensitivity_longtermcare.json
"""
from __future__ import annotations

import argparse
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
ADULT_LO, ADULT_HI = 23, 85

CATS = ["food", "clothing", "housing", "durables",
        "transport", "education", "health", "other"]
CAT_LABEL = {
    "food": "食品烟酒", "clothing": "衣着", "housing": "居住",
    "durables": "生活用品及服务", "transport": "交通和通信",
    "education": "教育文化娱乐", "health": "医疗保健",
    "other": "其他用品和服务",
}

# ── A 级锚点：上海 2024 城镇居民人均消费支出（中国统计年鉴 2025 表 6-27
#    上海行，与上海统计年鉴 2025 表 9.14 逐项一致） ───────────────────────
TARGET = {
    "food": 13877.0, "clothing": 2011.0, "housing": 18932.0,
    "durables": 2258.0, "transport": 5746.0, "education": 5733.0,
    "health": 4570.0, "other": 1853.0,
}
TOTAL_ANCHOR = 54980.0
assert abs(sum(TARGET.values()) - TOTAL_ANCHOR) < 1.0

# ══════════════════════════════════════════════════════════════════════════
# 1. 0–17 岁：家庭为该孩子「直接支付」的分项篮子（元/年，2024 上海价）
#    每个格子都是可追溯的构造，不再由总额四等分得到。
#    居住 = 仅孩子分摊的水电燃气物业（不含房租、不含房贷本息）。
#    用品 = 婴幼儿耐用品 + 日用杂品（纸尿裤）+ 家庭服务（托育/育儿嫂分摊）。
# ══════════════════════════════════════════════════════════════════════════
CHILD_BANDS = [(0, 2), (3, 5), (6, 11), (12, 14), (15, 17)]
CHILD_BASKET = [
    # food, clothing, housing, durables, transport, education, health, other
    [12500, 1400, 3500, 8000, 1300, 1200, 1300, 3300],   # 0–2  Σ 32,500
    [13400, 1500, 3900, 4200, 2300, 9200, 1400, 2700],   # 3–5  Σ 38,600
    [14800, 1700, 4300, 3000, 3300, 12600, 1500, 2800],  # 6–11 Σ 44,000
    [15500, 1900, 4500, 3100, 3500, 12800, 1600, 2900],  # 12–14 Σ 45,800
    [15300, 2000, 4700, 3200, 3600, 13700, 1750, 2400],  # 15–17 Σ 46,650
]
# 0–2 岁按年摊销的修正（v3）：耐用品是一次性购置，不该在 0/1/2 岁各记一次
# 年流量；医疗（自费疫苗/儿保/门诊）应高于学龄段。0–2 段均值 32,386→31,432。
INFANT_AMORTIZE = {
    0: {"durables": 6500.0, "health": 2200.0},
    1: {"durables": 5800.0, "health": 2200.0},
    2: {"durables": 5200.0, "health": 2200.0},
}
# 0–2 岁托育/早教（v4，D 复核）：v3 把 0–2 岁教育压到 1,200，隐含「三岁前
# 育儿免费」，于是 2→3 变成 +24.9%，成为全表最大跳变。
#   托育：上海 3 岁以下入托率公开口径约 5%–8%，2 岁托班是主体（0 岁几乎
#         不入托，1 岁少量，2 岁最多）；托班月费公办 2,000–3,000、民办
#         5,000–8,000，取混合价 4,000 元/月 × 12 个月 × 入托率。
#   早教：亲子课，按参与率 × 年支出 4,000 元计（不是每个孩子都上）。
# 结果：0/1/2 岁教育 = 840 / 2,680 / 6,480，2→3 涨幅回到 +7% 量级。
INFANT_EDU = {
    0: {"tuoyu_rate": 0.005, "tuoyu_fee": 4000.0,
        "zaojiao_rate": 0.15, "zaojiao_spend": 4000.0},
    1: {"tuoyu_rate": 0.035, "tuoyu_fee": 4000.0,
        "zaojiao_rate": 0.25, "zaojiao_spend": 4000.0},
    2: {"tuoyu_rate": 0.120, "tuoyu_fee": 4000.0,
        "zaojiao_rate": 0.18, "zaojiao_spend": 4000.0},
}

CHILD_BAND_NOTE = [
    "0–2：配方奶/辅食 + 纸尿裤/耐用品 + 托育/早教 + 少儿医保自付",
    "3–5：公办幼儿园 5,000 + 兴趣班，教育首次成为最大单项",
    "6–11：公办小学 + 校外培训，教育占 29%",
    "12–14：初中 + 培训，教育与 6–11 基本持平",
    "15–17：高中 + 补课，教育 13,700 为 0–17 最高",
]

# ── 18–22：上海公办本科在校生成本（独立构造，不含房租本金） ──────────────
UNI_BASKET = [12500, 2400, 4200, 2200, 3400, 12000, 1850, 4450]   # Σ 43,000
UNI_BAND_NOTE = ("学费 5,500 + 住宿 1,200 + 生活费 30,000 + 书本设备 6,500 "
                 "+ 寒暑假在家水电物业分摊 3,000（口径与 0–17 一致）；"
                 "18–22 为构造块，四年等值，非逐年估计")

# 22 岁（毕业年）在构造块内部的一次性加项：租房押金 + 首月租金按半年计
# （居住 +1,800）+ 求职/搬家/毕业过渡（其他 +1,200）。它把 22→23 的口径缝
# 从 +27.5% 收到 +13% 左右，同时不改 18–21 的"四年等值"构造。
UNI_YEAR_ADD = {22: {"housing": 1800.0, "other": 1200.0}}

# ══════════════════════════════════════════════════════════════════════════
# 2. 23–85 岁：户均消费 h(a) × 成人份额调整 φ(a) × 退休台阶 ρ(a)
# ══════════════════════════════════════════════════════════════════════════
# h(a)：该年龄「典型家庭」的人均消费（含孩子，÷ 全家人口）。
# 形状来自 A/B 审计的独立先验（23–29 56k / 30–39 62k / 40–49 69k / 50–59 66k /
# 60–69 50k / 70–85 40k，×0.862 折算）去掉「有孩户被孩子拉低」的部分后，
# 平滑成一条近乎平坦、59 岁见顶、之后缓降的曲线。
H_KNOTS = [
    (23, 51400.0), (27, 55000.0), (32, 55500.0), (38, 56200.0),
    (45, 56600.0), (52, 56400.0), (59, 55000.0), (65, 53200.0),
    (70, 51600.0), (75, 50000.0), (80, 48200.0), (85, 47400.0),
]

# φ(a) = 1 + κ·s(a)·(1 − c̄_kid / h(a))
#   s(a) = n_c / (n_a + n_c)：户内儿童数占家庭人口的比例（按 build_household 的
#          户均构成规则：30–52 岁为「2 成人 + 1 孩」，其余年龄 n_c = 0）
#   c̄_kid：0–22 岁孩子的平均年成本（用全周期均值，不用当年值，避免把
#          「孩子当年贵」误读成「父母当年穷」）
#   κ = 1：恒等式口径（家庭消费 = 成人自身 + 孩子份额）
PHI = {"child_age_lo": 30, "child_age_hi": 52, "n_child": 1.0,
       "n_adult": 2.0, "kappa": 1.0, "sigma": 2.0}

# ρ(a)：退休坡度。v2 用一年内硬下移 10% 的 smoothstep(59,60)，被 C 复核
# 判定为"装饰性硬编码"（去掉后 59→60 只剩 −0.49%）。v3 改成 5 年 glide：
# 60..64 = 0.970/0.945/0.925/0.910/0.900，59→60 约 −3%，60→64 累计 −10%。
# 这是"坡"不是"崖"，且不再依赖一个刚好能框住答案的验收窗口。
RETIRE = {"knots": [(59, 1.000), (60, 0.970), (61, 0.945), (62, 0.925),
                    (63, 0.910), (64, 0.900), (85, 0.900)],
          # 用「完成度」曲线参数化端点，端点值本身是敏感性变量（v4）：
          # ρ(a) = 1 + (ρ_end − 1)·frac(a)，frac 在 59→64 线性铺开。
          "frac": [(59, 0.00), (60, 0.30), (61, 0.55), (62, 0.75),
                   (63, 0.90), (64, 1.00), (85, 1.00)],
          "end_value": 0.90,
          "start": 59.0, "end": 64.0, "drop": 0.10,
          "note": "5 年 glide，累计 −10%，非一年硬下移"}

# 23–26 岁：合租/单间租金低于 27 岁后的整租，居住份额随年龄爬升（v3 新增）。
# 它只改份额（行和不变），总额的下移由 H_KNOTS(23)=51,400 承担。
YOUNG_HOUSING = {23: 0.86, 24: 0.90, 25: 0.94, 26: 0.97}

# A5 情景：老年段水平再乘一个系数（1.0 = 不额外折减）
A5_DEFAULT = 1.0

# ══════════════════════════════════════════════════════════════════════════
# 3. 成人八类份额：2024 上海成人平均结构 × 年龄相对梯度
#    梯度 g_j(a) 的（人口加权）均值 = 1，所以列和天然接近官方值；
#    IPF 只做小幅修正，逐带缩放率会被完整报告。
# ══════════════════════════════════════════════════════════════════════════
SHARE_GRAD_AGES = [23, 27, 32, 38, 45, 52, 59, 60, 66, 72, 78, 85]
SHARE_GRAD = {
    #          23    27    32    38    45    52    59    60    66    72    78    85
    "food":      [1.02, 1.04, 1.05, 1.03, 1.00, 0.98, 0.97, 0.97, 0.99, 1.03, 1.07, 1.12],
    "clothing":  [1.18, 1.30, 1.26, 1.12, 1.00, 0.94, 0.90, 0.89, 0.86, 0.82, 0.78, 0.72],
    "housing":   [1.13, 1.16, 1.17, 1.10, 1.00, 0.91, 0.84, 0.82, 0.76, 0.70, 0.65, 0.60],
    "durables":  [0.94, 1.02, 1.06, 1.04, 1.00, 0.98, 0.97, 0.97, 0.96, 0.94, 0.92, 0.88],
    "transport": [0.95, 1.05, 1.10, 1.09, 1.00, 0.93, 0.87, 0.85, 0.79, 0.72, 0.66, 0.58],
    "education": [1.02, 1.00, 0.95, 0.97, 1.00, 1.02, 1.04, 1.05, 1.09, 1.11, 1.10, 0.98],
    "health":    [0.34, 0.36, 0.39, 0.46, 0.60, 0.82, 1.16, 1.34, 1.70, 2.20, 3.05, 4.50],
    "other":     [1.12, 1.08, 1.04, 1.00, 0.97, 0.95, 0.93, 0.92, 0.90, 0.87, 0.84, 0.78],
}

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
BASIS = {
    0: "估算-B 分项篮子（家庭代付，不含房租/房贷本金）",
    18: "构造块-C 学费+住宿+生活费（四年等值，非逐年估计）",
    23: "估算-B 户均×成人份额调整 + IPF 标定(2024 上海)；22→23 为口径缝（校园→青年自身消费）",
    24: "估算-B 户均×成人份额调整 + IPF 标定(2024 上海)",
    70: "外推-C 户均曲线外推 + CHARLS/美日校准",
}


# ══════════════════════════════════════════════════════════════════════════
# 工具
# ══════════════════════════════════════════════════════════════════════════
def smooth1d(x, sigma):
    """高斯平滑（边缘复制），sigma 单位为岁。"""
    x = np.asarray(x, dtype=float)
    if sigma <= 0:
        return x.copy()
    r = max(1, int(math.ceil(3 * sigma)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    xp = np.pad(x, r, mode="edge")
    return np.convolve(xp, k, mode="valid")


def smooth2d(X, sigma):
    return np.column_stack([smooth1d(X[:, j], sigma) for j in range(X.shape[1])])


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ══════════════════════════════════════════════════════════════════════════
# 4. 人口权重
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
    tau = 11.5
    for _ in range(60):
        cb = 0.5 * (cb_lo + cb_hi)
        t_lo, t_hi = 4.0, 40.0
        for _ in range(60):
            tau = 0.5 * (t_lo + t_hi)
            if _share(population_weights(cb, tau), 60, 85) < POP_TARGET["60+"]:
                t_lo = tau
            else:
                t_hi = tau
        tau = 0.5 * (t_lo + t_hi)
        if _share(population_weights(cb, tau), 0, 14) > POP_TARGET["0-14"]:
            cb_hi = cb
        else:
            cb_lo = cb
    cb = 0.5 * (cb_lo + cb_hi)
    return cb, tau


POP_CSV = "shanghai_pop_age.csv"


def load_pop_weights():
    with open(DATA / POP_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    p = {int(r["age"]): float(r["population"]) for r in rows}
    v = np.array([p.get(int(a), 0.0) for a in AGES], dtype=float)
    v[-1] += sum(p.get(a, 0.0) for a in range(86, 101))
    return v / v.sum(), {"source": POP_CSV, "total": float(sum(p.values())),
                         "year": int(rows[0]["year"]), "n_ages": len(rows)}


def get_pop_weights(use_constructed=None):
    if use_constructed is None:
        use_constructed = ("--constructed-pop" in sys.argv
                           or os.environ.get("POP_WEIGHTS", "").lower() == "constructed")
    if use_constructed:
        cb, tau = calibrate_population()
        return population_weights(cb, tau), {"child_base": cb, "old_tau": tau}
    return load_pop_weights()


# ══════════════════════════════════════════════════════════════════════════
# 5. 0–17 / 18–22：分项篮子
# ══════════════════════════════════════════════════════════════════════════
def _band_index():
    idx = np.zeros(18, dtype=int)
    for i, (lo, hi) in enumerate(CHILD_BANDS):
        idx[lo:hi + 1] = i
    return idx


def child_profile(kindergarten_addon=0.0):
    """返回 (level[18], share[18,8], basket)。

    kindergarten_addon：3–5 岁教育项外生的额外加项（base 0 = 公办 5,000 已含
    在篮子里；敏感性 private_12000 用 +7,000，把民办园与公办园的差额补上）。
    """
    basket = np.array(CHILD_BASKET, dtype=float)
    idx = _band_index()
    X = basket[idx].copy()
    if kindergarten_addon:
        X[3:6, CATS.index("education")] += float(kindergarten_addon)
    # 教育在 3 岁有一个制度性台阶（入园），用更小的平滑核，避免把 9,200
    # 泄漏回 0–2 岁（验收要求 0–2 岁教育 < 3,000）
    sig = np.full(len(CATS), 0.75)
    sig[CATS.index("education")] = 0.35
    X = np.column_stack([smooth1d(X[:, j], sig[j]) for j in range(len(CATS))])
    # 婴幼儿按年摊销，而不是把一次性购置当年流量重复三次：推车/童床/安全
    # 座椅合计 8,000–15,000 是 0 岁的一次性支出；医疗（疫苗/儿保/门诊）则
    # 高于学龄段。v2 的 8,000/年 被 C 复核判为配平项（高于双方先验 45–78%）。
    for a, kv in INFANT_AMORTIZE.items():
        for k, v in kv.items():
            X[a, CATS.index(k)] = v
    # 0–2 岁托育/早教：教育列不再是一条 1,200 的直线，按 0/1/2 岁的入托
    # 强度与早教参与率分别给出。放在平滑之后覆盖，避免 3 岁 9,200 的入园
    # 台阶把 0–2 岁"抬"起来，也避免 0–2 岁把 3 岁"压"下去。
    for a, spec in INFANT_EDU.items():
        X[a, CATS.index("education")] = (
            spec["tuoyu_rate"] * spec["tuoyu_fee"] * 12.0
            + spec["zaojiao_rate"] * spec["zaojiao_spend"])
    level = X.sum(1)
    share = X / level[:, None]
    return level, share, basket


def university_profile():
    X = np.tile(np.array(UNI_BASKET, dtype=float), (5, 1))
    for a, kv in UNI_YEAR_ADD.items():
        for k, v in kv.items():
            X[a - 18, CATS.index(k)] += v
    level = X.sum(1)
    return level, X / level[:, None]


# ══════════════════════════════════════════════════════════════════════════
# 6. 成人：h(a) × φ(a) × ρ(a)
# ══════════════════════════════════════════════════════════════════════════
def household_adult_share(ages, phi=PHI):
    """s(a) = n_c/(n_a+n_c)，按户均构成规则 30–52 岁有 1 个孩子，边缘平滑。"""
    a = np.asarray(ages, float)
    s = np.zeros_like(a)
    inside = (a >= phi["child_age_lo"]) & (a <= phi["child_age_hi"])
    # 成人份额调整的恒等式：n_a·c_adult + n_c·c_kid = (n_a+n_c)·h
    #   ⇒ c_adult = h + (n_c/n_a)(h − c_kid) ⇒ φ = 1 + (n_c/n_a)(1 − c_kid/h)
    s[inside] = phi["n_child"] / phi["n_adult"]
    return smooth1d(s, phi["sigma"])


def adult_level_shape(a5_factor=A5_DEFAULT, diag=None, retire_end=None):
    ages = np.arange(ADULT_LO, ADULT_HI + 1, dtype=float)
    ax = np.array([k[0] for k in H_KNOTS], float)
    ay = np.array([k[1] for k in H_KNOTS], float)
    h = np.interp(ages, ax, ay)
    h = smooth1d(h, 1.2)

    # 老年段额外折减（A5 情景；默认 1.0 关闭）
    if a5_factor != 1.0:
        h = h * (1.0 + (float(a5_factor) - 1.0) * smoothstep(60, 85, ages))

    s = household_adult_share(ages)
    kid_mean = float(np.average(np.concatenate([child_profile()[0], university_profile()[0]])))
    phi = 1.0 + PHI["kappa"] * s * (1.0 - kid_mean / h)

    # ρ(a) = 1 + (ρ_end − 1)·frac(a)：端点 ρ_end 是敏感性变量（0.85/0.90/0.95），
    # frac 是 59→64 的完成度曲线，保证 59→60 只走完 30%。
    if retire_end is None:
        retire_end = RETIRE["end_value"]
    fx = np.array([k[0] for k in RETIRE["frac"]], float)
    fy = np.array([k[1] for k in RETIRE["frac"]], float)
    rho = 1.0 + (float(retire_end) - 1.0) * np.interp(ages, fx, fy)
    level = h * phi * rho
    if diag is not None:
        diag.update(dict(ages=ages, h=h, phi=phi, rho=rho, kid_mean=kid_mean,
                         retire_end=float(retire_end)))
    return level, phi, rho, h


def adult_share_prior(adult_resid):
    """2024 成人平均份额 × 年龄梯度 g_j(a)，行归一。"""
    ages = np.arange(ADULT_LO, ADULT_HI + 1, dtype=float)
    target = np.asarray(adult_resid, float)
    target = target / target.sum()
    grad = np.zeros((len(ages), len(CATS)))
    for j, c in enumerate(CATS):
        grad[:, j] = np.interp(ages, SHARE_GRAD_AGES, SHARE_GRAD[c])
        # 医疗在 59→60 的台阶必须保留（退休后医疗不降），用更小的核
        grad[:, j] = smooth1d(grad[:, j], 0.35 if c == "health" else 1.0)
    share = grad * target[None, :]
    share /= share.sum(1, keepdims=True)
    return ages, share, target


# ══════════════════════════════════════════════════════════════════════════
# 7. IPF / RAS（行和锁定 = 水平形状不变；列和 = 八类官方额）
# ══════════════════════════════════════════════════════════════════════════
def ipf(X, row_tot, col_tot, w, iters=20000, tol=1e-13):
    """行列交替缩放。返回 (X, 每格相对初始的缩放因子矩阵)。"""
    X0 = X.copy()
    for _ in range(iters):
        X *= (row_tot / X.sum(1))[:, None]
        cur = (X * w[:, None]).sum(0)
        X *= (col_tot / cur)[None, :]
        row_err = np.max(np.abs(X.sum(1) / row_tot - 1.0))
        col_err = np.max(np.abs((X * w[:, None]).sum(0) / col_tot - 1.0))
        if max(row_err, col_err) < tol:
            break
    return X, X / X0


def band_factors(ages, factors, bands):
    """把逐岁缩放因子聚合成 band×cat 表（按 w·x 加权平均）。"""
    out = {}
    for lo, hi in bands:
        m = (ages >= lo) & (ages <= hi)
        out[(lo, hi)] = factors[m].mean(0)
    return out


# ══════════════════════════════════════════════════════════════════════════
# 8. 构建
# ══════════════════════════════════════════════════════════════════════════
BANDS = [(23, 29), (30, 39), (40, 49), (50, 59), (60, 69), (70, 79), (80, 85)]


def build(pop=None, kindergarten_addon=0.0, a5_factor=A5_DEFAULT, diag=None,
          retire_end=None):
    if pop is None:
        pop = get_pop_weights()
    w, pop_params = pop

    child_lvl, child_sh, basket = child_profile(kindergarten_addon)
    uni_lvl, uni_sh = university_profile()
    fixed = np.vstack([child_lvl[:, None] * child_sh, uni_lvl[:, None] * uni_sh])

    resid = np.array([TARGET[c] for c in CATS]) - (fixed * w[:ADULT_LO, None]).sum(0)
    if (resid <= 0).any():
        raise SystemExit(f"残差类别为负：{dict(zip(CATS, resid))}")

    d = {}
    level, phi, rho, h = adult_level_shape(a5_factor, diag=d, retire_end=retire_end)
    # 全局水平：使 Σ w·level = Σ resid（此时总量自动 = 54,980）
    lam = resid.sum() / float((w[ADULT_LO:] * level).sum())
    level *= lam

    ages, share0, target = adult_share_prior(resid)
    # 23–26 的年轻租客份额修正（行和不变，只改构成）
    jh = CATS.index("housing")
    for a, g in YOUNG_HOUSING.items():
        i = int(a) - ADULT_LO
        share0[i, jh] *= g
        share0[i, :] /= share0[i, :].sum()
    X0 = level[:, None] * share0
    X, fac = ipf(X0, level, resid, w[ADULT_LO:])
    bf = band_factors(ages, fac, BANDS)
    max_adj = float(np.max(np.abs(fac - 1.0)))
    if max_adj > 0.15 + 1e-12:
        bad = np.unravel_index(np.argmax(np.abs(fac - 1.0)), fac.shape)
        raise SystemExit(
            f"IPF 缩放超出 ±15% 上限：格 {bad} 需 {fac[bad]:.4f}；"
            "请修正先验而不是放宽约束")

    full = np.vstack([fixed, X])
    row_targets = np.concatenate([child_lvl, uni_lvl, level])
    out = dict(ages=ages, h=h, phi=phi, rho=rho, lam=lam, level=level,
               share0=share0, target_share=target, factors=fac,
               band_factors=bf, max_adj=max_adj, resid=resid,
               row_targets=row_targets, pop_params=pop_params,
               basket=basket, kid_mean=d.get("kid_mean"))
    if diag is not None:
        diag.update(out)
    return full, w, out


# ══════════════════════════════════════════════════════════════════════════
# 9. 验收检查
# ══════════════════════════════════════════════════════════════════════════
def stage_of(a):
    for lo, hi, name, _ in STAGES:
        if lo <= a <= hi:
            return name
    raise ValueError(a)


def checks(full, w, dbg):
    tot = full.sum(1)
    out = {"total": tot}
    # 1) 水平与八类列
    out["weighted_total"] = float((w * tot).sum())
    out["weighted_total_err"] = out["weighted_total"] - TOTAL_ANCHOR
    out["cat"] = {}
    for j, c in enumerate(CATS):
        v = float((w * full[:, j]).sum())
        out["cat"][c] = {"model": v, "target": TARGET[c],
                         "err_pct": (v / TARGET[c] - 1) * 100}
    out["cat_err_max_pct"] = max(abs(v["err_pct"]) for v in out["cat"].values())

    # 2) 相邻年龄跌幅
    d = np.diff(tot) / tot[:-1] * 100
    out["drops"] = d
    drops_ex18 = [(i, float(v)) for i, v in enumerate(d) if v < 0 and i != 18]
    out["max_drop_ex18"] = min([v for _, v in drops_ex18], default=0.0)
    out["max_drop_ex18_age"] = (min(drops_ex18, key=lambda t: t[1])[0]
                                if drops_ex18 else None)
    out["drop_18"] = float(d[17])
    # v3 规则 (a)：任何相邻年跌幅 ≤8%。17→18（学制切换）与 22→23（口径缝）
    # 是两座桥，单独报告、不参与该规则——但也不遮掩：值就印在验收表里。
    drops_ex_bridge = [(i, float(v)) for i, v in enumerate(d)
                       if v < 0 and i not in (17, 22)]
    out["max_drop_ex_bridge"] = min([v for _, v in drops_ex_bridge], default=0.0)
    out["max_drop_ex_bridge_age"] = (min(drops_ex_bridge, key=lambda t: t[1])[0]
                                     if drops_ex_bridge else None)
    out["drop_22_23"] = float(d[22])

    # 3) 退休台阶
    out["drop_59_60"] = float(tot[60] / tot[59] - 1) * 100
    out["mean_50_59"] = float(tot[50:60].mean())
    out["mean_60_69"] = float(tot[60:70].mean())
    out["ratio_60_69_over_50_59"] = out["mean_60_69"] / out["mean_50_59"]

    # 4) 形状
    def peak_age(lo, hi, j=None):
        v = tot[lo:hi + 1] if j is None else full[lo:hi + 1, j]
        return int(np.argmax(v)) + lo

    def trough_age(lo, hi, j=None):
        v = tot[lo:hi + 1] if j is None else full[lo:hi + 1, j]
        return int(np.argmin(v)) + lo

    sh = {}
    sh["clothing_peak_age"] = peak_age(0, 85, CATS.index("clothing"))
    sh["clothing_4_vs_23"] = float(full[4, CATS.index("clothing")] /
                                   full[23, CATS.index("clothing")] - 1) * 100
    sh["education_peak_age"] = peak_age(0, 85, CATS.index("education"))
    sh["education_0_2_max"] = float(full[0:3, CATS.index("education")].max())
    sh["health_85"] = float(full[85, CATS.index("health")])
    sh["health_0"] = float(full[0, CATS.index("health")])
    hv = full[23:, CATS.index("health")]
    sh["health_monotone_23_85"] = bool(np.all(np.diff(hv) >= -hv[:-1] * 0.005))
    sh["health_min_dip_pct"] = float(min(np.diff(hv) / hv[:-1] * 100))
    hh = full[ADULT_LO:, CATS.index("housing")]
    pk = int(np.argmax(hh))
    sh["housing_peak_age"] = pk + ADULT_LO
    sh["housing_monotone_after_peak"] = bool(np.all(np.diff(hh[pk:]) <= hh[pk:-1] * 0.002))
    sh["housing_max_rise_after_peak_pct"] = float(
        max([0.0] + list(np.diff(hh[pk:]) / hh[pk:-1] * 100)))
    sh["food_85"] = float(full[85, CATS.index("food")])
    sh["food_45"] = float(full[45, CATS.index("food")])
    sh["global_peak_age"] = int(np.argmax(tot))
    sh["global_peak"] = float(tot.max())
    sh["global_trough_age"] = int(np.argmin(tot))
    sh["global_trough"] = float(tot.min())
    sh["peak_to_trough"] = sh["global_peak"] / sh["global_trough"]
    sh["adult_peak_age"] = int(np.argmax(tot[ADULT_LO:]) + ADULT_LO)
    sh["adult_peak"] = float(tot.max()) if sh["global_peak_age"] >= ADULT_LO else float(
        tot[ADULT_LO:].max())
    # v3 规则 (b)：全局峰之后不再上升
    sh["monotone_after_peak"] = bool(
        np.all(np.diff(tot[sh["global_peak_age"]:]) <= 0.0))
    sh["rise_after_peak_max_pct"] = float(max(
        [0.0] + list(np.diff(tot[sh["global_peak_age"]:]) /
                     tot[sh["global_peak_age"]:-1] * 100)))
    out["shape"] = sh

    # 6) 户内一致性（3 口之家：35+35+5）
    c35 = tot[35]
    c5 = tot[5]
    hh_total = 2 * c35 + c5
    hh_pc = hh_total / 3.0
    # 独立基准：该户人均消费 h(35) = c(35)/φ(35)（φ 为成人份额调整因子），
    # 户总消费基准 = 3·h(35)。归因和 = 2·c(35) + c(5)。
    i35 = 35 - ADULT_LO
    phi35 = float(dbg["phi"][i35])
    h35 = c35 / phi35
    bench = 3.0 * h35
    out["household"] = {"father": float(c35), "mother": float(c35), "child": float(c5),
                        "total": float(hh_total), "per_capita": float(hh_pc),
                        "phi_35": phi35, "h_35": float(h35), "bench_total_3h": float(bench),
                        "attr_vs_total_pct": float((hh_total / bench - 1) * 100),
                        "formula": "attr=2·c(35)+c(5); bench=3·h(35), h(35)=c(35)/φ(35)"}

    out["negative"] = int((full < 0).sum())
    out["max_adj"] = float(dbg["max_adj"])
    return out


# ══════════════════════════════════════════════════════════════════════════
# 10. 输出
# ══════════════════════════════════════════════════════════════════════════
def _segment(a):
    if a <= 17:
        return "0-17 家庭代付"
    if a <= 22:
        return "18-22 大学"
    if a <= 69:
        return "23-69 标定"
    return "70-85 外推"


def _basis(a):
    if a <= 17:
        return BASIS[0]
    if a <= 22:
        return BASIS[18]
    if a == 23:
        # 口径缝只标在 23 岁这一行本身，不要复制到 24–69（v4 清理）
        return BASIS[23]
    if a <= 69:
        return BASIS[24]
    return BASIS[70]


NOTE = {
    0: "出生；家庭代付口径，按分项篮子计入，非个人独立消费",
    3: "入园；公办园 5,000 计入教育，教育首次成为最大单项",
    15: "高中；教育 13,700 为 0–17 段峰值",
    18: "学制切换；17→18 −7.8%（家庭代付篮子→大学成本构造）",
    22: "毕业年；构造块内加租房押金/求职搬家 3,000（居住 6,000）",
    23: "口径缝：校园成本（含寒暑假水电）→ 上海青年自身消费（合租租金 1,750/月）",
    30: "生育；φ(a) 上行，成人自身消费相对户均上移",
    45: "自身消费峰值段（40–59）；居住份额已从 42% 降至 38%",
    60: "退休；5 年 glide 起点（59→60 约 −3%，60→64 累计 −10%）",
    70: "高龄；医疗占比超过 20%",
    85: "序列终点（85 岁及以上，85–100 岁合并）；医疗含约 4,000 居家照护",
}


def write_csv(full, tot):
    path = DATA / "shanghai_lifecycle.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["age", "stage", "segment"] + [f"cat_{c}" for c in CATS] +
                    ["total"] + [f"share_{c}" for c in CATS] + ["basis", "note"])
        for a in AGES:
            wr.writerow([int(a), stage_of(a), _segment(a)] +
                        [round(float(full[a, j]), 1) for j in range(8)] +
                        [round(float(tot[a]), 1)] +
                        [round(float(full[a, j] / tot[a]), 4) for j in range(8)] +
                        [_basis(a), NOTE.get(int(a), "")])


def write_scenarios(full, w):
    scen_def = {
        "low":  {"edu": 0.8, "housing": 0.8, "health": 0.8},
        "base": {"edu": 1.0, "housing": 1.0, "health": 1.0},
        "high": {"edu": 1.4, "housing": 1.2, "health": 1.3},
    }
    store = {}
    with open(DATA / "shanghai_lifecycle_scenarios.csv", "w",
              encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["scenario", "age"] + [f"cat_{c}" for c in CATS] + ["total"])
        for name, p in scen_def.items():
            X = full.copy()
            X[:, CATS.index("education")] *= p["edu"]
            X[25:46, CATS.index("housing")] *= p["housing"]
            X[60:, CATS.index("health")] *= p["health"]
            store[name] = X
            for a in AGES:
                wr.writerow([name, int(a)] +
                            [round(float(X[a, j]), 1) for j in range(8)] +
                            [round(float(X[a].sum()), 1)])
    return store, scen_def


def write_diff(full, tot):
    """新旧逐年龄 + 阶段聚合差异。"""
    old_path = DATA / "archive" / "shanghai_lifecycle_v1.csv"
    if not old_path.exists():
        print(f"[warn] 缺少 {old_path}，跳过 diff")
        return
    old = {}
    with open(old_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            old[int(r["age"])] = float(r["total"])
    rows = []
    for a in AGES:
        o, n = old[int(a)], float(tot[a])
        rows.append([int(a), o, n, n - o, (n / o - 1) * 100])
    with open(DATA / "rebuild_diff.csv", "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["age", "old", "new", "delta", "pct"])
        for r in rows:
            wr.writerow([r[0], round(r[1], 1), round(r[2], 1),
                         round(r[3], 1), round(r[4], 2)])
    with open(DATA / "rebuild_diff_stages.csv", "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["stage", "start", "end", "old_mean", "new_mean", "delta", "pct"])
        for lo, hi, name, _ in STAGES:
            o = float(np.mean([old[int(a)] for a in range(lo, hi + 1)]))
            n = float(tot[lo:hi + 1].mean())
            wr.writerow([name, lo, hi, round(o, 1), round(n, 1),
                         round(n - o, 1), round((n / o - 1) * 100, 2)])


def write_diff_v2v3(full, tot):
    """v2 → v3 的逐年龄对比（C 复核后的三处再改）。"""
    old_path = DATA / "archive" / "shanghai_lifecycle_v2.csv"
    if not old_path.exists():
        print(f"[warn] 缺少 {old_path}，跳过 v2→v3 diff")
        return
    old = {}
    with open(old_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            old[int(r["age"])] = float(r["total"])
    with open(DATA / "rebuild_diff_v2_v3.csv", "w",
              encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["age", "old_v2", "new_v3", "delta", "pct"])
        for a in AGES:
            o, n = old[int(a)], float(tot[a])
            wr.writerow([int(a), round(o, 1), round(n, 1),
                         round(n - o, 1), round((n / o - 1) * 100, 2)])


def write_diff_v3v4(full, tot):
    """v3 → v4 的逐年龄对比（D 复核后的四处再改）。"""
    old_path = DATA / "archive" / "shanghai_lifecycle_v3.csv"
    if not old_path.exists():
        print(f"[warn] 缺少 {old_path}，跳过 v3→v4 diff")
        return
    old = {}
    with open(old_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            old[int(r["age"])] = float(r["total"])
    with open(DATA / "rebuild_diff_v3_v4.csv", "w",
              encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["age", "old_v3", "new_v4", "delta", "pct"])
        for a in AGES:
            o, n = old[int(a)], float(tot[a])
            wr.writerow([int(a), round(o, 1), round(n, 1),
                         round(n - o, 1), round((n / o - 1) * 100, 2)])


def build_retirement_glide(pop, base_tot=None):
    """退休 glide 端点敏感性：0.85 / 0.90 / 0.95。

    每档独立重跑 build()（行和/列和照常锁定，λ 重新归一化到 54,980），
    报告 59→60、59→64、60–69 均值、30–39 均值、85 岁总额、峰谷比。
    """
    variants = {}
    for end in (0.85, 0.90, 0.95):
        full, w, dbg = build(pop=pop, retire_end=end)
        tot = full.sum(1)
        chk = checks(full, w, dbg)
        sh = chk["shape"]
        variants[f"end_{end:.2f}"] = {
            "retire_end_value": end,
            "rho_60_64_85": [round(float(dbg["rho"][a - ADULT_LO]), 4)
                             for a in (60, 64, 85)],
            "drop_59_60_pct": round(chk["drop_59_60"], 2),
            "cum_59_64_pct": round(float(tot[64] / tot[59] - 1) * 100, 2),
            "mean_60_69": round(float(tot[60:70].mean()), 1),
            "mean_30_39": round(float(tot[30:40].mean()), 1),
            "total_85": round(float(tot[85]), 1),
            "peak_age": sh["global_peak_age"],
            "peak_value": round(sh["global_peak"], 1),
            "trough_age": sh["global_trough_age"],
            "trough_value": round(sh["global_trough"], 1),
            "peak_to_trough": round(sh["peak_to_trough"], 2),
            "ratio_60_69_over_50_59": round(chk["ratio_60_69_over_50_59"], 3),
            "weighted_mean": round(chk["weighted_total"], 2),
        }
    base = variants[f"end_{RETIRE['end_value']:.2f}"]
    note = ("glide 端点 ρ_end 是估计值不是观测值：0.85/0.90/0.95 三档分别对应"
            "退休后消费降 15%/10%/5%。三档都各自归一化到 54,980 且八类锁官方，"
            "所以差异只出现在 59 岁之后的形状上。")
    if base_tot is not None:
        note += f" base 档（0.90）85 岁 {base['total_85']:,.1f} 元。"
    return {"title": "退休 glide 端点敏感性（ρ_end）", "note": note,
            "variants": variants}


def _variant_payload(full, w, chk, label, kindergarten_addon, a5_factor):
    tot = full.sum(1)
    return {
        "label": label,
        "kindergarten_addon": float(kindergarten_addon),
        "a5_factor": float(a5_factor),
        "total": [round(float(v), 1) for v in tot],
        "absolute": {c: [round(float(full[a, j]), 1) for a in AGES]
                     for j, c in enumerate(CATS)},
        "weighted_mean": round(float((w * tot).sum()), 1),
        "peak_age": chk["shape"]["global_peak_age"],
        "peak_value": round(chk["shape"]["global_peak"], 1),
        "adult_peak_age": chk["shape"]["adult_peak_age"],
        "adult_peak_value": round(chk["shape"]["adult_peak"], 1),
    }


def build_sensitivity(pop):
    kg = {}
    for key, addon, label in [
        ("private_12000", 7000.0, "民办园：3–5 岁教育 +7,000（公办 5,000 → 12,000）"),
        ("public_5000", 0.0, "公办园：3–5 岁教育 5,000（base）"),
    ]:
        full, w, dbg = build(pop=pop, kindergarten_addon=addon)
        chk = checks(full, w, dbg)
        kg[key] = _variant_payload(full, w, chk, label, addon, A5_DEFAULT)

    a5 = {}
    for key, factor, label in [
        ("a5_072", 0.72, "A5=0.72：老年段水平再降 28%（旧版口径）"),
        ("a5_100", 1.00, "A5=1.00：不做额外老年折减（base）"),
    ]:
        full, w, dbg = build(pop=pop, a5_factor=factor)
        chk = checks(full, w, dbg)
        a5[key] = _variant_payload(full, w, chk, label, 0.0, factor)

    summary = {
        "kindergarten_private_peak_age": kg["private_12000"]["peak_age"],
        "kindergarten_public_peak_age": kg["public_5000"]["peak_age"],
        "a5_removed_85yo": a5["a5_100"]["total"][85],
        "a5_072_85yo": a5["a5_072"]["total"][85],
        "conclusion": ("4 岁峰不再成立：公办与民办两种幼儿园口径下 "
                       "全局峰都在 45 岁前后"),
    }
    return {"kindergarten": kg, "a5": a5, "summary": summary}


def build_longtermcare(pop, base_full, w):
    """长护情景：60+ 医疗按年龄加成长护自付（85 岁 +3,000），
    其余类别按比例吸收，保持该年龄总额不变（不改变生命周期水平形状）。"""
    from copy import deepcopy
    variants = {}
    for key, add85, label in [
        ("base", 0.0, "base：居家口径，85 岁医疗 14,900 量级（含约 4,000 照护）"),
        ("ltc_1500", 1500.0, "含长护（低）：85 岁医疗 +1,500"),
        ("ltc_3000", 3000.0, "含长护（高）：85 岁医疗 +3,000，机构/外溢自付"),
    ]:
        X = base_full.copy()
        add = add85 * smoothstep(65, 85, AGES.astype(float))
        j = CATS.index("health")
        X[:, j] += add
        others = [k for k in range(8) if k != j]
        sub = X[:, others].sum(1)
        X[:, others] *= ((sub - add) / np.where(sub > 0, sub, 1))[:, None]
        tot = X.sum(1)
        variants[key] = {
            "label": label,
            "health_85": round(float(X[85, j]), 1),
            "total_85": round(float(tot[85]), 1),
            "weighted_mean": round(float((w * tot).sum()), 2),
            "health": [round(float(v), 1) for v in X[:, j]],
            "absolute": {c: [round(float(X[a, k]), 1) for a in AGES]
                         for k, c in enumerate(CATS)},
        }
    return {
        "title": "老年医疗「含长护」情景",
        "note": ("base 为居家口径（85 岁医疗约 14,900，其中 NBS 医疗约 10,900 + "
                 "居家照护 4,000），长护情景把 65→85 岁"
                 "的机构养老/外溢自付按年龄斜坡加入医疗，并从其他类别等比例扣除，"
                 "保持各年龄总额不变；因此本情景只改结构，不改 54,980 标定。"),
        "variants": variants,
    }


def build_json(full, w, chk, dbg, scen_store, scen_def, sens, ltc, glide=None):
    tot = chk["total"]
    sh = chk["shape"]
    active = {"0-14": round(float(w[:15].sum()), 4),
              "15-59": round(float(w[15:60].sum()), 4),
              "60+": round(float(w[60:].sum()), 4),
              "65+": round(float(w[65:].sum()), 4)}
    cb, tau = calibrate_population()
    wfb = population_weights(cb, tau)
    fallback = {"0-14": round(float(wfb[:15].sum()), 4),
                "15-59": round(float(wfb[15:60].sum()), 4),
                "60+": round(float(wfb[60:].sum()), 4),
                "65+": round(float(wfb[65:].sum()), 4)}

    band_tbl = []
    for lo, hi in BANDS:
        row = {"band": f"{lo}-{hi}"}
        for j, c in enumerate(CATS):
            row[c] = round(float(dbg["band_factors"][(lo, hi)][j] - 1.0) * 100, 2)
        band_tbl.append(row)

    phi_pts = {int(a): round(float(dbg["phi"][a - ADULT_LO]), 4)
               for a in [23, 30, 35, 40, 45, 50, 52, 55, 60, 70, 85]}

    stages = []
    palette = {"婴幼儿": "#E8C4B8", "学前": "#E3B7A5", "小学": "#D9A88F",
               "初中": "#CE9A7C", "高中": "#C08A6A", "大学": "#9B8EA8",
               "初入职场": "#8FA9B8", "成家育儿": "#6F9AA8", "中年": "#5B8797",
               "空巢前": "#4C7484", "退休过渡": "#7E8F7A", "高龄": "#93A18B",
               "耄耋": "#A8B39C"}
    for lo, hi, name, seg in STAGES:
        stages.append({"id": f"s{lo}", "label": name, "start": lo, "end": hi,
                       "segment": seg, "color": palette[name]})

    annotations = [
        {"age": 0, "type": "stage", "title": "出生",
         "text": "0–17 岁是「家庭为一个孩子直接支付的现金」，不是孩子自己的消费。0 岁约 3.2 万，食品约 39%，医疗 2,200（7%）；含托育/早教后 0–2 岁不再是同一个数。"},
        {"age": 3, "type": "stage", "title": "入园",
         "text": "公办园 5,000 计入教育。v1 的「4 岁最贵」是 12,000 元/年幼儿园假设的产物；本版两种口径下 4 岁都不是峰。2→3 岁只涨个位数（v3 是 +24.9%）。"},
        {"age": 15, "type": "peak", "title": "教育峰值",
         "text": "高中教育 13,700，为 0–17 段最高；但 18 岁只比 17 岁低约 8%，不再是断崖。"},
        {"age": 18, "type": "step", "title": "大学",
         "text": "学费+住宿+生活费 43,000，独立构造，不含房租本金；与 17 岁同口径衔接。"},
        {"age": 23, "type": "stage", "title": "就业",
         "text": "进入「户均消费 × 成人份额调整」段：23 岁自身消费约 5.6 万，居住占 41%。"},
        {"age": 30, "type": "note", "title": "生育",
         "text": "φ(a) 从 1.00 升到约 1.07：有孩户里成年人自身消费高于户均，因为孩子份额低于人均。30–49 不再被分母摊薄。"},
        {"age": 45, "type": "peak", "title": "全局峰",
         "text": "40–59 岁是全局峰（约 6.2 万）。v1 的成年峰被机械推到 59 岁，本版回到 45 岁前后。"},
        {"age": 60, "type": "step", "title": "退休",
         "text": "退休坡度：59→60 约 −3.5%，59→64 累计约 −12%。v1 只有 −0.57%，是一条假平台；v2 的 −10.4% 是一年内硬下移。"},
        {"age": 85, "type": "note", "title": "高龄",
         "text": "医疗约 14,900、占 34%（NBS 医疗 ~10,900 + 居家照护 4,000）；含长护情景见 sensitivity_longtermcare.json。"},
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
        {"id": "YUHUA-2022", "level": "B",
         "label": "育娲人口《中国生育成本报告 2022 版》",
         "url": "https://www.199it.com/archives/1392623.html",
         "use": "0–17 分段总额与教育/医疗/居住三大项的比例锚（本版只用其结构，不用其四等分）"},
        {"id": "YUHUA-2026", "level": "B",
         "label": "育娲人口《中国生育成本报告 2026 版》",
         "url": "https://cj.sina.com.cn/articles/view/1704103183/65928d0f0200aos0k",
         "use": "上海 4,751 元/月（本版指出该值含推算房租，与本版不含房租本金的口径不可直接比）"},
        {"id": "S1", "level": "B",
         "label": "倪红福、李善同、何建武 (2014)，人口与发展 20(5):25-34，表2",
         "url": "https://ccj.pku.edu.cn/Article/DownLoad?id=331122480&type=ArticleFile",
         "use": "仅用其年龄梯度方向（不用其 2007 年水平，否则需 −34% 压缩，超出 ±15% 约束）"},
        {"id": "S2", "level": "B",
         "label": "石贝贝 (2017)，人口研究 41(3):53-64，表3",
         "url": "https://rkyj.ruc.edu.cn/EN/article/downloadArticleFile.do?attachType=PDF&id=3469",
         "use": "60+ 老年段结构（CHARLS 2013 城镇）"},
        {"id": "BLS-CE-2023", "level": "A",
         "label": "BLS Consumer Expenditure Survey 2023（PUMD 微观，逐岁）",
         "url": "https://www.bls.gov/cex/pumd_data.htm",
         "use": "成人段 h(a) 的水平形状参照（per consumer unit / 家庭人数）"},
        {"id": "JP-KAKEI-2024", "level": "A",
         "label": "日本总务省 家計調査 2024 年報 第3表",
         "url": "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040297516&fileKind=4",
         "use": "退休台阶与高龄梯度的第二来源"},
        {"id": "PBoC-2019", "level": "B",
         "label": "中国人民银行城镇居民家庭资产负债调查（2019-10）",
         "url": "https://tech.sina.com.cn/roll/2020-04-25/doc-iircuyvh9753649.shtml",
         "use": "26–35 岁负债参与率 73.1%，用于居住驼峰"},
        {"id": "P1", "level": "C", "label": "上海 2024 常住人口年龄结构（模型构造）",
         "url": "", "use": "人口权重 fallback；默认用 2025 实测单岁表"},
    ]

    return {
        "meta": {
            "title": "一个上海人的一生：0–85 岁逐年消费结构（v4）",
            "age_axis_label": "85 岁及以上（85–100 岁合并为一个顶码）",
            "city": "上海", "year": 2024, "currency": "CNY", "unit": "元/人/年",
            "price_base": "2024 年上海价",
            "basis": "模型估算，非官方观测",
            "version": "v4-rebuild-2026-11",
            "disclaimer": ("上海 2024 官方只发布全年龄八大类。年龄形状由分项篮子（0–17）、"
                           "大学成本构造（18–22）、户均×成人份额调整（23–85）得到，"
                           "再用 IPF 锁定 54,980 与八类官方额；每格都不是官方分年龄观测值。"),
            "weighted_mean": round(chk["weighted_total"], 2),
            "anchor_total": TOTAL_ANCHOR,
            "peak_age": sh["global_peak_age"], "peak_value": round(sh["global_peak"], 1),
            "trough_age": sh["global_trough_age"], "trough_value": round(sh["global_trough"], 1),
            "peak_to_trough": round(sh["peak_to_trough"], 2),
            "adult_peak_age": sh["adult_peak_age"],
            "adult_peak_value": round(sh["adult_peak"], 1),
            "medical_85_split": {
                "label": "85 岁医疗的两种口径（图表仍为 8 类，不新增堆叠项）",
                "nbs_medical": round(float(sh["health_85"]) - 4000.0, 1),
                "home_care_addon": 4000.0,
                "total": round(float(sh["health_85"]), 1),
                "note": ("NBS 医疗保健列不含长期照护；本表按含居家照护口径给出。"
                         "去掉 4,000 照护后与 A 先验的居家区间 10,600–11,500 一致；"
                         "含机构/外溢的长护口径见 sensitivity_longtermcare.json 的 ltc_3000。"),
            },
            "childcare_0_2": {
                "assumption": ("上海 3 岁以下入托率约 5%–8%（2 岁托班是主体）；"
                               "托班月费公办 2,000–3,000、民办 5,000–8,000，"
                               "取混合价 4,000 元/月；早教亲子课按参与率×4,000 元/年"),
                "education_by_age": [round(float(full[a, CATS.index("education")]), 1)
                                     for a in (0, 1, 2)],
                "tuoyu_rate": {str(a): s["tuoyu_rate"] for a, s in INFANT_EDU.items()},
                "tuoyu_fee_month": 4000.0,
                "zaojiao_rate": {str(a): s["zaojiao_rate"] for a, s in INFANT_EDU.items()},
                "zaojiao_spend_year": 4000.0,
                "note": ("v3 的 0–2 岁教育 1,200 隐含「三岁前育儿免费」，"
                         "使 2→3 成为 +24.9% 的全表最大跳变；v4 补托育后该跳变回到个位数。"),
            },
            "retirement_glide_sensitivity": {
                "file": "sensitivity_retirement_glide.json",
                "end_values": [0.85, 0.90, 0.95],
                "summary": ({k: {"drop_59_60_pct": v["drop_59_60_pct"],
                                 "cum_59_64_pct": v["cum_59_64_pct"],
                                 "peak_to_trough": v["peak_to_trough"]}
                             for k, v in glide["variants"].items()}
                            if glide else None),
            },
            "bridges": [
                {"age": 18, "change_pct": round(chk["drop_18"], 2),
                 "note": "学制切换：家庭代付的孩子篮子 → 大学成本构造块（四年等值）"},
                {"age": 23, "change_pct": round(chk["drop_22_23"], 2),
                 "note": "口径缝：校园成本（含寒暑假水电）→ 上海青年自身消费（含合租租金）"},
            ],
            "range_min": round(float(tot.min()), 1),
            "range_max": round(float(tot.max()), 1),
            "calibration": {
                "method": "行和 = 预设水平形状；列和 = 八类官方额；行列交替 IPF",
                "row_error_max": float(np.max(np.abs(full.sum(1) / dbg["row_targets"] - 1))),
                "weighted_total_error": round(chk["weighted_total_err"], 4),
                "category_error_pct_max": round(chk["cat_err_max_pct"], 4),
                "max_cell_scaling_pct": round(dbg["max_adj"] * 100, 2),
                "cap_pct": 15.0,
                "band_scaling_pct": band_tbl,
                "shape_is_input_not_output":
                    "水平形状由 h(a)×φ(a)×ρ(a) 给定，IPF 只调八类构成，不压平年龄形状",
                "counterfactual_raw_s1_food_compression_pct": -34.2,
                "counterfactual_note":
                    "若直接用 S1(2007) 的食品份额 38–41%，要把列和压回 13,877 需 −34%，"
                    "超出 ±15% 上限——所以 S1 只贡献年龄梯度方向，不贡献水平。",
                "phi_at_ages": phi_pts,
                "phi_formula": "φ(a)=1+κ·s(a)·(1−c̄_kid/h(a))，s(a)=n_c/n_a·1[30≤a≤52]（平滑）",
                "retirement_glide": {int(k): round(v, 3) for k, v in RETIRE["knots"]},
                "retirement_note": ("v4 把 glide 端点参数化为 ρ_end（0.85/0.90/0.95），"
                                    "见 sensitivity_retirement_glide.json；base 0.90 下 "
                                    "59→60 约 −3.5%，59→64 累计约 −12%"),
                "young_housing_gap": {int(k): v for k, v in YOUNG_HOUSING.items()},
                "lambda_level_scale": round(float(dbg["lam"]), 5),
            },
            "acceptance": {
                "weighted_54980": bool(abs(chk["weighted_total_err"]) < 0.01),
                "categories_exact": bool(chk["cat_err_max_pct"] < 0.005),
                "rule_a_max_drop_ex_bridge_pct": round(chk["max_drop_ex_bridge"], 2),
                "rule_a_ok": bool(chk["max_drop_ex_bridge"] >= -8.0),
                "rule_b_monotone_after_peak": sh["monotone_after_peak"],
                "bridge_18_pct": round(chk["drop_18"], 2),
                "bridge_22_23_pct": round(chk["drop_22_23"], 2),
                "drop_59_60_pct": round(chk["drop_59_60"], 2),
                "drop_59_60_note": "报告值，不设验收窗口（v2 的 [−18%,−8%] 已删除）",
                "shape": {k: (round(v, 2) if isinstance(v, float) else v)
                          for k, v in sh.items()},
                "household": chk["household"],
            },
            "population_weights": {
                "active": {"source": ("假设 P1：模型构造" if "child_base" in dbg["pop_params"]
                                      else f"实测：data/{dbg['pop_params'].get('source','')}"
                                           f"（{dbg['pop_params'].get('year','')} 年，单岁）"),
                           "band_shares": active, "params": dbg["pop_params"]},
                "fallback_constructed": {"band_shares": fallback,
                                         "params": {"child_base": round(cb, 4),
                                                    "old_tau": round(tau, 4)}},
                "source": ("假设 P1：模型构造" if "child_base" in dbg["pop_params"]
                           else f"实测：data/{dbg['pop_params'].get('source','')}"),
                "band_shares": active,
            },
            "zero_to_17_share_of_weighted_total": round(
                float((w[:18] * tot[:18]).sum() / chk["weighted_total"] * 100), 2),
            "scenario_def": {
                "edu_multiplier": {k: v["edu"] for k, v in scen_def.items()},
                "housing_multiplier_25_45": {k: v["housing"] for k, v in scen_def.items()},
                "health_multiplier_60plus": {k: v["health"] for k, v in scen_def.items()},
            },
            "sensitivity_summary": sens.get("summary"),
            "generated_by": "build_lifecycle.py (v4)",
        },
        "categories": [{"id": c, "label": CAT_LABEL[c],
                        "color": {"food": "#C4553B", "clothing": "#D9A441",
                                  "housing": "#2F5D62", "durables": "#7FA6A0",
                                  "transport": "#4A6FA5", "education": "#8B5E83",
                                  "health": "#A64253", "other": "#B9B3A8"}[c]}
                       for c in CATS],
        "ages": [int(a) for a in AGES],
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
        "longtermcare": ltc["variants"],
    }


def _print_diag(chk, dbg):
    sh = chk["shape"]
    print("\n— 逐带 IPF 缩放率（%，正=先验偏低被上调）—")
    hdr = "band  " + " ".join(f"{c[:4]:>6s}" for c in CATS)
    print(hdr)
    for lo, hi in BANDS:
        f = dbg["band_factors"][(lo, hi)]
        print(f"{lo:02d}-{hi:02d} " + " ".join(f"{(v-1)*100:+6.1f}" for v in f))
    print(f"max |cell scaling| = {dbg['max_adj']*100:.2f}%  (cap 15%)")
    print(f"λ（水平标定）= {dbg['lam']:.5f}")
    print(f"φ: 23={dbg['phi'][0]:.3f} 30={dbg['phi'][7]:.3f} "
          f"45={dbg['phi'][22]:.3f} 52={dbg['phi'][29]:.3f} 60={dbg['phi'][37]:.3f}")
    print("\n— 验收 —")
    print(f"1) 加权 {chk['weighted_total']:.2f}  err {chk['weighted_total_err']:+.4f}  "
          f"列最大偏差 {chk['cat_err_max_pct']:.4f}%")
    print(f"2) 规则(a) 除桥接外最大跌幅 {chk['max_drop_ex_bridge']:+.2f}% "
          f"@ {chk['max_drop_ex_bridge_age']}；桥接 17→18 {chk['drop_18']:+.2f}%、"
          f"22→23 {chk['drop_22_23']:+.2f}%")
    print(f"   规则(b) {sh['global_peak_age']} 岁后单调不增 {sh['monotone_after_peak']}"
          f"（峰后最大回升 {sh['rise_after_peak_max_pct']:+.2f}%）")
    dd = np.diff(chk["total"]) / chk["total"][:-1] * 100
    top = sorted(range(len(dd)), key=lambda i: -abs(dd[i]))[:3]
    print("   最大相邻年跳变 Top3：" + "；".join(
        f"{i}→{i + 1} {dd[i]:+.2f}%" for i in top))
    print(f"3) 59→60 {chk['drop_59_60']:+.2f}%（报告值；glide 5 年累计约 −10%）；"
          f"60–69/50–59 {chk['ratio_60_69_over_50_59']:.3f}")
    print(f"4) 峰 {sh['global_peak_age']} 岁 {sh['global_peak']:.0f}；谷 "
          f"{sh['global_trough_age']} 岁 {sh['global_trough']:.0f}；"
          f"峰谷比 {sh['peak_to_trough']:.2f}")
    print(f"   衣 peak {sh['clothing_peak_age']}  4岁/23岁 {sh['clothing_4_vs_23']:+.1f}%")
    print(f"   教 peak {sh['education_peak_age']}  0–2 max {sh['education_0_2_max']:.0f}")
    print(f"   医 85 {sh['health_85']:.0f}  0 {sh['health_0']:.0f}  "
          f"单调 {sh['health_monotone_23_85']}  min dip {sh['health_min_dip_pct']:+.2f}%")
    print(f"   住 peak {sh['housing_peak_age']}  峰后单调 {sh['housing_monotone_after_peak']}  "
          f"max rise {sh['housing_max_rise_after_peak_pct']:+.2f}%")
    print(f"   食 85 {sh['food_85']:.0f} ≤ 45 {sh['food_45']:.0f} "
          f"{sh['food_85'] <= sh['food_45']}")
    hh = chk["household"]
    print(f"6) 三口之家 2·c(35)+c(5) = 2×{hh['father']:.0f}+{hh['child']:.0f} = "
          f"{hh['total']:.0f}；基准 3·h(35) = {hh['bench_total_3h']:.0f}；"
          f"偏差 {hh['attr_vs_total_pct']:+.2f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--constructed-pop", action="store_true")
    ap.add_argument("--diag", action="store_true")
    ap.add_argument("--no-sensitivity", action="store_true")
    args = ap.parse_args()

    pop = get_pop_weights(args.constructed_pop)
    full, w, dbg = build(pop=pop)
    chk = checks(full, w, dbg)
    tot = chk["total"]

    write_csv(full, tot)
    scen_store, scen_def = write_scenarios(full, w)
    write_diff(full, tot)
    write_diff_v2v3(full, tot)
    write_diff_v3v4(full, tot)

    sens = ({"kindergarten": {}, "a5": {}, "summary": {}}
            if args.no_sensitivity else build_sensitivity(pop))
    if not args.no_sensitivity:
        (DATA / "sensitivity_kindergarten.json").write_text(
            json.dumps(sens["kindergarten"], ensure_ascii=False, indent=1),
            encoding="utf-8")
        (DATA / "sensitivity_a5.json").write_text(
            json.dumps(sens["a5"], ensure_ascii=False, indent=1), encoding="utf-8")
    ltc = build_longtermcare(pop, full, w)
    (DATA / "sensitivity_longtermcare.json").write_text(
        json.dumps(ltc, ensure_ascii=False, indent=1), encoding="utf-8")

    glide = ({"variants": {}} if args.no_sensitivity
             else build_retirement_glide(pop, base_tot=tot))
    if not args.no_sensitivity:
        (DATA / "sensitivity_retirement_glide.json").write_text(
            json.dumps(glide, ensure_ascii=False, indent=1), encoding="utf-8")

    doc = build_json(full, w, chk, dbg, scen_store, scen_def, sens, ltc,
                     glide if not args.no_sensitivity else None)
    (DATA / "shanghai_lifecycle.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    print("=" * 78)
    print("上海 0–85 岁消费生命周期 — v4 重建完成（D 复核后四处再改）")
    print("=" * 78)
    pp = dbg["pop_params"]
    if "child_base" in pp:
        print(f"人口权重：构造 P1  child_base={pp['child_base']:.4f} old_tau={pp['old_tau']:.3f}")
    else:
        print(f"人口权重：实测 {pp['source']}（{pp['year']}，{pp['total']:,.0f} 人）")
    print(f"分档：0-14 {w[:15].sum()*100:.2f}%  15-59 {w[15:60].sum()*100:.2f}%  "
          f"60+ {w[60:].sum()*100:.2f}%")
    if args.diag:
        _print_diag(chk, dbg)
    print("\n分段均值（新）：")
    for lo, hi, name, _ in STAGES:
        print(f"  {name:6s} {lo:2d}-{hi:2d}: {tot[lo:hi+1].mean():8.0f}")
    print("\n输出：data/shanghai_lifecycle.{csv,json}, _scenarios.csv, "
          "rebuild_diff{,_stages,_v2_v3,_v3_v4}.csv, sensitivity_*.json")


if __name__ == "__main__":
    main()
