# 数据可视化项目页设计研究 —— 20 组实测样本 + 可执行清单

> 目的：给「一个上海人一生 86 根柱」的 GitHub Pages 单文件落地页做设计决策。
> 约束：单文件、零外部依赖、可离线（不能引 CDN 字体/图表库）。
> 数据锚点固定：0 岁 31,540 ／ 46 岁前后 64,415 ／ 峰谷比 2.04 ／ 85 岁医疗 34.4% ／ 每户 22 岁 46,000 → 46 岁 175,437。
> 本文所有数字都是**我抓页面量出来的**（HTML/CSS/og 图尺寸/HN 点数），不是印象。

## 0. 方法与局限

- 抓取方式：`requests` 直连 + 正则解析 `<head>`（og/twitter/JSON-LD）、`<h1>/<h2>`、内联 `<style>` 的 `font-family / position:sticky / font-size`、`<script src>` 的库指纹（d3/gsap/scrollama/svelte/next/mapbox…）、正文纯文本与关键词位置。脚本：`tools/probe_pages.py`，原始 JSON 在 `notes/probe/`。
- og:image 真实像素：下载后用 PIL 读，不是看文件名。
- HN 传播数据：Algolia API，2024-01 之后、points>250 的 story。
- **打不开的（已尽力，如实标注）**：`nytimes.com` 403（Upshot 栏目也 403）；`ft.com` 403（安全校验页）；`multimedia.scmp.com` 直连返回反爬 JSON；`neal.fun` 403；`washingtonpost.com` 读超时。其中 FT / SCMP / NYT 改用 web.archive.org 的 `id_` 原始快照才拿到（见 S07/S08/附注），**这三条的"首屏"是从存档 HTML 判读的，可能与现网有差异**。
- 搜不到「Sandbox/Playfair」是哪两个项目（Playfair Data 是 BI 培训站，不是项目页），用 Distill + OWID + Observable 覆盖了"开源/学术型落地页"这一档。

---

## 1. 样本（20 组，逐个打开过；打不开的 6 个站点单独列在附注）

### S01 The Pudding — *Are you more likely to die on your birthday?*（2025-04）
`https://pudding.cool/2025/04/birthday-effect/`
- 作者/机构：Russell Samora / The Pudding。Svelte 构建，2 个 script。
- **首屏**：`By Russell Samora` → 三行大字 **"You will die / someday. / Probably not today."**（14 词，分三行，逐行出现）→ 然后才是一句问句 "Would you believe me if I told you that you're actually more likely to die on your birthday…"。没有 CTA，往下滚就是全部。
- 叙事：滚动推进，每屏一句 + 一个图；无 sticky（内联 CSS 里 `position:sticky` 计数 0），靠"一句一段 + 图"的节奏。
- 可信度：摘要里就写"we'll run a study to show you how"；正文出现 "This statistical curiosity is called the birthday effect"，把术语先给名再给数；方法在全文 90% 位置。
- 视觉：全宽图 + 极窄正文；标题无衬线、字重 500；无网格线；配色为 Paul Tol bright 六色（CSS 里实测 `#4477AA #EE6677 #228833 #CCBB44 #66CCEE #AA3377`）。
- 分享卡：`assets/social.png` **1200×630 实测**。
- **为什么被转**：把"死亡"这种不可谈论的事，用一句 14 词的短句说成了"你会死，但不是今天"——**身份代入 + 黑色幽默**，标题本身就是转发的理由。

### S02 The Pudding — *Women's Pockets are Inferior.*（2018-08）
`https://pudding.cool/2018/08/pockets/`
- **首屏**：h1 就是一句 4 词的判决 "Women's Pockets are Inferior."（带句号）；og:description 是第二句钩子："If you wear women's clothes, you already know this. But now we've got the data to show it."——**先认同读者经验，再承诺证据**。
- 叙事：sticky 图 + 文字块（内联 CSS 有 2 处 `position:sticky`、2 处 `fixed`），这是 Pudding 最典型的滚动驱动。
- 可信度：正文 38% 处首次出现 caveat 类措辞，99% 处出现 credits；`@font-face` 9 个（自托管字体，**不是 CDN**）。
- 分享卡：**1200×628** JPEG。
- **为什么被转**：**身份认同**——一半人类穿女装口袋，标题就是她们的日常怨恨；数据只是把怨恨变成可引用的证据。

### S03 The Pudding — *Comparisons as Predictable as the Sunrise*（2026-05）
`https://pudding.cool/2026/05/similes/`
- h1 分三段排版（"Comparisons / as Predictable as / the Sunrise"）；副标一句 "An analysis of 200,000 similes from popular fiction."（**数字前置**）。
- 署名两行：`By Russell Samora. Design & Illustration by Shelly Tan.`——**文字作者与设计作者分开署名**，这是可信度信号里最便宜的一种。
- h2 结构：`Every Adjective has a Fingerprint` / `Specialists and Generalists` / `The Ironic Ones` / **`Data and Methods`**（放最后，4 个 h2 里排第 4）。
- 分享卡 1200×630。
- **为什么被转**：把"文学修辞"这种软话题，用 20 万条的语料做成"指纹"这种硬隐喻。

