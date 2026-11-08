# -*- coding: utf-8 -*-
"""生成仓库根目录的落地页 index.html。

    python tools/build_index.py

输入：tools/index.template.html + data/shanghai_lifecycle.json（只读）
输出：index.html（单文件、零依赖、可离线打开）

模板里的占位符：
- `/*__DATA__*/`  —— 整份 JSON（图表用）
- `__TOKEN__`      —— 首屏与文案里要现算的数字（避免硬编码后与数据脱节）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "tools" / "index.template.html"
DATA = ROOT / "data" / "shanghai_lifecycle.json"
OUT = ROOT / "index.html"


def main() -> None:
    if not TPL.exists():
        sys.exit(f"[index] 缺少模板：{TPL}")
    if not DATA.exists():
        sys.exit(f"[index] 缺少数据：{DATA}")

    d = json.loads(DATA.read_text(encoding="utf-8"))
    ages, total, abs_ = d["ages"], d["total"], d["absolute"]
    n = len(ages)
    assert n == len(total) and ages[0] == 0, "数据应为 0 岁起逐年序列"

    i_peak = max(range(n), key=lambda i: total[i])
    i_trough = min(range(n), key=lambda i: total[i])
    mean_0_17 = sum(total[i] for i in range(0, 18)) / 18
    i18, i17 = ages.index(18), ages.index(17)
    i23, i22 = ages.index(23), ages.index(22)
    i59, i60, i64 = ages.index(59), ages.index(60), ages.index(64)
    h85 = abs_["housing"][i23]

    def num(x: float) -> str:
        return f"{int(x + 0.5):,}"

    def pct(x: float) -> str:
        return f"{x * 100:+.1f}".replace("+", "+").replace("-", "−")

    tok = {
        "__PEAK__": num(total[i_peak]),
        "__PEAK_AGE__": str(ages[i_peak]),
        "__TROUGH__": num(total[i_trough]),
        "__TROUGH_AGE__": str(ages[i_trough]),
        "__RATIO__": f"{total[i_peak] / total[i_trough]:.2f}",
        "__MEAN017__": num(mean_0_17),
        "__UP017__": f"{(total[i_peak] / mean_0_17 - 1) * 100:.0f}",
        "__T017__": num(total[i17]),
        "__T018__": num(total[i18]),
        "__D18__": f"{(total[i18] / total[i17] - 1) * 100:.1f}".replace("-", "−"),
        "__T023__": num(total[i23]),
        "__D23__": f"{(total[i23] / total[i22] - 1) * 100:+.1f}",
        "__H23__": num(h85),
        "__H23SH__": f"{(h85 / total[i23]) * 100:.1f}",
        "__D59_60__": f"{(total[i60] / total[i59] - 1) * 100:.1f}".replace("-", "−"),
        "__D59_64__": f"{(total[i64] / total[i59] - 1) * 100:.1f}".replace("-", "−"),
        "__H85__": num(abs_["health"][ages.index(85)]),
        "__H85SH__": f"{(abs_['health'][ages.index(85)] / total[ages.index(85)]) * 100:.1f}",
        "__VERSION__": str(d.get("meta", {}).get("version", "")),
        "__H0__": num(abs_["health"][0]),
        "__H0SH__": f"{(abs_['health'][0] / total[0]) * 100:.1f}",
        "__W0__": f"{total[0] / 10000:.1f}",
        "__W17__": f"{total[i17] / 10000:.1f}",
        "__LTC__": num(d.get("meta", {}).get("medical_85_split", {}).get("home_care_addon", 0) or 0),
    }

    # 新增段落（05 三十岁 / 07 空巢 / 08 退休 / 09 老年）全部现算，不写字面金额
    i30, i39 = ages.index(30), ages.index(39)
    i50, i85 = ages.index(50), ages.index(85)
    for a, k in ((30, "30"), (39, "39"), (50, "50"), (59, "59"), (64, "64"), (85, "85")):
        tok["__T%s__" % k] = num(total[ages.index(a)])
    for a, k in ((30, "30"), (39, "39"), (50, "50"), (59, "59")):
        tok["__H%s__" % k] = num(abs_["housing"][ages.index(a)])
        tok["__H%sSH__" % k] = f"{(abs_['housing'][ages.index(a)] / total[ages.index(a)]) * 100:.1f}"
    tok["__E30__"] = num(abs_["education"][i30])
    tok["__E39__"] = num(abs_["education"][i39])
    tok["__DE3039__"] = f"{(abs_['education'][i39] / abs_['education'][i30] - 1) * 100:+.1f}"
    tok["__D3039__"] = f"{(total[i39] / total[i30] - 1) * 100:+.1f}"
    tok["__D5059__"] = f"{(total[i59] / total[i50] - 1) * 100:.1f}".replace("-", "−")
    tok["__DOWN85__"] = f"{(1 - total[i85] / total[i_peak]) * 100:.1f}"

    # 展示口径：数据文件里的 meta.title 不动，注入时覆盖成对外标题
    d.setdefault("meta", {})["title"] = "一个中国城市人的一生：0–85 岁逐年消费结构（以上海为例）"

    html = TPL.read_text(encoding="utf-8")
    payload = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("/*__DATA__*/", payload)
    for k, v in tok.items():
        html = html.replace(k, v)

    leftover = [t for t in ("__PEAK__", "__TROUGH__", "__D18__", "__H85SH__",
                            "__H30SH__", "__H39SH__", "__D5059__", "__D3039__", "__DE3039__", "__T85__")
                if t in html]
    if leftover:
        sys.exit(f"[index] 占位符未替换：{leftover}")

    # 叙事段连续性自检：9 段的 band 必须无洞覆盖 0–85（0–2 与 0–17 重叠是特写，允许）
    bands = [(int(a), int(b)) for a, b in re.findall(r"band:\s*\[(\d+),\s*(\d+)\]", TPL.read_text(encoding="utf-8"))]
    if not bands:
        sys.exit("[index] 解析不到 band，段数自检失败")
    covered = [False] * 86
    for lo, hi in bands:
        for a in range(lo, hi + 1):
            if 0 <= a <= 85:
                covered[a] = True
    holes = [a for a in range(86) if not covered[a]]
    print("[index] 段数 %d · 区间 %s" % (len(bands), " ".join("%d–%d" % b for b in bands)))
    print("[index] 覆盖检查：union = [0,85] %s" % ("OK" if not holes else "缺口 %s" % holes))
    if holes:
        sys.exit("[index] 叙事段有缺口：%s" % holes)

    OUT.write_text(html, encoding="utf-8", newline="\n")
    print(f"[index] {OUT.name}  {len(html.encode('utf-8')):,} B")
    print(f"[index] 峰 {ages[i_peak]} 岁 {num(total[i_peak])} · 谷 {ages[i_trough]} 岁 {num(total[i_trough])} · 峰谷比 {tok['__RATIO__']}")
    print(f"[index] 0–17 均值 {tok['__MEAN017__']} · 峰比 0–17 高 {tok['__UP017__']}% · 18 岁 {tok['__D18__']}% · 23 岁居住 {tok['__H23SH__']}%")


if __name__ == "__main__":
    main()
