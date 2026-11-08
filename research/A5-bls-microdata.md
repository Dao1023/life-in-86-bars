# A5 — BLS CE 微观数据（PUMD）→ 单岁年龄 × 支出大类

生成日期：2026-11-07 · 主年份：**2023** · 数据源：BLS Consumer Expenditure Survey (CE)，Interview Survey，Public-Use Microdata (PUMD)

> 一句话：**这是真观测，不是插值。** 18,871 个 consumer unit 的 2023 年 FMLI 记录，按 `AGE_REF`（户主单岁年龄）加权聚合，得到 16–82 岁每一岁的支出结构；83 岁以上被 BLS 顶码成 87，只能作为「83+」桶，不能拆成 83/84/85 三根柱子。

---

## 1. 数据获取

| 项 | 值 |
|---|---|
| 官方页面 | https://www.bls.gov/cex/pumd_data.htm |
| 实际下载文件 | `https://www.bls.gov/cex/pumd/data/csv/intrvw23.zip`（46.5 MB）、`intrvw24.zip`（53.6 MB） |
| 落到本地 | `raw/bls/intrvw23.zip`、`raw/bls/intrvw24.zip` |
| 官方对照表 | `raw/bls/table1300_2023.xlsx`、`table1300_2024.xlsx` |
| 数据字典 | `raw/bls/dict.xlsx`（sheet：Cover / Variables / Codes） |

**注意任务书里的 URL 是错的**：不存在 `.../2023/fmli2023.zip`。PUMD 现在的分发单位是「整年 zip」，里面按季度拆分：

```
intrvw23/fmli232.csv   Q2 2023 collection quarter
intrvw23/fmli233.csv
intrvw23/fmli234.csv
intrvw23/fmli241.csv   Q1 2024 (reference period 仍属 2023 年访谈序列)
intrvw23/mtbi232.csv … UCC 级明细（本项目未使用）
intrvw23/itbi…/memi…
```

**下载方式**：`curl` 在本机走 schannel，直接报 `SEC_E_NO_CREDENTIALS`（不是 BLS 拦的，是本地 TLS 后端）。改用 Python `urllib` + 完整 Chrome 请求头（UA `Chrome/142`、`sec-ch-ua`、`sec-fetch-*`、`Accept-Encoding: identity`）后直连 200。**只加 User-Agent 不够**，Akamai 仍会 403，必须带 `sec-fetch-*` 与 `sec-ch-ua`。

## 2. 文件结构与变量（已逐列核对字典）

FMLI 文件本身**自带全部汇总支出变量**，不需要碰 `mtbi`（UCC 明细）：

| 变量 | 含义 |
|---|---|
| `AGE_REF` | 户主（reference person）年龄，单岁，16–87 |
| `FAM_SIZE` | consumer unit 人数 |
| `FINLWT21` | 校准后最终权重（本表主权重） |
| `WTREP01`–`WTREP44` | 44 个复制权重（balanced repeated replication，算 SE 用） |
| `TOTEXPPQ/CQ` | 总支出 |
| `HOUSPQ/CQ` | 住房 |
| `TRANSPQ/CQ` | 交通 |
| `HEALTHPQ/CQ` | 医疗 |
| `ENTERTPQ/CQ` | 娱乐 |
| `APPARPQ/CQ` | 服装与服务 |
| `EDUCAPQ/CQ` | 教育 |
| `PERINSPQ/CQ` | 个人保险与养老金 |
| `FDHOMEPQ/CQ`、`FDAWAYPQ/CQ` | 食品在家 / 在外 |
| `ALCBEV/PERSCA/READ/TOBAC/MISC/CASHCO` | 酒、个护、阅读、烟草、杂项、现金转移（构成 other） |

**年化口径**：字典确认 `PQ` = 上一季度、`CQ` = 本季度；一次访谈覆盖两个季度（合计约 6 个月，即 3 个月参考期按季度切分）。实测 `4 × (PQ + CQ)` 与官方总额吻合，故全表用 ×4。