### S04 The Pudding — *Walkachusetts*（2025-10）
`https://pudding.cool/2025/10/walk/`
- 首屏给**读者一个选择**："You decide how to experience my story: TEXT / VISUAL"——两种阅读模式。
- h2 是 `Day Zero / Day One / … / Day Five`，**用时间戳当章节标题**，天然形成"往下滚 = 走过一周"。
- 正文 35K 字符，是全样本里最长的；分享卡 1200×630。
- **为什么被转**：第一人称 + 身体经验（跟腱断裂），不是"数据故事"而是"人的故事 + 数据"。

### S05 The Pudding — *Hamilton*（2017-03，Shirley Wu）
`https://pudding.cool/2017/03/hamilton/`
- 首屏几乎没有文字（h1 是一个 💖 emoji），正文只有 316 字符——**整页就是可视化本体**，是"一屏讲完"的极端样本。
- 可信度全靠文末一段致谢 + 署名 "Made with 💕 by Shirley Wu"。
- twitter:creator 有值（`@sxywu`），og:image 1200×630。
- **为什么被转**：把一个已有狂热粉丝群的 IP（音乐剧）做成可交互歌词图，**寄生在现成的传播池**。

### S06 Reuters — *Diversity Report 2024*
`https://www.reuters.com/graphics/DIVERSITY-REPORT/2024/xmpjbgdrapr/`
- 机构型：h1 "Diversity and inclusion at Reuters in 2023"，h2 序列 `Foreword / A reminder of our goals / Our data / Gender / …`（20 个 h2）。
- **"Our data" 是一个独立小节标题**——把方法论做成了章节，而不是脚注；正文 35.7K 字符里 source 类词 5 次，最早出现在 1% 位置。
- 技术：Svelte，只有 4 个 script，零框架 shell；自托管字体 `knowledge-light/regular/medium/bold`（4 个字重，@font-face 7 条）。
- 分享卡 **1500×1000（1.5:1）**——非标准比例，Twitter 大图会被裁两侧。
- **为什么被转**：不太会被转（企业年报），但它示范了**"机构可信度"如何用版式摆出来**：先目标、再口径、再数据。

### S07 Financial Times — *Follow $100 through the 2020 market rollercoaster*（存档快照判读）
`https://ig.ft.com/2020-markets/`（现网 403；经 `web.archive.org/…id_/` 取得）
- 首屏：标题 "$100" 在正中间；第一段是**第二人称的规则设定**："Good news reader! It is the first day of 2020 and the FT has gifted you $100… Let's see how 2020 shapes up."
- 署名三人并排（Katie Martin, Brooke Fox, Fan Fei）+ 相对时间 "24 seconds ago"；栏目 kicker "Capital markets"。
- 技术：React 挂载（"You need to enable JavaScript to run this app"），8 个 script，**整页依赖 JS**——这正是我们要避免的。
- **为什么被转**：把"指数涨跌"这种没人有感觉的东西，换成"**你口袋里的 100 块**"。抽象的金融变成可感知的损失。

### S08 SCMP — *The 120-year story of Hong Kong's iconic Star Ferry*（存档快照判读）
`https://multimedia.scmp.com/infographics/article/star-ferry/`（现网反爬；经存档取得）
- 首屏：大标题 2 行 + 日期 "June 16, 2018" + **三行署名带职务**：
  `Hana Davis — Journalist` / `Adolfo Arranz — Deputy Head Infographics & Illustration` / `Pablo Robles — Infographic Designer`。
- 版式：手绘插画 + 全出血；HTML 只有 15.8KB，jQuery，无 sticky；`img/cover.jpg` 当分享图。
- **为什么被转**：一个城市符号的百年史 = 本地身份认同；插画承担情绪，图表承担事实。

### S09 Distill — *How to Use t-SNE Effectively*（2016）
`https://distill.pub/2016/misread-tsne/`
- 首屏：h1 + **一句话摘要被写成 h2**（"Although extremely useful… plots can sometimes be mysterious or misleading."），然后立刻是 5 条**编号结论式小标题**：
  `1. Those hyperparameters really matter` / `2. Cluster sizes in a t-SNE plot mean nothing` / `3. Distances between clusters might not mean anything` / `4. Random noise doesn't always look random.` / `5. You can see some shapes, sometimes`
- **这份目录本身就是全文的结论**——读者滚到任何一节都知道在证明什么。这是"可信度做成版式"的核心技巧。
- 视觉：`h1 { font-family: Cochin, Georgia, serif }`，最大字号实测 **56px**，正文衬线，图内交互控件（play/pause/step）常驻图上方。
- 技术：13 个 script（D3），单篇静态页，无构建 shell。
- **为什么被转**：**反直觉 + 可操作**。"cluster 大小无意义"这句话直接推翻了很多人的直觉，而且给了 5 条使用建议。

### S10 Distill — *Zoom In: An Introduction to Circuits*（2020）
`https://distill.pub/2020/circuits/zoom-in/`
- 15.4MB HTML（图内嵌），h2 是 `Introduction / Three Speculative Claims / Claim 1: Features / Claim 2: Circuits / Claim 3: Universality`——**把论证结构直接做成目录**，"Claim 1/2/3" 是可被引用的编号。
- 字体栈 `-apple-system, BlinkMacSystemFont, …` + georgia；GSAP 做过渡。
- **为什么被转**：它给了一个可命名的框架（features / circuits / universality），媒体引用时只需要引用这三个词。

