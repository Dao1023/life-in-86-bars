# -*- coding: utf-8 -*-
"""生成社交分享卡片与站点图标。

    cd viz && python build_og.py

输入：../data/shanghai_lifecycle.json（只读）
输出：og-image.svg / og-image.png / favicon.svg / favicon-32.png / apple-touch-icon.png

设计约束
- 1200×630，左侧 60% 放字、右侧 40% 放堆叠柱剪影（无坐标轴、无注释文字，只有一个峰值标记）。
- 先按 2 倍尺寸绘制再 LANCZOS 下采样，保证缩到 300px 宽时标题与数字仍清楚。
- 全部图形走同一份显示列表（rect / line / text / circle），Pillow 与 SVG 两个后端共用，
  所以矢量稿与位图不会漂移。
- 无随机数、无时间戳：重复运行字节一致。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data" / "shanghai_lifecycle.json"

PAPER = "#FAF8F4"
INK = "#191817"
MUTED = "#6E675C"
FAINT = "#8A8378"
RULE = "#DCD5C7"

SERIF = "C:/Windows/Fonts/NotoSerifSC-VF.ttf"
SANS = "C:/Windows/Fonts/msyh.ttc"

W, H = 1200, 630
SS = 2  # 超采样倍数


# ---------------------------------------------------------------- 数据
def load():
    if not DATA.exists():
        sys.exit(f"[og] 找不到数据文件：{DATA}")
    d = json.loads(DATA.read_text(encoding="utf-8"))
    cats = d["categories"]
    ages = d["ages"]
    total = d["total"]
    abs_ = d["absolute"]
    meta = d.get("meta", {})
    peak_i = max(range(len(total)), key=lambda i: total[i])
    mean = meta.get("weighted_mean") or meta.get("anchor_total")
    return {
        "cats": cats,
        "ages": ages,
        "total": total,
        "abs": abs_,
        "peak_i": peak_i,
        "peak_age": ages[peak_i],
        "peak_v": total[peak_i],
        "mean": mean,
    }


# ---------------------------------------------------------------- 字体
_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(kind: str, size: int, ss: int = SS):
    key = (kind, size, ss)
    if key not in _font_cache:
        path = SERIF if kind == "serif" else SANS
        _font_cache[key] = ImageFont.truetype(path, size * ss, index=0)
    return _font_cache[key]


def text_width(s: str, kind: str, size: int) -> float:
    f = font(kind, size)
    box = f.getbbox(s)
    return (box[2] - box[0]) / SS


# ---------------------------------------------------------------- 显示列表
class Scene:
    """极简显示列表：同一个 ops 列表既画位图也导出 SVG。"""

    def __init__(self):
        self.ops = []

    def rect(self, x, y, w, h, fill, opacity=1.0):
        self.ops.append(("rect", x, y, w, h, fill, opacity))

    def line(self, x1, y1, x2, y2, color, width=1.0, opacity=1.0):
        self.ops.append(("line", x1, y1, x2, y2, color, width, opacity))

    def circle(self, cx, cy, r, fill, opacity=1.0):
        self.ops.append(("circle", cx, cy, r, fill, opacity))

    def text(self, x, y, s, kind, size, fill, anchor="lt", opacity=1.0):
        """anchor: l/m/r 横向 + t/m/b 纵向，如 'lt'、'rm'、'cm'。"""
        self.ops.append(("text", x, y, s, kind, size, fill, anchor, opacity))


def render_png(scene: Scene, path: Path, w=W, h=H, ss=SS):
    img = Image.new("RGB", (w * ss, h * ss), PAPER)
    dr = ImageDraw.Draw(img, "RGBA")
    for op in scene.ops:
        kind = op[0]
        if kind == "rect":
            _, x, y, ww, hh, fill, a = op
            dr.rectangle([x * ss, y * ss, (x + ww) * ss - 1, (y + hh) * ss - 1], fill=fill, width=0)
        elif kind == "line":
            _, x1, y1, x2, y2, color, lw, a = op
            dr.line([x1 * ss, y1 * ss, x2 * ss, y2 * ss], fill=color, width=max(1, int(round(lw * ss))))
        elif kind == "circle":
            _, cx, cy, r, fill, a = op
            dr.ellipse([(cx - r) * ss, (cy - r) * ss, (cx + r) * ss, (cy + r) * ss], fill=fill)
        elif kind == "text":
            _, x, y, s, fk, size, fill, anchor, a = op
            f = font(fk, size, ss)
            box = f.getbbox(s)
            tw, th = (box[2] - box[0]) / ss, (box[3] - box[1]) / ss
            ax, ay = anchor[0], anchor[1]
            if ax == "m":
                x -= tw / 2
            elif ax == "r":
                x -= tw
            if ay == "m":
                y -= th / 2
            elif ay == "b":
                y -= th
            dr.text((x * ss, y * ss - box[1]), s, font=f, fill=fill)
    img = img.resize((w, h), Image.LANCZOS) if ss != 1 else img
    # 128 色 + 无抖动：卡片是平涂色块，量化后肉眼无差，体积从 ~102 KB 降到 ~35 KB
    img = img.convert("RGB").quantize(colors=128, method=Image.MEDIANCUT, dither=Image.NONE)
    img.save(path, "PNG", optimize=True)


def render_svg(scene: Scene, path: Path, w=W, h=H):
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="{PAPER}"/>',
    ]
    esc = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}
    for op in scene.ops:
        kind = op[0]
        if kind == "rect":
            _, x, y, ww, hh, fill, a = op
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{ww:.2f}" height="{hh:.2f}" fill="{fill}"/>')
        elif kind == "line":
            _, x1, y1, x2, y2, color, lw, a = op
            out.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{lw}"/>'
            )
        elif kind == "circle":
            _, cx, cy, r, fill, a = op
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.2f}" fill="{fill}"/>')
        elif kind == "text":
            _, x, y, s, fk, size, fill, anchor, a = op
            fam = "Noto Serif SC, Songti SC, serif" if fk == "serif" else "Microsoft YaHei, sans-serif"
            weight = ' font-weight="700"' if fk == "serif" else ""
            anchor_map = {("l", "t"): "start", ("m", "t"): "middle", ("r", "t"): "end"}
            out.append(
                f'<text x="{x:.1f}" y="{y + size * 0.92:.1f}" font-family="{fam}" font-size="{size}"{weight} '
                f'fill="{fill}" text-anchor="{anchor_map.get((anchor[0], anchor[1]), "start")}">'
                + "".join(esc.get(ch, ch) for ch in s)
                + "</text>"
            )
    out.append("</svg>")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- OG 卡片
def build_og(d) -> Scene:
    sc = Scene()
    ages, total, abs_ = d["ages"], d["total"], d["abs"]
    cats = d["cats"]

    # 左栏
    L = 76
    sc.text(L, 62, "以上海为例 · 一线城市平均 · 2024 年价", "sans", 15, FAINT)
    sc.text(L, 104, "一个中国城市人，", "serif", 46, INK)
    sc.text(L, 164, "一生要花多少钱", "serif", 46, INK)
    sc.line(L, 246, L + 64, 246, INK, 2)
    sc.text(L, 266, "0–85 岁 · 8 类消费 · 元 / 人 / 年", "sans", 17, MUTED)

    big = f"{int(d['peak_v'] + 0.5):,}"   # 四舍五入到整数（Python 默认 banker rounding 会把 .5 抹成 64,414）
    sc.text(L - 2, 330, big, "serif", 82, INK)
    sc.text(L + text_width(big, "serif", 82) + 10, 386, "元 / 人 / 年", "sans", 16, MUTED)
    sc.text(L, 444, f"{d['peak_age']} 岁前后，一年的人均消费", "sans", 16, MUTED)

    # 右栏：堆叠柱剪影
    cx0, cx1 = 700, 1124
    base, top = 470, 128
    n = len(ages)
    step = (cx1 - cx0) / n
    barw = max(2.4, step - 1.5)
    vmax = max(total)
    ymax = vmax * 1.18

    def y_of(v):
        return base - (v / ymax) * (base - top)

    sc.line(cx0 - 6, base + 1, cx1 + 6, base + 1, RULE, 1)

    for i in range(n):
        y = base
        for c in cats:
            v = abs_[c["id"]][i]
            if v <= 0:
                continue
            h = (v / ymax) * (base - top)
            y -= h
            sc.rect(cx0 + i * step + (step - barw) / 2, y, barw, h, c["color"])

    # 峰值柱：一圈细描边，让「最贵那根」在缩略图里也能被挑出来
    pi = d["peak_i"]
    px = cx0 + pi * step + step / 2
    py = y_of(total[pi])
    bx = cx0 + pi * step + (step - barw) / 2
    sc.line(bx - 1.4, py - 1.6, bx + barw + 1.4, py - 1.6, INK, 1.2)
    sc.line(px, py - 10, px, py - 42, INK, 1.2)
    sc.circle(px, py - 46, 3.2, INK)
    sc.text(px, py - 70, "最贵", "sans", 11, MUTED, anchor="mt")

    # 右下角极小的来源行
    sc.text(W - 76, 588, "数据：上海 2024 城镇人均消费 54,980（全国城镇 34,557）｜模型估算，非统计发布物",
            "sans", 11, FAINT, anchor="rt")
    return sc


# ---------------------------------------------------------------- 图标
def icon_geo(size: float, pad_ratio: float = 0.10, with_dot: bool = False):
    """3 根高低不同的柱，每根上下两段（暗示堆叠）+ 一个点。返回 (rects, dot)。

    pad_ratio 随尺寸变化：32px 时留白更小，16px 观感下柱子才站得住。
    """
    pad = size * pad_ratio
    w = size - pad * 2
    gap = w * 0.10
    bw = (w - gap * 2) / 3.0
    base = size - pad
    heights = [0.50, 0.86, 0.34]
    cols = [("#C4553B", "#D8826C"), ("#2F5D62", "#6F9498"), ("#4A6FA5", "#8CA6C6")]
    rects = []
    for i, (hv, (c1, c2)) in enumerate(zip(heights, cols)):
        x = pad + i * (bw + gap)
        h = (base - pad) * hv
        cut = h * 0.58
        rects.append((x, base - h, bw, cut, c1))
        rects.append((x, base - h + cut, bw, h - cut, c2))
    # 16–32px 下 1px 的圆点会和中柱顶端糊在一起，所以小尺寸只留三根柱子
    px = pad + 1 * (bw + gap) + bw / 2
    py = base - (base - pad) * 0.86 - size * 0.12
    return rects, ((px, py, max(0.7, size * 0.055)) if with_dot else None)


def build_icon_scene(size: int) -> Scene:
    sc = Scene()
    rects, dot = icon_geo(size)
    for x, y, w, h, col in rects:
        sc.rect(x, y, w, h, col)
    if dot:
        sc.circle(dot[0], dot[1], dot[2], INK)
    return sc


def build_icon_svg(path: Path, size: int = 16):
    """与 icon_geo 同几何的矢量版（viewBox 16）。"""
    rects, dot = icon_geo(size, 0.10)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" aria-label="三根高低不同的消费堆叠柱">',
        f'<rect width="{size}" height="{size}" rx="2.4" fill="#FAF8F4"/>',
    ]
    for x, y, w, h, col in rects:
        out.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{max(h, 0.35):.2f}" fill="{col}"/>')
    if dot:
        out.append(f'<circle cx="{dot[0]:.2f}" cy="{dot[1]:.2f}" r="{dot[2]:.2f}" fill="#191817"/>')
    out.append("</svg>")
    path.write_text(chr(10).join(out) + chr(10), encoding="utf-8")


def build_touch_icon(path: Path, size: int = 180):
    """iOS 图标：米白底、圆角由系统裁切，柱形居中放大。"""
    big = size * 4
    img = Image.new("RGB", (big, big), PAPER)
    dr = ImageDraw.Draw(img)
    rects, dot = icon_geo(big, 0.22, with_dot=False)
    for x, y, w, h, col in rects:
        dr.rectangle([x, y, x + w - 1, y + h - 1], fill=col)
    if dot:
        px, py, R = dot
        dr.ellipse([px - R, py - R, px + R, py + R], fill=(25, 24, 23))
    img.resize((size, size), Image.LANCZOS).save(path, "PNG", optimize=True)


def main():
    d = load()
    scene = build_og(d)
    render_png(scene, ROOT / "og-image.png")
    render_svg(scene, ROOT / "og-image.svg")
    build_icon_svg(ROOT / "favicon.svg")
    render_png(build_icon_scene(32), ROOT / "favicon-32.png", 32, 32)
    build_touch_icon(ROOT / "apple-touch-icon.png")
    for name in ("og-image.png", "og-image.svg", "favicon.svg", "favicon-32.png", "apple-touch-icon.png"):
        p = ROOT / name
        print(f"[og] {name:<22} {p.stat().st_size:>8,} B")
    print(f"[og] 峰值 {d['peak_age']} 岁 {d['peak_v']:,.1f} 元 · 加权 {d['mean']:,.0f} 元")


if __name__ == "__main__":
    main()
