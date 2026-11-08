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

    html = TPL.read_text(encoding="utf-8")
    payload = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("/*__DATA__*/", payload)
    for k, v in tok.items():
        html = html.replace(k, v)

    leftover = [t for t in ("__PEAK__", "__TROUGH__", "__D18__", "__H85SH__") if t in html]
    if leftover:
        sys.exit(f"[index] 占位符未替换：{leftover}")

    OUT.write_text(html, encoding="utf-8", newline="\n")
    print(f"[index] {OUT.name}  {len(html.encode('utf-8')):,} B")
    print(f"[index] 峰 {ages[i_peak]} 岁 {num(total[i_peak])} · 谷 {ages[i_trough]} 岁 {num(total[i_trough])} · 峰谷比 {tok['__RATIO__']}")
    print(f"[index] 0–17 均值 {tok['__MEAN017__']} · 峰比 0–17 高 {tok['__UP017__']}% · 18 岁 {tok['__D18__']}% · 23 岁居住 {tok['__H23SH__']}%")


if __name__ == "__main__":
    main()