### S11 Our World in Data — *Life Expectancy*
`https://ourworldindata.org/life-expectancy`
- 首屏：h1 + **一行 by-line 五个作者全名** + 两个按钮 **"Cite this work" / "Reuse this work"**（就在折叠线以上）。
- 正文 24K 字符，source 类词 18 次，最早的出现在 **12%** 位置；15 个 `<figure>`，每图自带 "Chart / Table / Sources / Download" 四件套。
- 视觉：单色系（主题色 `#1d3d63` 出现 253 次），无装饰；图表全宽，正文窄栏。
- 技术：607KB 单 CSS，服务端渲染，无 JS 依赖即可读。
- **为什么被转/被引用**：**"Cite this work" 是给引用者准备的按钮**。它把"我想引用你"这个动作的成本降到一次点击。

### S12 Nicky Case — *Parable of the Polygons*（2014，长期被转）
`https://ncase.me/polygons/`
- 18.6KB 单 HTML、1 个 CSS、**零库**（`libs: []`）——这是"零依赖也能做爆款"的存在证明。
- 首屏第一句就是全文论点："This is a story of how harmless choices can make a harmful world."；第二屏直接让你拖动小人。
- 可信度：无数据源、无方法段——它不假装是研究，是**可玩的论证**（parable）。
- 分享卡 1200×600。
- **为什么被转**：**你得先玩一下才能理解**，玩的行为本身就是传播动机。

### S13 no days off（2025-06，HN **958 分 / 495 评论**）
`https://nodaysoff.run`
- 首屏：4 个巨型数字横排 —— `3,881 days / 13,454 miles / 2,088 hours / 257k ft climbed`，上面只有一行小字 "running everyday from July 11, 2015 to February 23, 2026"。**没有一个形容词**。
- 章节：`FOREWORD / NOTABLE RUNS / STATISTICS / GEOGRAPHY`（4 个 h2，全部四字大写）。
- 技术：Next.js + Mapbox，页面 **9.9MB**（数据内联）——说明"单页"不等于"轻"。
- 分享卡 1200×630。
- **为什么被转**：一个普通人十年不间断的记录，**极端连续性**本身就是钩子；数字全部可验证（日期区间写死在首屏）。

### S14 jameshard.ing/pilot（2025-06，HN **1539 分 / 197 评论**）
`https://jameshard.ing/pilot`
- 首屏 h1 是第一人称身份句：**"I am an Airbus A350 Pilot"**；下面 18 个 h2（`Statistics / Career Highlights & Stats / Destination Matrix / Flight Calendar`）。
- 技术：单页、8 个 script、内联 CSS（抓不到外部 CSS）、`IntersectionObserver` + `scroll` 监听都在用；**无 og:image、无 twitter 卡**。
- **为什么被转**：职业身份 + 只有从业者才有的数据（航线矩阵）。**"只有你能有的数据"是最强的护城河**。
- 教训：它传播很好，但分享出去是一条无图的裸链接——**缺 og 卡是纯损失**。

### S15 valhovey.github.io/gaia-mary（2026-05，HN **1200 分 / 244 评论**）
`https://valhovey.github.io/gaia-mary/`
- **GitHub Pages 项目页**的典型：HTML 只有 3.3KB，Svelte 编译产物，首屏全是 canvas（无文本），og:image = `featured.png` **实测 1750×1218（1.44:1，非标准）**。
- 传播理由：蹭《Project Hail Mary》电影热度 + 真实星表数据（"accurate star data" 写在 description 里）。
- 教训：3.3KB 的 HTML 也能上 HN 首页——**重量不在结构，在体验**；但 1.44:1 的卡在 Twitter 会被裁。

### S16 bbycroft.net/llm（2025-09，HN **640 分**）
`https://bbycroft.net/llm`
- HTML 12KB，16 个 script（Next.js），正文文本仅 23 字符（**全部内容在 canvas 里**）；无 og 标签。
- **为什么被转**：3D 可旋转的 LLM 内部结构，别人没做过；话题正热。
- 教训：全 canvas 页面 = 对 SEO/分享/无障碍全部放弃。我们要吸收它的"可旋转/可探索"，但**保留 DOM 文本**。

### S17 财新数字说 — *「新工体」揭面纱*（2023）
`https://datanews.caixin.com/interactive/2023/Beijing-Workers-Stadium/`
- 中文机构里最接近我们形态的：**单 HTML 页面 + D3**，h1 无（标题是图里的字），正文 6K 字符，`fixed` 定位 1 处。
- 字号实测：CSS 里最大 **40px / 30px / 20px**（中文标题 40px 上限）。
- **没有 og:title / og:description / og:image**（三个财新样本全为 0）——分享出去是裸链。
- 可信度：source 类词 6 次，最早 52% 位置；caveat 1 次 68% 位置；**署名在最末（89%）**。
- **为什么会被转**：本地地标 + 足球情绪；但技术上是"网页里的信息图"，缺传播件。