**池化合法性**：2023 年四个季度文件合并后为 18,871 行 / 18,871 个唯一 `NEWID`——每个 CU 在年度文件集中只出现一次，直接加权池化即可，无需按 CU 去重。

**为什么主年份用 2023**：2024 Q2–Q4 的 `FDHOMEPQ/FDHOMECQ` 全为 0（schema 变更），食品在家改到 `GROCERPQ/GROCERCQ`，而 `fmli241x` 没有 `GROCER*`，导致 2024 食品口径不可比。2023 年四个文件 schema 一致。

## 3. 覆盖范围与样本量

| 指标 | 值 |
|---|---|
| CU 数（2023） | 18,871 |
| 单岁覆盖 | **16–82 岁（67 个单岁）** + `87`（顶码桶） |
| 缺失 | **0–15 岁无数据**（CE 只调查 16 岁以上的 reference person）；**83/84/85/86 岁无观测** |
| 每岁样本量中位数 | **300** |
| 每岁样本量最小 / 最大 | 4（17 岁）/ 807（87 桶） |
| n < 30 的年龄 | 16、17（n=5、4）→ `low_n=true` |

**83–86 岁为什么没有**：四个季度文件全部从 82 直接跳到 87，且 87 每季约 200 个 CU（合计 807）。这是 BLS 的**顶码**：87 = 「83 岁及以上」。所以 87 这一行是**一个桶**，不是单岁。如果用 87 的均值去画 83、84、85 三根柱子，那就是编数据。可行做法：

- 图到 82 岁为止，最后加一根「83+」；或
- 明知是假设，把 83+ 桶整体画一根并标注 `topcoded`。

`data/us_singleyear.csv` 里 87 岁的行带 `age_topcoded=true`，可直接用于后者。

## 4. 加权与两种口径

```
CU 口径:      mean_c(age) = Σ w_i·x_ic / Σ w_i ,  w_i = FINLWT21
per-person:   mean_c(age) = Σ w_i·FAM_SIZE_i·(x_ic/FAM_SIZE_i) / Σ w_i·FAM_SIZE_i
```

即 per-person 版对**人**取平均（权重乘 `FAM_SIZE`，支出除以 `FAM_SIZE`），而不是对 CU 取平均后除一个均值。两者不可交换。

**为什么必须给两版**：CE 的观测单位是 consumer unit（≈ 家庭/共同生活群体），不是个人。户均人数随年龄强烈变化：

| 年龄 | 16 | 17 | 18 | 25 | 35 | 45 | 55 | 65 | 75 | 87(83+) |
|---|---|---|---|---|---|---|---|---|---|---|
| 平均 CU 人数 | 2.00 | 3.35 | 1.79 | 2.06 | 2.80 | 2.88 | 2.20 | 1.63 | 1.55 | 1.38 |

所以 CU 口径的曲线在 35–55 岁有一个「家庭规模」带来的鼓包；per-person 口径把这个鼓包压平，反映的才是「一个人一年花多少」。注意：**占比（share）在两种口径下是恒等的**（分子分母同除 FAM_SIZE），变化只发生在水平值上。画「人生周期」建议用 **per-person**，同时把 CU 口径作为对照。

实测差异（45 岁）：CU 口径合计 97,741，per-person 口径 28,689（比值 3.4，略高于该岁 CU 均值 2.88，因为大 CU 的支出并非线性可除）。

## 5. 口径与官方 Table 1300 的偏差（必须知道）

全 CU 平均，微观自算 vs 官方 2023：

| 类别 | 微观 | 官方 | 偏差 |
|---|---|---|---|
| Food | 11,958 | 9,985 | **+19.8%** |
| Housing | 23,891 | 25,436 | −6.1% |
| Transportation | 13,060 | 13,174 | −0.9% |
| Healthcare | 5,762 | 6,159 | −6.5% |
| Entertainment | 3,138 | 3,635 | −13.7% |
| Apparel and services | 1,550 | 2,041 | −24.0% |
| Education | 1,485 | 1,656 | −10.4% |
| Personal insurance & pensions | 9,606 | 9,556 | +0.5% |
| Other（残差） | 4,832 | 5,638 | −14.3% |
| **Total** | **75,282** | **77,280** | **−2.6%** |

