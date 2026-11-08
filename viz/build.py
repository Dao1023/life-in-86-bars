#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 viz/lifecycle.html：把数据注入 viz/template.html 的 /*__DATA__*/。

用法：
    python build.py                      # 在 viz/ 目录
    python viz/build.py                  # 在项目根目录
    python build.py --household path.json  # 用临时文件覆盖家庭口径数据（自检用）

数据来源：
    data/shanghai_lifecycle.json            必读，人均口径（0–85 岁）
    data/shanghai_lifecycle_household.json  可选，家庭口径（户主年龄 22–85）；
                                            不存在时向页面注入 null，页面自动隐藏「口径」开关。

设计要点：
- 幂等：重复运行只覆盖同一份输出，不做任何累积性修改。
- 数据是唯一真源：页面里所有数字都由内联 JSON 在浏览器端计算。
- 不联网，不依赖第三方库。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TEMPLATE = HERE / "template.html"
DATA = ROOT / "data" / "shanghai_lifecycle.json"
DATA_HH = ROOT / "data" / "shanghai_lifecycle_household.json"
SENS_FILES = {
    "kindergarten": ROOT / "data" / "sensitivity_kindergarten.json",
    "a5": ROOT / "data" / "sensitivity_a5.json",
    "ltc": ROOT / "data" / "sensitivity_longtermcare.json",
    "glide": ROOT / "data" / "sensitivity_retirement_glide.json",
    "childcare": ROOT / "data" / "sensitivity_childcare.json",
}


def sens_variants(obj: dict, label: str) -> dict:
    """两种 schema：{variant_id: {...}} 或 {title, note, variants: {variant_id: {...}}}"""
    if isinstance(obj.get("variants"), dict):
        return obj["variants"]
    return {k: v for k, v in obj.items() if isinstance(v, dict)}
OUT = HERE / "lifecycle.html"

PLACEHOLDER = "/*__DATA__*/"
STAMP = "__GENERATED_AT__"

REQUIRED_TOP = ["meta", "categories", "ages", "absolute", "share", "total",
                "stages", "annotations", "sources", "scenarios"]


def fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print("[build] ERROR: " + msg, file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path, label: str) -> dict:
    if not path.exists():
        fail("找不到%s: %s" % (label, path))
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        fail("%s JSON 解析失败: %s (line %d col %d)" % (label, e.msg, e.lineno, e.colno))


def check_common(data: dict, label: str, ages_must_be_0_85: bool) -> list[str]:
    """人均与家庭共用的结构检查。"""
    warns: list[str] = []
    for k in REQUIRED_TOP:
        if k not in data:
            fail("%s 缺少顶层字段: %s" % (label, k))

    ages = data["ages"]
    n = len(ages)
    if ages_must_be_0_85 and (n != 86 or ages[0] != 0 or ages[-1] != 85):
        fail("ages 期望 0..85 共 86 项，实际 %d 项（%s..%s）" % (n, ages[0], ages[-1]))
    if not ages_must_be_0_85:
        if n < 10:
            fail("%s ages 只有 %d 项" % (label, n))
        if n > 1 and any(ages[i + 1] != ages[i] + 1 for i in range(n - 1)):
            fail("%s ages 不是逐年连续（%s..%s）" % (label, ages[0], ages[-1]))
        if not (0 <= ages[0] <= ages[-1] <= 110):
            fail("%s ages 超出合理范围（%s..%s）" % (label, ages[0], ages[-1]))

    cats = data["categories"]
    if len(cats) != 8:
        fail("%s categories 期望 8 类，实际 %d 类" % (label, len(cats)))

    for c in cats:
        if c["id"] not in data["absolute"]:
            fail("%s absolute 缺少类别: %s" % (label, c["id"]))
        if len(data["absolute"][c["id"]]) != n:
            fail("%s absolute.%s 长度不是 %d" % (label, c["id"], n))
    if len(data["total"]) != n:
        fail("%s total 长度不是 %d" % (label, n))

    worst = 0.0
    for i in range(n):
        s = sum(data["absolute"][c["id"]][i] for c in cats)
        t = data["total"][i]
        if t:
            worst = max(worst, abs(s - t) / t * 100)
    if worst > 0.01:
        warns.append("%s 八类之和与 total 的最大相对误差 %.4f%%，超过 0.01%%" % (label, worst))

    for key in ("low", "base", "high"):
        sc = (data.get("scenarios") or {}).get(key)
        if not sc:
            fail("%s scenarios 缺少情景: %s" % (label, key))
        if len(sc["total"]) != n:
            fail("%s scenarios.%s.total 长度不是 %d" % (label, key, n))
        for c in cats:
            arr = (sc.get("absolute") or {}).get(c["id"])
            if arr is None or len(arr) != n:
                fail("%s scenarios.%s.absolute.%s 缺失或长度不是 %d" % (label, key, c["id"], n))

    return warns