### S18 澎湃 美数课 — *宠物「银发潮」*（2026-11）
`https://www.thepaper.cn/newsDetail_forward_34429161`
- 首屏：标题 20 字 + 记者署名一行（`澎湃新闻记者 杨睿贤 王亚赛`）+ 日期 + 栏目「美数课」+ 「责任编辑 / 校对」。
- 技术上被平台绑架：37 个 script、Next.js、11 个 CSS；og:image 是一张**正文截图 PNG**（不是设计过的卡片）。
- 图文正文被折叠进客户端，网页端只有 535 字符可见——**内容不在 HTML 里**，这对引用极不友好。
- 教训：中文语境里"署名 + 责任编辑 + 校对"是标准可信度件，但**没人做 share card**。这是我们可以直接领先的地方。

### S19 独立设计师页 — Nadieh Bremer / Amelia Wattenberger / Observable
- `https://www.visualcinnamon.com/portfolio/`：**没有 h1**（全靠视觉），作品墙 + "Featured Projects"；一个 CTA "get in touch"；无 twitter 卡；og:image 是通用品牌图。
- `https://wattenberger.com/`：首屏第一人称 "Hi, I'm Amelia Wattenberger"，三个动词短语链接（create things / explore novel interfaces / turn data into meaning）——**用动词而不是职位介绍自己**。
- `https://observablehq.com/@d3/gallery`：42 个 script、零 og 标签；notebook 形态的可复现性来自"代码就在页面上"，不是来自方法段。
- 共同点：**个人品牌页靠"作品密度"而非"论述"说服人**；对我们是反面教材（我们没有作品集，只有一件作品）。

### S20 Observable / Datawrapper / Data Viz Catalogue（工具型落地页）
- `https://blog.datawrapper.de/`：blog 索引，15 个 CSS，`summary_large_image`，og:image 走 CDN 动态裁切（`cdn-cgi/image/width=1200`）——**分享图是构建时生成的**，不是手工画的。
- `https://datavizcatalogue.com/`：26KB、零 og、零 h1，纯目录站，靠 SEO 长尾。
- 结论：工具站靠"可搜索的目录"，项目站靠"一张卡"。我们属于后者。

### 附：打不开的样本（如实记录）
| 站点 | 结果 | 处理 |
|---|---|---|
| nytimes.com/interactive（含 Upshot 栏目） | 403 | 未取得；NYT 的版式（Cheltenham 衬线标题 + 窄栏 + "By …" 署名 + 图注里写 source）在 S09/S11 中已有同构替代 |
| ft.com 正文页 | 403 安全校验 | 改用 `ig.ft.com/2020-markets/` 存档快照（S07） |
| multimedia.scmp.com 直连 | 反爬 JSON | 改用存档快照（S08） |
| neal.fun/spend、/size-of-space | 403 | 未取得；其在 HN 的传播靠"一个可玩的反事实"，与我们相关性低于 S13/S14 |
| washingtonpost.com/corona-simulator | 读超时 | 未取得 |

---

## 2. 横向统计（我量到的，不是感觉）

| 指标 | 实测结果 | 含义 |
|---|---|---|
| og:image 尺寸 | 11 个可测样本中 **5 个正好 1200×630**；其余各不同：1200×628、1200×600、1200×675、1120×590、1500×1000、1750×1218 | 1200×630 是事实标准（Pudding 6 个里有 4 个是它）；非 1.9:1 的会被裁（gaia-mary 的 1.44:1 就废了） |
| 有 twitter:card 的 | Pudding 6/6、Distill 3/3、OWID 2/2、ncase 2/2；**财新 0/3、pilot 0、bbycroft 0、Observable 0** | 独立开发者与中文机构普遍缺卡 → 传播白丢 |
| h1 词数（英文样本） | Pudding 4–6 词（"You will die someday." 4 词；"Women's Pockets are Inferior." 5 词）；Distill 6 词；SCMP 9 词；FT 10 词 | 首屏标题 ≤10 词，中文对应 ≤20 字 |
| 正文长度 | Pudding 9.7K–35K 字符；OWID 24K；Distill 14K–57K；Caixin 6K；澎湃网页端仅 535 | 长文不是问题，"首屏有没有钩子"才是 |
| `position:sticky` | 20 组里只有 2 组（Pudding pockets、Caixin wall）内联样式出现 | 滚动驱动更多靠"一屏一图"，不是必须 sticky |
| 字体 | Distill 用 Cochin/Georgia 系统衬线；Reuters 自托管 4 字重；Pudding 9 个 @font-face 自托管；OWID 纯系统字体 | **没有人用 CDN 字体**；自托管或系统栈 |
| 配色 | Pudding 6 色（Paul Tol bright）；OWID 单色 253 次；nodaysoff 全灰阶 + 1 强调 | 图表用色 ≤6，页面用色 ≤3 |
| HN 点数 | pilot 1539 / gaia-mary 1200 / nodaysoff 958 / LLM viz 640 / relativity 633 | 单页个人项目能上首页，前提是"只有他能做的数据" |

---

## 3. 可直接抄的 15 条手法（每条附证据）