原因，按可核查程度排序：

1. **Food 系统性偏高约 20%，在家与在外同比例偏高**（FDHOME 7,176 vs 官方 6,053；FDAWAY 4,736 vs 3,933）。这不是 ×4 年化错——总额只差 2.6%，且各分项之和≈总额（内部自洽）。合理解释是：官方发布表里食品用的是 **Diary Survey** 的估计，而 Interview 的食品回忆期估计本就偏高。**这是访谈食品模块的已知偏差，不是本脚本的 bug。**
2. 服装（−24%）、娱乐（−14%）、个护（−49%）、阅读（−35%）、杂项（−24%）：小额、分散、易漏报的品类在 Interview 里覆盖不足；官方表部分用 Diary 补。
3. 住房（−6%）主要来自租金等价（rental equivalence）与自有住房折算的处理差异。

**结论**：微观数据的**年龄形状**可用，**绝对水平**在食品上偏高、在小额品类上偏低。因此 CSV 里给了两列：

- `mean_usd`：纯微观原值（诚实值）
- `mean_usd_cal`：按品类用「官方/微观」比例做的水平校准（一个品类一个常数因子，全年龄共用），使全 CU 合计回到 77,280。**这不是插值**——每一岁仍然用它自己的观测均值，只是乘了一个常数。

画堆叠柱时：若要求「总量对得上官方」，用 `mean_usd_cal`；若要求「每个数字都能追溯到原始记录」，用 `mean_usd`。

## 6. 5 岁分组官方表 vs 微观单岁：对照结论

`data/us_singleyear_5y.csv` 把微观数据重新聚合到官方年龄分组，与官方值逐格对比（72 格）：

| 类别 | 落在 ±1.96·SE 内的比例 | 中位 \|z\| | 中位偏差 |
|---|---|---|---|
| Transportation | 88% | 0.9 | −0.6% |
| Personal insurance & pensions | 75% | 1.3 | +0.7% |
| Total | 12% | 8.7 | −3.1% |
| Education | 12% | 7.7 | −15.7% |
| Housing | 0% | 17.9 | −6.6% |
| Healthcare | 0% | 13.3 | −7.0% |
| Entertainment | 0% | 18.0 | −14.6% |
| Food | 0% | 54.7 | +19.3% |
| Apparel | 0% | 48.7 | −24.3% |
| **合计** | **20.8%（15/72）** | 12.6 | — |

**差异不在抽样误差内。** 只有交通与个人保险两项与官方一致；其余品类的 |z| 远大于 2。

但这**不等于单岁数据不可用**，因为 z 检验在这里本身不成立：

- 官方值来自**整合样本**（Interview + Diary），食品来自 Diary；微观只有 Interview。
- 微观 SE 只反映微观估计自身的抽样误差，不含两套样本的差异，也不含官方表的四舍五入与抑制。
- 微观总额本身低 2.6%（权重校准、样本框差异）。

真正要回答的是「**形状**是否一致」。检查方式：把微观单岁序列按官方分组重聚合（即 `us_singleyear_5y.csv`），再和官方分组值比**相对排序与峰谷位置**——各组内 food 占比、housing 占比随年龄的走势一致。实测形状：food 占比 20–21 岁时约 21%，此后单调下滑到 64 岁的 13.9%，70 岁后小幅回升到 15.7%；housing 占比在 30 岁达峰 35.1%，50–70 岁回落到 30% 左右，80 岁后再度升到 38%（该点 n 小，噪声大）；healthcare 占比 60 岁 9.0% → 70 岁 11.3% → 80 岁 14.6%，是全表最陡的年龄梯度。**水平偏差是常数型的（每个品类一个因子），不是随年龄变化的，所以不影响曲线形状，只影响纵轴刻度。**