def check_person(data: dict) -> list[str]:
    warns = check_common(data, "人均数据", ages_must_be_0_85=True)
    meta = data["meta"]
    for k in ("peak_age", "peak_value", "trough_age", "trough_value", "weighted_mean"):
        if k not in meta:
            fail("meta 缺少字段: " + k)
    return warns


def check_household(data: dict) -> list[str]:
    warns = check_common(data, "家庭数据", ages_must_be_0_85=False)
    meta = data.get("meta") or {}
    if "household_size" not in meta and "anchor_household_size" not in meta:
        warns.append("家庭数据 meta 缺少 household_size / anchor_household_size")
    return warns


def check_sens(data: dict, n: int, cats: list, label: str) -> list[str]:
    """敏感性变体：key -> {label, total[86], absolute{cat:[86]}, ...}
    长护情景只改结构、不改总额，因此可以没有 total（此时跳过行和校验）。"""
    warns: list[str] = []
    for vid, v in sens_variants(data, label).items():
        if not isinstance(v, dict):
            fail("%s.%s 不是对象" % (label, vid))
        if "absolute" not in v:
            # 只有汇总统计的敏感性（如退休 glide 的 ρ_end 三档）：不画图，只做文字说明
            continue
        if v.get("total") is not None and len(v["total"]) != n:
            fail("%s.%s.total 长度不是 %d" % (label, vid, n))
        for c in cats:
            arr = v["absolute"].get(c["id"])
            if arr is None or len(arr) != n:
                fail("%s.%s.absolute.%s 缺失或长度不是 %d" % (label, vid, c["id"], n))
        if v.get("total") is None:
            continue
        worst = 0.0
        for i in range(n):
            s = sum(v["absolute"][c["id"]][i] for c in cats)
            t = v["total"][i]
            if t:
                worst = max(worst, abs(s - t) / t * 100)
        if worst > 0.01:
            warns.append("%s.%s 八类之和与 total 最大误差 %.4f%%" % (label, vid, worst))
    return warns