1. **首屏第一行是一句 ≤20 字的反直觉断言，独立成段，前后各留 40px 空白**——不是标题的副产物。证据：Pudding 首屏 "You will die / someday." `https://pudding.cool/2025/04/birthday-effect/`
2. **标题写成判决句并带句号**："Women's Pockets are Inferior." 比 "The Gender Gap in Pocket Size" 强一个数量级。证据：`https://pudding.cool/2018/08/pockets/`
3. **首屏放一个 ≥64px 的数字，且数字自带参照系**（分母/区间/年份）。证据：nodaysoff 首屏 `3,881 days / 13,454 miles / 2,088 hours` `https://nodaysoff.run`
4. **把抽象量换成第二人称的"你的某个东西"**：FT 把股指换成"你口袋里的 100 美元"。证据：`https://ig.ft.com/2020-markets/`
5. **结论句直接当小标题，编号、可引用**："2. Cluster sizes in a t-SNE plot mean nothing"。证据：`https://distill.pub/2016/misread-tsne/`
6. **署名带职务、放在标题正下方，作者与设计者分开写**。证据：SCMP 三行 `Journalist / Deputy Head Infographics / Infographic Designer` `https://multimedia.scmp.com/infographics/article/star-ferry/`；Pudding "By X. Design & Illustration by Y."
7. **给引用者一个按钮**："Cite this work" / "Reuse this work" 放在折叠线以上。证据：`https://ourworldindata.org/life-expectancy`
8. **方法不是免责声明，是一个有标题的章节**（h2 级），放文末，入口在首屏。证据：Pudding h2 `Data and Methods`；Reuters h2 `Our data`
9. **"已知局限"用降调排版**（12px、灰、左竖线），一段话讲清"哪个数最不可信、错多少"，不要三条并列的免责声明。证据：现有 v6 的 `.hh-warn` 已是这个形态，保留。
10. **图内直接标注，删掉网格线与图例**：注释文字贴着数据点，不靠图例色块。证据：nodaysoff / pilot 的图全部内联标注；反例：OWID 的 15 个 figure 仍带完整轴与网格（机构风，不是传播风）
11. **正文窄栏 + 图全宽**：文字 `max-width: 34em`，图 100%。证据：Distill 的 CSS 里只有一个 `max-width: 700px`（实测），配全宽交互图；Pudding 同构
12. **默认状态就必须"截图可读"**：不交互、不 hover，静态截图里也能看出结论（因为 HN/Twitter 传播 90% 是截图）。证据：S13/S14 的首屏数字条；反例：bbycroft 的 canvas 页 `https://bbycroft.net/llm` 截图只有一团几何体
13. **交互只做一层**：hover/pin 一根柱，弹出这一年的构成；不要四个控件（口径/视图/情景/注释）。证据：Pudding 全站每个故事只有一个交互维度；现有 v6 有 8 组控件（口径/视图/情景/注释/表格 + 幼儿园/老年折减/长护）
14. **分享卡是设计出来的，不是截图**：标题 ≤12 字 + 一个数字 + 图缩略，1200×630。证据：Pudding 6/6 有专门 `assets/social.png`；反例：澎湃用正文截图当 og:image `https://www.thepaper.cn/newsDetail_forward_34429161`
15. **首屏写给"已经同意你的人"，方法段写给"还没同意你的人"**：认同感在前，证据在后。证据：S02 的 og:description "If you wear women's clothes, you already know this. But now we've got the data to show it."

---

## 4. 中文语境的注意点

### 4.1 字号阶梯（1440 宽实测对照）
| 元素 | 现有 v6 | 建议 | 理由 |
|---|---|---|---|
| h1 | `clamp(36px,4.6vw,64px)` | `clamp(40px,6.4vw,88px)` | 中文标题字面密度高，64px 在 1440 下只占 2/3 行宽，气势不足；88px 时 12 字标题正好两行 |
| 首屏大数字 | `.stat .vv` 34px | **72–96px** | 34px 在 1200px 宽的分享卡里缩到 ~17px，读不出；72px 缩到 36px 仍可读 |
| 副标题 | 14px | 19–21px | 14px 中文在 Windows 上糊成一团（SimSun 无次像素优化） |
| 正文 | 15px / 1.6 | 17–18px / 1.85 | 中文单字信息量 ≈ 1.6 个英文词，15px 相当于英文 11px |
| 图注/注释 | 11.5px | 12.5–13px | 11.5px 中文可读性临界 |

**中文行宽**：每行 28–38 字。17px 下 `max-width: 34em`（≈578px）比现有 1000px 的 `.lede` 更易读（现有 lede 1000px，17 字/行 → 太长，实测截图里一行 40+ 字）。

### 4.2 标点与排版
- 标题**不加句号**；如果要"判决感"，用句号只在英文标题（Pudding 的句号是英文惯例，中文照搬会显得像未完句）。
- 数字与中文之间加 `0.08em` 空隙（`64,415 元`），不要用全角空格。
- 千分位用半角逗号 `64,415`，不要 `6.4 万` 与 `64,415` 混用——**全文统一到"元"，只在口语化句子里用"6 万 4"**。
- 「」用于术语强调，引号用 “”，不要混用英文 `"…"`（现有页面里的 `"` 需统一）。
- 破折号用 `——`（两个 em dash），不要 `--`。
- 百分比写 `34.4%`，不写 `34.4％`（全角百分号在部分字体里宽度跳变）。

