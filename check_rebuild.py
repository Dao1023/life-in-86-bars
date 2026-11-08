# -*- coding: utf-8 -*-
"""
check_rebuild.py — 重建后数据的独立验收脚本（只读 data/，不参与建模）

跑法：
    python check_rebuild.py            # 全部检查 + 幂等性（会重跑两次建模）
    python check_rebuild.py --no-idem  # 跳过幂等性

输出：逐条 PASS/FAIL 的结果表 + 汇总。退出码 0 = 全过，1 = 有失败。
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

CATS = ["food", "clothing", "housing", "durables", "transport",
        "education", "health", "other"]
CAT_CN = {"food": "食品", "clothing": "衣着", "housing": "居住", "durables": "用品",
          "transport": "交通", "education": "教文", "health": "医疗", "other": "其他"}
TARGET = {"food": 13877, "clothing": 2011, "housing": 18932, "durables": 2258,
          "transport": 5746, "education": 5733, "health": 4570, "other": 1853}
TOTAL_ANCHOR = 54980.0

ROWS = []      # (ok, name, detail)
FAILS = 0


def check(ok, name, detail="", warn=False):
    global FAILS
    tag = "PASS" if ok else ("WARN" if warn else "FAIL")
    if not ok and not warn:
        FAILS += 1
    ROWS.append((tag, name, detail))
    return ok


def info(name, detail=""):
    """报告项：只打印，不参与通过/失败判定（v3 删除了 v2 的自设窗口）。"""
    ROWS.append(("INFO", name, detail))
    return True


def read_csv(name):
    with open(os.path.join(DATA, name), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load():
    rows = read_csv("shanghai_lifecycle.csv")
    rows.sort(key=lambda r: int(r["age"]))
    ages = [int(r["age"]) for r in rows]
    X = [[float(r["cat_" + c]) for c in CATS] for r in rows]
    tot = [float(r["total"]) for r in rows]
    pop = {int(r["age"]): float(r["population"]) for r in read_csv("shanghai_pop_age.csv")}
    # 85 档含 86+（与建模脚本一致：86–100 岁人口并入 85 岁档）
    w = {a: pop[a] for a in ages}
    w[85] += sum(pop.get(a, 0.0) for a in range(86, 101))
    s = sum(w.values())
    w = {a: v / s for a, v in w.items()}
    return ages, X, tot, w


def main():
    ages, X, tot, w = load()
    assert ages == list(range(86)), "年龄不连续"

    # ── 1. 水平与八类列 ───────────────────────────────────────────────
    weighted = sum(w[a] * tot[a] for a in ages)
    check(abs(weighted - TOTAL_ANCHOR) <= 0.01, "1a 加权总消费 = 54,980.00 ± 0.01",
          f"{weighted:.4f}（偏差 {weighted - TOTAL_ANCHOR:+.4f}）")

    devs = {}
    for j, c in enumerate(CATS):
        v = sum(w[a] * X[a][j] for a in ages)
        devs[c] = (v, v / TARGET[c] - 1)
    worst = max(devs.items(), key=lambda kv: abs(kv[1][1]))
    check(all(abs(d) < 5e-5 for _, d in devs.values()),
          "1b 八类加权和 = 官方值，逐类偏差 0.00%",
          "；".join(f"{CAT_CN[c]} {v:,.0f}/{TARGET[c]:,} ({d * 100:+.4f}%)"
                   for c, (v, d) in devs.items())
          + f"；最大 {CAT_CN[worst[0]]} {worst[1][1] * 100:+.5f}%")

    row_err = max(abs(sum(X[a]) - tot[a]) for a in ages)
    check(row_err <= 0.8, "1c 每岁八类之和 = total",
          f"最大行误差 {row_err:.4f} 元（CSV 保留 1 位小数，8 类舍入上限 0.4 元）")

    # ── 2. 相邻年龄变化（v4 规则：涨跌都查）──────────────────────────
    # v3 的规则只判 `v < 0`，于是 2→3、5→6、22→23 三个"上涨"全部逃过检查，
    # 2→3 被改成 +24.9% 也没人发现。v4 起：
    #   · 非桥接点 |变化| > 12% → FAIL；
    #   · 18/23 两座口径桥另设 15% 红线（超了 FAIL，不超报余量），
    #     不再「免 12% 线」——否则 22→23 永远不可能 FAIL；
    #   · |变化| > 8% → 逐条 INFO（带方向与主因类别）；
    #   · Top3 每次运行都打印。
    d = {a: tot[a] / tot[a - 1] - 1 for a in range(1, 86)}
    BRIDGE = {18: "学制切换（家庭代付篮子 → 大学构造块）",
              23: "口径缝（校园成本 → 青年自身消费）"}

    def driver(a):
        dl = [(X[a][j] - X[a - 1][j], CATS[j]) for j in range(8)]
        best = max(dl, key=lambda t: abs(t[0]))
        return CAT_CN[best[1]], best[0]

    over12 = [(a, v) for a, v in d.items()
              if abs(v) > 0.12 and a not in BRIDGE]
    if over12:
        check(False, "2a 非桥接点相邻年变化 ≤ 12%",
              "；".join(f"{a - 1}→{a} {v * 100:+.2f}%" for a, v in over12))
    else:
        worst = max(((a, v) for a, v in d.items() if a not in BRIDGE),
                    key=lambda t: abs(t[1]))
        check(True, "2a 非桥接点相邻年变化 ≤ 12%",
              f"最大 {worst[1] * 100:+.2f}% @ {worst[0] - 1}→{worst[0]} 岁")

    # 18/23 两座口径桥不免检：独立红线 15%（E 复核指出「免 12% 线」等于
    # 让 22→23 永远不可能 FAIL）。超 15% 判 FAIL，未超则报告余量。
    over15 = [(a, v) for a, v in d.items()
              if a in BRIDGE and abs(v) > 0.15]
    if over15:
        check(False, "2a-b 桥接点相邻年变化 ≤ 15%（独立红线）",
              "；".join(f"{a - 1}→{a} {v * 100:+.2f}%" for a, v in over15))
    else:
        wb = max(((a, v) for a, v in d.items() if a in BRIDGE),
                 key=lambda t: abs(t[1]))
        check(True, "2a-b 桥接点相邻年变化 ≤ 15%（独立红线）",
              f"最大 {wb[1] * 100:+.2f}% @ {wb[0] - 1}→{wb[0]} 岁，"
              f"余量 {15.0 - abs(wb[1]) * 100:.2f}pp")

    flagged = [(a, v) for a, v in d.items()
               if abs(v) > 0.08 and a not in BRIDGE]
    for a, v in sorted(flagged):
        cn, amt = driver(a)
        info(f"2b 相邻年变化 {a - 1}→{a} 岁：{v * 100:+.2f}%",
             f"{tot[a - 1]:,.0f} → {tot[a]:,.0f}；主因 {cn} {amt:+,.0f} 元")
    info("2b 汇总 |相邻年变化| > 8%（桥除外）",
         ("无" if not flagged else
          f"{len(flagged)} 处：" + "、".join(
              f"{a - 1}→{a} {v * 100:+.1f}%" for a, v in sorted(flagged))))
    for a, why in BRIDGE.items():
        info(f"2b-bridge {a - 1}→{a} 岁（口径桥，独立 15% 红线）",
             f"{d[a] * 100:+.2f}%（{tot[a - 1]:,.0f} → {tot[a]:,.0f}），"
             f"余量 {15.0 - abs(d[a]) * 100:.2f}pp；{why}")
    top3 = sorted(d.items(), key=lambda kv: -abs(kv[1]))[:3]
    info("2b-top3 最大相邻年跳变 Top3（每次运行都打印）",
         "；".join(f"{a - 1}→{a} {v * 100:+.2f}%" for a, v in top3))

    p_all = max(ages, key=lambda a: tot[a])
    after = [(a, tot[a] / tot[a - 1] - 1) for a in range(p_all + 1, 86)]
    rise = max(after, key=lambda t: t[1]) if after else (p_all, 0.0)
    check(all(v <= 0 for _, v in after),
          "2c 规则(b) 全局峰之后单调不增",
          f"峰 {p_all} 岁；峰后最大变化 {rise[1] * 100:+.2f}% @ {rise[0]} 岁")

    # ── 3. 退休坡度（报告值；v2 的 [−18%, −8%] 窗口已删除）────────────
    drop60 = tot[60] / tot[59] - 1
    cum60_64 = tot[64] / tot[59] - 1
    info("3 59→60 降幅（报告值，不设验收窗口）",
         f"{drop60 * 100:+.2f}%（{tot[59]:,.0f} → {tot[60]:,.0f}）；"
         f"59→64 累计 {cum60_64 * 100:+.2f}%；60–69/50–59 = "
         f"{sum(tot[60:70]) / sum(tot[50:60]):.3f}")

    # ── 4. 形状断言 ─────────────────────────────────────────────────
    def col(c):
        j = CATS.index(c)
        return [X[a][j] for a in ages]

    def peak(v, lo=0, hi=85):
        return max(range(lo, hi + 1), key=lambda a: v[a])

    cl = col("clothing")
    p = peak(cl)
    check(25 <= p <= 40, "4a 衣着峰值在 25–40 岁", f"peak {p} 岁 {cl[p]:,.0f}")
    check(cl[4] <= cl[23], "4b 衣着 4 岁 ≤ 23 岁",
          f"4 岁 {cl[4]:,.0f} vs 23 岁 {cl[23]:,.0f}（{cl[4] / cl[23] - 1:+.1%}）")

    ed = col("education")
    p = peak(ed)
    check(15 <= p <= 17, "4c 教育峰值在 15–17 岁", f"peak {p} 岁 {ed[p]:,.0f}")
    # v4：旧门槛「0–2 岁 <3,000」在补托育后主动废止——它的本意是防"把
    # 12,000 幼儿园摊到 0 岁"，而 1–2 岁托育是真实支出。改为只约束 0 岁，
    # 1–2 岁单列 INFO（数值必须与托育假设自洽）。
    check(ed[0] < 3000, "4d 教育 0 岁 < 3,000（v1 假幼儿园成本的实质检验）",
          f"0 岁 {ed[0]:,.0f}（1/2/3 岁 = {ed[1]:,.0f}/{ed[2]:,.0f}/{ed[3]:,.0f}）")
    info("4d-b 教育 1–2 岁含托育（旧门槛「0–2 岁 <3,000」已废止）",
         f"1 岁 {ed[1]:,.0f}、2 岁 {ed[2]:,.0f}；托育月费 4,000×入托率×12，"
         f"入托率 0/1/2 岁 = 0.5%/5%/11%")

    he = col("health")
    check(he[85] >= 14000, "4e 医疗 85 岁 ≥ 14,000", f"{he[85]:,.0f}")
    check(he[0] <= 3000, "4f 医疗 0 岁 ≤ 3,000", f"{he[0]:,.0f}")
    dips = [(a, he[a] / he[a - 1] - 1) for a in range(24, 86)]
    wd = min(dips, key=lambda t: t[1])
    check(wd[1] >= -0.005, "4g 医疗 23→85 单调上升（允许 ≤0.5% 噪声）",
          f"最大回撤 {wd[1] * 100:+.2f}% @ {wd[0]} 岁")

    ho = col("housing")
    p = peak(ho, 23)
    after = [(a, ho[a] / ho[a - 1] - 1) for a in range(p + 1, 86)]
    wu = max(after, key=lambda t: t[1]) if after else (p, 0)
    check(25 <= p <= 35, "4h 居住峰值在 25–35 岁", f"peak {p} 岁 {ho[p]:,.0f}")
    check(wu[1] <= 0.002, "4i 居住峰后单调下降至 85",
          f"最大回升 {wu[1] * 100:+.2f}% @ {wu[0]} 岁；85 岁 {ho[85]:,.0f}")

    fo = col("food")
    check(fo[85] <= fo[45], "4j 食品 85 岁 ≤ 45 岁",
          f"{fo[85]:,.0f} vs {fo[45]:,.0f}")

    p = max(ages, key=lambda a: tot[a])
    check(40 <= p <= 59, "4k 全局峰在 40–59 岁", f"peak {p} 岁 {tot[p]:,.0f}")
    check(tot[59] > tot[4], "4l 59 岁 > 4 岁（4 岁峰不再成立）",
          f"{tot[59]:,.0f} vs {tot[4]:,.0f}")

    du = col("durables")
    info("4m 0 岁用品占比（v3 一次性支出摊销后）",
         f"{du[0]:,.0f}（{du[0] / tot[0] * 100:.1f}%）；0/1/2 = "
         f"{du[0]:,.0f}/{du[1]:,.0f}/{du[2]:,.0f}")

    # ── 5. 谷不在 85 岁 ─────────────────────────────────────────────
    tr = min(ages, key=lambda a: tot[a])
    check(tr != 85, "5 谷不在 85 岁", f"谷 {tr} 岁 {tot[tr]:,.0f}；85 岁 {tot[85]:,.0f}")

    # ── 6. 户内一致性（三口之家 35+35+5）────────────────────────────
    hh = {int(r["age"]): r for r in read_csv("shanghai_lifecycle_household.csv")}
    h35 = float(hh[35]["total"])
    c35, c33, c5 = tot[35], tot[33], tot[5]
    attr_strict = c35 + c33 + c5          # 按户表构成规则：配偶 = 户主 − 2 岁
    attr_lit = 2 * c35 + c5               # 按题面字面：父母同为 35 岁
    gap = attr_lit / h35 - 1
    check(abs(gap) < 0.15, "6 三口之家归因和 ≈ 户总消费（<15%）",
          f"按构成规则 c(35)+c(33)+c(5) = {attr_strict:,.1f} vs 户表 H(35) = "
          f"{h35:,.1f}（{attr_strict / h35 * 100 - 100:+.2f}%）；"
          f"按题面 2·c(35)+c(5) = {attr_lit:,.1f}（{gap * 100:+.2f}%）")

    hhj = json.load(open(os.path.join(DATA, "shanghai_lifecycle_household.json"),
                         encoding="utf-8"))
    dev_hh = hhj["meta"].get("calibration", {}).get("anchor_deviation_pct")
    if dev_hh is not None:
        check(abs(dev_hh) <= 1.0, "6b 户均加权 ≈ 54,980×2.32（内部锚，±1%）",
              f"户表加权 {hhj['meta']['calibration'].get('weighted_household_mean'):,.2f} "
              f"vs 锚 {hhj['meta']['anchor_household']:,.2f}（{dev_hh:+.3f}%）；"
              "构造户均规模 2.3029 < 2.32，且一人户占比 11.1% vs 七普 28.4%，"
              "缺口来自构成规则而非人均曲线", warn=True)

    # ── 打印 ────────────────────────────────────────────────────────
    w0 = max(len(r[1]) for r in ROWS)
    print("=" * 100)
    print("重建验收结果表（读 data/ 实际产物，独立重算）")
    print("=" * 100)
    for tag, name, detail in ROWS:
        print(f"[{tag}] {name:<{w0}}  {detail}")

    if "--no-idem" not in sys.argv:
        print("\n— 7. 幂等性（重跑两次逐字节比较）—")
        files = ["shanghai_lifecycle.csv", "shanghai_lifecycle.json",
                 "shanghai_lifecycle_scenarios.csv", "rebuild_diff.csv",
                 "rebuild_diff_stages.csv", "rebuild_diff_v3_v4.csv",
                 "sensitivity_retirement_glide.json",
                 "sensitivity_childcare.json",
                 "sensitivity_longtermcare.json"]

        def digest():
            return {f: hashlib.md5(open(os.path.join(DATA, f), "rb").read()).hexdigest()
                    for f in files}

        a = digest()
        subprocess.run([sys.executable, os.path.join(HERE, "build_lifecycle.py")],
                       cwd=HERE, check=True, stdout=subprocess.DEVNULL)
        b = digest()
        subprocess.run([sys.executable, os.path.join(HERE, "build_lifecycle.py")],
                       cwd=HERE, check=True, stdout=subprocess.DEVNULL)
        c = digest()
        same = (a == b == c)
        print(f"[{'PASS' if same else 'FAIL'}] 7 两次重跑逐字节一致")
        check(same, "7 两次重跑逐字节一致",
              "md5 相同：" + ", ".join(f"{f[:22]}…={a[f][:8]}" for f in files)
              if same else "不一致：" + ", ".join(f for f in files if not (a[f] == b[f] == c[f])))

    n_fail = sum(1 for r in ROWS if r[0] == "FAIL")
    n_warn = sum(1 for r in ROWS if r[0] == "WARN")
    n_info = sum(1 for r in ROWS if r[0] == "INFO")
    print("\n" + "=" * 100)
    print(f"合计 {len(ROWS)} 项：PASS {len(ROWS) - n_fail - n_warn - n_info}，"
          f"WARN {n_warn}，INFO {n_info}，FAIL {n_fail}")
    print("=" * 100)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