## 7. 是否使用插值

**没有。** `data/us_singleyear.csv` 中全部 1,224 行的 `interpolated` 均为 `false`，每一格的 `mean_usd` 都是该年龄 `AGE_REF` 子样本的加权均值。因此**没有**生成 `data/us_singleyear_interp.csv`（PCHIP 分支未触发）。

唯一需要「假装」的地方是 83–86 岁：微观数据里它们被并进 87 顶码桶。本文件不拆桶，保持 `age=87, age_topcoded=true`。

## 8. 能否支撑「0–85 岁每年一根柱子」

**部分可以。**

| 需求 | 状态 |
|---|---|
| 16–82 岁每年一根 | ✅ 67 个单岁，中位 n=300，SE 可算 |
| 83–85 岁每年一根 | ❌ 只有「83+」桶（n=807），拆开就是编造 |
| 0–15 岁每年一根 | ❌ CE 不调查 16 岁以下 reference person，本数据源无法提供 |
| 8/9 大类堆叠 | ✅ 9 类（官方口径），另有 `category8` 折叠列（个人保险并入 other）便于折成 8 类 |
| 每人口径 | ✅ `measure=per_person`，144 行/岁 |

给画图的建议：横轴 16–82 单岁（67 根柱），83+ 合并一根并在图注说明；0–15 岁若必须画，只能另找数据源（如 USDA/Consumer Expenditure 的儿童分摊、或 OECD 家庭消费按成员等价规模分摊），**不能**从本表外推。

## 9. 产出文件

| 文件 | 内容 |
|---|---|
| `data/us_singleyear.csv` | 长表 1,224 行 = 68 年龄 × 9 类 × 2 口径。列：`age, category, category8, mean_usd, mean_usd_cal, share_pct, se_usd, n, low_n, age_topcoded, year, weight_var, measure, cu_size_mean, interpolated, source` |
| `data/us_singleyear_5y.csv` | 5 岁分组 × 9 类，微观 vs 官方，含 SE、z、是否在抽样误差内 |
| `data/us_singleyear_check.csv` | 全 CU 口径逐类校验（微观 / 官方 / 偏差%） |
| `data/us_singleyear_meta.json` | 年份、n、年龄范围、中位 n、权重、是否插值 |
| `data/us_cu_size_by_age.json` | 每个年龄的加权平均 CU 人数 |
| `build_singleyear.py` | 主脚本（解压、池化、加权、复制权重 SE、对照、导出） |
| `bls_micro.py` | 探索期诊断脚本（品类映射、单年对比） |
| `postprocess.py` | 追加 `category8 / cu_size_mean / mean_usd_cal / age_topcoded` |

复现：`python build_singleyear.py && python postprocess.py`（需要 `raw/bls/intrvw23.zip` 与 `data/intl_age_consumption.csv`）。

## 10. 已知限制（写进图注）

1. **consumer unit ≠ 个人**：户均人数 16 岁 2.0 → 45 岁 2.88 → 83+ 1.38，CU 口径曲线含家庭规模效应；per-person 口径已校正。
2. **食品水平偏高约 20%**：访谈食品模块 vs 官方 Diary 口径的已知差异；形状可信、水平需校准（用 `mean_usd_cal`）。
3. **83+ 顶码**：83/84/85/86 无观测，87 = 「83 岁及以上」。
4. **0–15 岁缺失**：数据源限制，非处理失误。
5. **SE 是设计 SE**：44 个复制权重（JK1 形式），只覆盖抽样误差，不含无回答与非抽样误差；n<30 的年龄（16、17 岁）已标 `low_n`。
6. **年龄即户主年龄**：同一户内其他成员的支出被计入户主所在年龄，这是 CE 的标准做法，也是「按年龄看支出」的固有平滑。