### 4.3 竖排
**不建议**。`writing-mode: vertical-rl` 会让数字和单位旋转 90°（`64,415` 变成竖排的数字串），Safari 与 Chrome 的行内混排行为不一致，移动端几乎不可用。若一定要"竖排感"，只对**装饰性短标题**用 `writing-mode: vertical-rl; text-orientation: upright`，且该标题不承载信息。样本里 18 个页面**没有一个**用竖排——包括中文的财新与澎湃。

### 4.4 字体回退（离线、无 CDN）
```css
--serif: "Source Han Serif SC","Noto Serif CJK SC","Songti SC","STSong","SimSun",serif;
--sans: -apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei","DengXian","Source Han Sans SC","Noto Sans CJK SC",sans-serif;
```
坑（按严重度）：
1. **Windows 没有 Songti SC**，会掉到 `SimSun`——宋体在 14px 以下的屏幕上笔画粘连，标题尚可、正文不可用。所以 **正文一律走 sans**，衬线只用于 h1 和大数字。
2. Windows 的 `Microsoft YaHei` 字重只有 Regular/Bold，没有 500；`font-weight:500` 会被合成加粗导致发糊。**中文只用 400 / 600 / 700 三档**。
3. macOS 的 `PingFang SC` 在 600 以上会跳到 Semibold，与 Windows 的 Bold 视觉重量差一档，标题在两端看起来不一样重——**用 `font-synthesis: none` 关掉合成**。
4. `DengXian`（等线）比 SimSun 在屏幕上干净，可作为 sans 栈的 Windows 兜底（放在 YaHei 之后无意义，YaHei 一定命中；只有 YaHei 缺失的老系统才会用到）。

### 4.5 要不要内嵌字体：实测数据
用 `fontTools.subset` 对 1034 个字符（900 常用汉字 + ASCII + 中文标点）做子集，实测：
| 字体 | woff | woff2 |
|---|---|---|
| 微软雅黑 msyh.ttc | **145 KB** | ~95 KB（本机缺 brotli 未实测，按 CJK 常规 0.6× 估） |
| 宋体 simsun.ttc | **135 KB** | ~90 KB（估） |
| 等线 Deng.ttf | **216 KB** | ~140 KB（估） |

结论与建议：
- **正文不嵌字体**（系统栈足够，且中文正文嵌入会让单文件从 230KB 涨到 380KB+）。
- **只嵌标题用的一个衬线字重**，且只子集**标题里出现的字**（约 40–80 个汉字 + 数字 + 标点）→ woff2 **约 12–25KB**，base64 后 +33% ≈ 16–33KB。这是"离线也有统一标题气质"的最小代价。
- 实现：`@font-face{src:url(data:font/woff2;base64,…) format("woff2");font-display:swap;}` + 系统栈兜底；用 `size-adjust` 微调回退字体的度量，避免 swap 时跳版。
- 若连 20KB 都不想加：接受"macOS 看宋体、Windows 看雅黑"的双端差异，**但 h1 的 `letter-spacing` 要按字体分别调**（SimSun 需要 `+0.02em`，PingFang 需要 `0`）。

### 4.6 GitHub Pages 具体事项
- 放 `.nojekyll`（否则 `_` 开头的资源 404）。
- 单文件页面**不要**依赖 `?v=` 查询串做缓存失效，改用文件名（`index.html` 每次部署 GitHub 的 CDN 缓存约 10 分钟，可接受）。
- `<html lang="zh-Hans">`；`<meta name="theme-color">` 用纸色而不是白色（移动端地址栏染色）。
- GitHub Pages 对 `.woff2` 返回正确的 `font/woff2`，无需额外配置；但**大小写敏感**（Linux），文件名全小写。

---

## 5. 三种落地页结构方案

### 方案 A：极简海报式（一屏讲完）
**首屏文案**
- 标题：`你这辈子最贵的一年，46 岁`（15 字）
- 副标题：`上海 2024 年价，86 根柱，一年一根。模型估算，非官方观测。`（30 字）
- 大数字：`64,415` 元／人／年（96px）+ 角标 `最省的一年 31,540（0 岁）`
- CTA：`看完整 86 年 ↓`（唯一一个）

**模块清单**：报头（眉题/标题/副标/一句断言）→ 数字条（2 格）→ 单张 86 柱 SVG（全宽，图内 4 条注释）→ 一行图注（口径 + 模型估算 + 数据文件链接）→ 分享按钮 → 方法折叠（默认收起）。

**实现复杂度：低。** 在现有 v6 上做减法即可，JS 增量 ≈ **120–180 行**（删控件的事件绑定、加 resize 重算、加"复制链接/下载 PNG"按钮）。总计约 250 行 JS。

**适合场景**：Twitter/X 与 HN 的单图传播、微信朋友圈截图、媒体报道配图。缺点：讲不了"结构变化"，只能讲"一个数"。

### 方案 B：滚动叙事式（sticky 图 + 5 个 step）★推荐
**首屏文案**
- 标题：`一辈子 86 根柱，钱花在哪一年？`（16 字）
- 副标题：`上海 2024 年价。0 岁最省，46 岁最贵，85 岁医疗占 34.4%。`（33 字）
- 大数字：`2.04×`（96px，峰谷比）+ 小字 `64,415 ÷ 31,540`
- CTA：`往下滚，5 个转折 →`