def main() -> None:
    ap = argparse.ArgumentParser(description="把数据注入模板，生成单文件页面")
    ap.add_argument("--household", default=None,
                    help="家庭口径 JSON 路径覆盖（默认 data/shanghai_lifecycle_household.json）")
    ap.add_argument("--out", default=None, help="输出路径覆盖（默认 viz/lifecycle.html）")
    ap.add_argument("--sens-kg", default=None, help="覆盖幼儿园敏感性数据路径（自检用）")
    ap.add_argument("--sens-a5", default=None, help="覆盖 A5 敏感性数据路径（自检用）")
    ap.add_argument("--sens-ltc", default=None, help="覆盖长护敏感性数据路径（自检用）")
    args = ap.parse_args()

    if not TEMPLATE.exists():
        fail("找不到模板: " + str(TEMPLATE))

    data = load_json(DATA, "人均数据")
    warns = check_person(data)

    hh_path = Path(args.household).resolve() if args.household else DATA_HH
    household = None
    if hh_path.exists():
        household = load_json(hh_path, "家庭数据")
        warns += check_household(household)
    elif args.household:
        fail("--household 指定的文件不存在: " + str(hh_path))

    sens = {}
    sens_paths = dict(SENS_FILES)
    if args.sens_kg:
        sens_paths["kindergarten"] = Path(args.sens_kg).resolve()
    if args.sens_a5:
        sens_paths["a5"] = Path(args.sens_a5).resolve()
    if args.sens_ltc:
        sens_paths["ltc"] = Path(args.sens_ltc).resolve()
    for key, path in sens_paths.items():
        if path.exists():
            obj = load_json(path, "%s 敏感性数据" % key)
            sens[key] = obj
            warns += check_sens(obj, len(data["ages"]), data["categories"], key)
            print("[build] sens.%-12s: %s" % (key, ", ".join(sens_variants(obj, key).keys())))
        else:
            sens[key] = None

    tpl = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in tpl:
        fail("模板里找不到占位符 " + PLACEHOLDER)

    # 展示口径（v5）：data/ 里的 meta.title 仍是旧标题，只在注入时覆盖，数据文件一个字节不动
    data["meta"]["title"] = "一个中国城市人的一生：0–85 岁逐年消费结构（以上海为例）"
    if household:
        household["meta"]["title"] = "上海家庭（中国城市·以上海为例）：户主年龄消费结构"

    payload_obj = {"person": data, "household": household, "sens": sens}
    payload = json.dumps(payload_obj, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    if "</script" in payload.lower():
        fail("数据里含 </script，注入后会破坏文档结构")

    out = tpl.replace(PLACEHOLDER, payload)

    now = _dt.datetime.now()
    out = out.replace(STAMP, now.strftime("%Y-%m-%d %H:%M"))
    if "__DATA__" in out or STAMP in out:
        fail("仍有未替换的占位符")

    out_path = Path(args.out).resolve() if args.out else OUT
    with open(out_path, "w", encoding="utf-8", newline=chr(10)) as fh:
        fh.write(out)

    size = out_path.stat().st_size
    if size > 2 * 1024 * 1024:
        fail("输出文件过大: %.2f MB（上限 2 MB）" % (size / 1048576))

    mtime = _dt.datetime.fromtimestamp(DATA.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    print("[build] template : %s" % TEMPLATE.name)
    print("[build] data     : %s  (%d bytes, mtime %s)" % (DATA.name, len(DATA.read_bytes()), mtime))
    if household is not None:
        hm = _dt.datetime.fromtimestamp(hh_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print("[build] household: %s  (%s, ages %s..%s, %d 项, mtime %s)"
              % (hh_path.name, "内置" if not args.household else "覆盖", household["ages"][0],
                 household["ages"][-1], len(household["ages"]), hm))
    else:
        print("[build] household: 未找到 %s，注入 null（页面隐藏「口径」开关）" % hh_path.name)
    for key in ("kindergarten", "a5", "ltc"):
        obj = sens.get(key)
        if obj:
            ids = list(obj.get("variants", obj).keys())
            print("[build] sens.%-12s: %s" % (key, ", ".join(sorted(ids))))
            if obj.get("note"):
                print("[build]   note: " + str(obj["note"])[:120])
        else:
            print("[build] sens.%-12s: 未找到 %s，页面隐藏该开关" % (key, sens_paths[key].name))
    print("[build] output   : %s  (%.1f KB)" % (out_path.name, size / 1024))
    print("[build] ages=%d cats=%d annotations=%d sources=%d stages=%d"
          % (len(data["ages"]), len(data["categories"]), len(data["annotations"]),
             len(data["sources"]), len(data["stages"])))
    cal = data["meta"]["calibration"]
    wte = cal.get("weighted_total_error_pct", cal.get("weighted_total_error", 0.0))
    print("[build] calibration: weighted_total_err=%.4f%% category_err_max=%.4f%% max_cell=%.2f%%"
          % (wte, cal.get("category_error_pct_max", 0.0), cal.get("max_cell_scaling_pct", 0.0)))
    for w in warns:
        print("[build] WARN: " + w)
    print("[build] OK -> %s" % out_path)


if __name__ == "__main__":
    main()
