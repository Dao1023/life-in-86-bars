#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pop_sensitivity.py — 只读诊断：把 build_lifecycle 的构造人口权重换成真实权重，
量化对模型的影响。不写 data/shanghai_lifecycle.*（不调用 main()）。

输出：
  raw/pop_sensitivity.json   四段份额 + 加权均值 + 分段修正幅度
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import build_lifecycle as bl  # noqa: E402

DATA = ROOT / "data"
RAW = ROOT / "raw"


def load_csv(fn):
    rows = list(csv.DictReader(open(DATA / fn, encoding="utf-8-sig")))
    P = {int(r["age"]): float(r["population"]) for r in rows}
    return P


def vec(P, ages=bl.AGES):
    """把 0–100 的单岁人口压到 0–85（86+ 并入 85），再归一。"""
    v = np.array([P.get(int(a), 0.0) for a in ages], dtype=float)
    tail = sum(P.get(a, 0.0) for a in range(86, 101))
    v[-1] += tail                      # 85 岁档吸收 86+
    return v / v.sum()


def band(w):
    return dict(p0_14=float(w[0:15].sum()), p15_59=float(w[15:60].sum()),
                p60=float(w[60:].sum()), p65=float(w[65:].sum()))


def main():
    P20 = load_csv("shanghai_pop_age_2020_census.csv")
    P25 = load_csv("shanghai_pop_age_2025.csv")

    # 基准模型（构造权重）
    full0, w0, dbg = bl.build()
    tot0 = full0.sum(1)

    variants = {
        "construct": w0,
        "census2020": vec(P20),
        "model2025": vec(P25),
    }

    out = {"baseline_weighted_total": float((w0 * tot0).sum()),
           "anchor": bl.TOTAL_ANCHOR, "variants": {}}

    for name, w in variants.items():
        m = float((w * tot0).sum())          # 同一 c(age) 下的加权均值
        out["variants"][name] = {
            "band": band(w),
            "weighted_mean_of_baseline_profile": m,
            "implied_rescale_pct": (bl.TOTAL_ANCHOR / m - 1) * 100,
        }

    # 用真实权重重跑整套标定：权重固定，其余流程不变
    for name in ("census2020", "model2025"):
        w = variants[name]
        old_pw, old_cal = bl.population_weights, bl.calibrate_population
        bl.population_weights = lambda cb, tau, _w=w: _w
        bl.calibrate_population = lambda: (0.0, 0.0)
        try:
            full1, _, _ = bl.build()
        finally:
            bl.population_weights, bl.calibrate_population = old_pw, old_cal
        t1 = full1.sum(1)
        stages = {}
        for lo, hi, label, _ in bl.STAGES:
            a0 = tot0[lo:hi + 1].mean()
            a1 = t1[lo:hi + 1].mean()
            stages[label] = {"base": float(a0), "new": float(a1),
                             "pct": float((a1 / a0 - 1) * 100)}
        out["variants"][name]["recalibrated"] = {
            "weighted_total": float((w * t1).sum()),
            "ages_23_69_level_pct": float((t1[23:70].mean() / tot0[23:70].mean() - 1) * 100),
            "stages": stages,
            "peak_age": int(np.argmax(t1)), "peak": float(t1.max()),
            "age85": float(t1[85]),
        }

    RAW.mkdir(exist_ok=True)
    (RAW / "pop_sensitivity.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"构造权重加权均值 {out['baseline_weighted_total']:.0f}（锚 {bl.TOTAL_ANCHOR:.0f}）")
    for name, d in out["variants"].items():
        b = d["band"]
        print(f"\n[{name}] 0-14 {b['p0_14']*100:.2f}%  15-59 {b['p15_59']*100:.2f}%  "
              f"60+ {b['p60']*100:.2f}%  65+ {b['p65']*100:.2f}%")
        print(f"  同 c(age) 加权均值 {d['weighted_mean_of_baseline_profile']:.0f} "
              f"→ 需整体 {'上调' if d['implied_rescale_pct']>0 else '下调'} "
              f"{abs(d['implied_rescale_pct']):.2f}%")
        if "recalibrated" in d:
            r = d["recalibrated"]
            print(f"  重跑标定：23-69 段水平 {r['ages_23_69_level_pct']:+.2f}%，"
                  f"峰 {r['peak_age']} 岁 {r['peak']:.0f}，85 岁 {r['age85']:.0f}")
            for k, v in r["stages"].items():
                print(f"    {k:6s} {v['base']:7.0f} → {v['new']:7.0f}  ({v['pct']:+.2f}%)")
    print("\nwritten raw/pop_sensitivity.json")


if __name__ == "__main__":
    main()