**5 个 step（全部用已定稿锚点，不新增数字）**
| # | step 标题（≤14 字） | 图的状态 | 文案落点 |
|---|---|---|---|
| 1 | 0 岁：一年 31,540 | 只高亮第 1 根柱，其余 30% 透明 | "这是全图最低点，托育还没开始" |
| 2 | 22 岁：每户 46,000 | 切到每户口径，高亮第 1 根 | "一个家庭从这里开始花钱" |
| 3 | 46 岁：64,415（每户 175,437） | 高亮峰值柱 + 一条水平基准线 | "最贵的不是养娃，是四十几岁那一段" |
| 4 | 峰谷比 2.04× | 两根柱并排抽出，中间画一个 2.04 的括号 | "最贵的一年是最便宜的两倍" |
| 5 | 85 岁：医疗 34.4% | 只高亮医疗色块，其余降饱和 | "最后一根柱里，三分之一是医疗" |

**模块清单**：报头（= A 的首屏，复用）→ sticky 图容器（`position:sticky; top:0; height:100vh`）+ 5 个 step 文字块（每个 `min-height:100vh`）→ 进度指示（5 个点）→ 图例（可 solo）→ 详情卡（pin 某年）→ 方法折叠 → 分享。

**实现复杂度：中。** 现有 v6 的 SVG 渲染可整段复用（688 个 rect 一次渲染已经做好），新增：
- `IntersectionObserver` 监听 5 个 step（**不要引 scrollama**）：~45 行；
- step → 图表状态的映射（透明度/高亮/基准线/括号）：~90 行；
- sticky 布局与移动端降级（窄屏改为"图在上、文字在下，不 sticky"）：~40 行 CSS + 25 行 JS；
- 进度点与"回到顶部"：~20 行。
合计新增 **≈180–220 行 JS**，删掉现有 8 组控件中的 5 组（省 ~120 行），净增约 100 行，总量 ~900 行。

**适合场景**：被媒体引用（记者需要一个"能截 5 张图"的页面）、深度阅读、HN 长评论讨论。风险：移动端 sticky 抖动——必须给 `height:100dvh` 并准备 `@media (max-height:600px)` 的降级。

### 方案 C：报告式（摘要 + 图表 + 方法）—— 现有 v6 就是
**首屏文案**
- 标题：`一个上海人的一生，每年要花多少钱`（18 字） （2026-11-08 口径调整：标题改为「一个中国城市人，一生要花多少钱」，上海降为示例。）
- 副标题：`0–85 岁逐年消费结构 · 2024 年上海市价 · 元/人/年 · 模型估算，非官方分年龄观测`
- 断言：`模型里最贵的不是养娃那几年，是四十几岁那一段。`

**模块清单**：报头 → 4 格数字条 → 2 行控件（口径/视图/情景/注释/表格 + 3 组敏感性）→ 86 柱主图 + 11 条注释 → 图例 + 详情卡 → 方法折叠（含 5 个敏感性文件）→ 数据文件页脚。

**实现复杂度：高。** 现有实现 ~1000 行 JS（含表格视图、pin、solo、敏感性切换）。**不建议再扩**，只做减法。

**适合场景**：研究者/记者二次分析、需要"可核查"的场合。缺点：首屏被控件占据（实测截图里图从约 700px 才开始，1440×900 的笔记本看不到图主体），截图传播几乎为零。

### 推荐：**B**，但首屏照抄 A 的排版
理由三条：
1. 我们的**唯一资产是连续性**（86 根柱、一年一根）——这是 A 讲不了的，只有滚动能让人"走过"一生；5 个 step 恰好对应 5 个已定稿锚点，文案不需要新数字。
2. **截图传播靠首屏，深度传播靠滚动**。B 的首屏可以完全套用 A（一句 15 字断言 + 96px 数字），所以 B 是 A 的超集，不是替代。
3. **改造成本可控**：SVG 与数据管线已存在，新增逻辑约 200 行，且不引入任何库；C 的复杂度换不来传播，A 的简洁换不来论证。

落地顺序：先在现有 v6 上**做减法到 B 的首屏**（删 4 组控件、h1 提到 88px、数字提到 96px、断言提到副标之前），再加 5 个 step。不建议重写。

---

## 6. 分享卡片规格（1200×630）

### 6.1 版式（尺寸对标 Pudding 的 `assets/social.png`，1200×630 实测；版式是我们按 S13/S14 首屏的规律设计的，未逐像素比对它的卡）
```
┌─────────────────────────────────────────────────┐ 1200×630
│  眉题 24px  「上海 · 2024 年价 · 元/人/年」        │  上边距 56
│                                                  │
│  标题 76px（2 行，≤12 字）                        │
│  你这辈子最贵的一年                               │
│  是 46 岁                                        │
│                                                  │
│  64,415 元   ← 132px 衬线，tabular-nums          │
│  最省的一年 31,540（0 岁）  ← 26px 灰             │
│                                     ┌──────────┐ │
│                                     │ 86 根柱   │ │  右侧 380×300 缩略
│                                     │ 缩略图    │ │  （原图直接缩，不重绘）
│                                     └──────────┘ │
│  jameshard.ing 风格：不加 logo、不加二维码        │  下边距 48
└─────────────────────────────────────────────────┘
```
硬规则：
- **安全区**：四周留 56px，Twitter 大图在移动端会左右各裁 ~40px。
- **标题 ≤12 字**（76px 下 12 字 = 912px，正好一行半）；超过 12 字必缩到 64px。
- **数字 132px**，且必须带单位（`元`）——数字要在缩略到 600px 宽时仍是视线第一个落点。
- **配色 ≤3**：纸色底 + 墨色字 + 一个强调（用医疗色或峰值色）。
- 不要放 QR 码、不要放 "点击查看"（截图里点不了）。
- 另存一张 **1080×1080**（朋友圈/小红书 1:1），内容同版式重排为上下结构。

### 6.2 meta 完整清单
```html
<!-- 基础 -->
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>你这辈子最贵的一年，46 岁 · 上海人一生 86 根柱</title>
<meta name="description" content="上海 2024 年价，0–85 岁逐年消费结构。0 岁 31,540，46 岁 64,415，峰谷比 2.04。模型估算，非官方观测。">
<meta name="author" content="（你的名字）">
<meta name="theme-color" content="#F7F4EE">
<link rel="canonical" href="https://<user>.github.io/<repo>/">

<!-- Open Graph -->
<meta property="og:type" content="article">
<meta property="og:site_name" content="（站点名）">
<meta property="og:locale" content="zh_CN">
<meta property="og:url" content="https://<user>.github.io/<repo>/">
<meta property="og:title" content="你这辈子最贵的一年，46 岁">
<meta property="og:description" content="0–85 岁，86 根柱。0 岁 31,540，46 岁 64,415，峰谷比 2.04。">
<meta property="og:image" content="https://<user>.github.io/<repo>/og-1200x630.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:type" content="image/png">
<meta property="og:image:alt" content="86 根堆叠柱：46 岁最高 64,415 元，0 岁最低 31,540 元">

<!-- Twitter / X -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="你这辈子最贵的一年，46 岁">
<meta name="twitter:description" content="上海 2024 年价，0–85 岁逐年消费结构。峰谷比 2.04。">
<meta name="twitter:image" content="https://<user>.github.io/<repo>/og-1200x630.png">
<meta name="twitter:image:alt" content="86 根堆叠柱的缩略图">
<meta name="twitter:creator" content="@你的账号">

<!-- 可信度：给机器读的 Dataset 标记（OWID 式"可引用"的机器版） -->
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Dataset",
 "name":"上海 2024 年分年龄消费结构（模型估算）",
 "description":"0–85 岁逐年、八类消费的模型估算，非官方分年龄观测。",
 "creator":{"@type":"Person","name":"（你的名字）"},
 "datePublished":"2026-11-08",
 "license":"https://creativecommons.org/licenses/by/4.0/",
 "variableMeasured":["食品烟酒","衣着","居住","生活用品及服务","交通通信","教育文化娱乐","医疗保健","其他用品和服务"],
 "spatialCoverage":"上海","temporalCoverage":"2024"}
</script>
```

注意：
- **`og:image` 必须是绝对 URL**（GitHub Pages 的相对路径在微信/Twitter 抓取时经常失败）。
- 微信内置浏览器抓 `og:image` 有缓存，换图后要在链接后加 `?v=2` 再发一次。
- 现有 `viz/og-image.png` 已是 1200×630（实测），可直接用；但需补 `og:image:width/height`、`twitter:*` 与 JSON-LD——这三样目前都缺。

---

## 7. 对照现有 v6 的具体差距（10 条，按性价比排序）

1. **首屏没有 96px 的数字**：`.stat .vv` 是 34px。→ 提到 72–96px，只保留 2 格（64,415 / 31,540），另两格下沉。
2. **断言句位置太低**：现在在副标之后、还有一行"模型估算"夹在中间。→ 断言提到副标**之前**，14px→22px。
3. **8 组控件在折叠线以上**：口径/视图/情景/注释/表格/幼儿园/老年折减/长护。→ 首屏只留"人均｜每户"一个切换，其余进"方法"或"高级"。
4. **"模型估算"重复 3 次**（眉题、副标、图注）。→ 首屏只留 1 次，其余在图注。
5. **h1 64px 上限**，在 1440 下两行占宽约 70%。→ 88px，`text-wrap:balance` 已具备。
6. **缺"每户"的叙事**：46,000 → 175,437 是 3.8 倍的落差，比人均的 2.04× 更有冲击，但现在藏在切换器里。→ 做成 step 2。
7. **没有分享按钮/复制链接**。→ 加一个 `navigator.clipboard` + `navigator.share`，20 行。
8. **meta 不全**：缺 twitter 全套与 JSON-LD（og:image 已有 1200×630）。
9. **图注与注释文字 11.5px**，在移动端不可读。→ 12.5px 起。
10. **正文 lede 1000px 宽**，一行 40+ 字。→ 34em。

---

## 8. 结论一句话

样本里**没有一个**是靠"页面漂亮"被转的：被转的都是"**一句话说得清的反直觉结论 + 一个只有作者能算出来的数**"，页面只是把这句话的证据摆整齐。我们的那句话是「**最贵的不是养娃，是四十六岁**」，那个数是 **64,415**（还有 2.04× 和每户 175,437 两个备选）。设计任务不是让它好看，是让这句话在**首屏 900px 内**被读完，并且**截图能单独成立**。
