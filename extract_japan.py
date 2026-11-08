import xlrd, csv, os

# e-Stat 家計調査 2024年 年報 第3表 世帯人員・世帯主の年齢階級別
# 1世帯当たり1か月間の収入と支出（二人以上の世帯）
SRC = ('e-Stat 家計調査 2024年(令和6年) 年報 家計収支編 二人以上の世帯 第3表 '
       '「世帯人員・世帯主の年齢階級別 1世帯当たり1か月間の収入と支出」')
URL = 'https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040297516&fileKind=4'

AGE_COLS = {16: 'all', 22: '~29', 23: '30-39', 24: '40-49', 25: '50-59', 26: '60-69',
            27: '70+', 28: '65+'}
CATS = {23: 'Food', 36: 'Housing', 39: 'Utilities (fuel, light & water)',
        44: 'Furniture & household goods', 51: 'Apparel & footwear',
        60: 'Healthcare', 65: 'Transport & communication', 69: 'Education',
        73: 'Culture & recreation', 78: 'Other consumption expenditure'}
TOTAL_ROW = 22
SIZE_ROW = 17

wb = xlrd.open_workbook('raw/jp_age_4.xlsx')
sh = wb.sheet_by_index(0)

rows = []
sizes = []
for col, band in AGE_COLS.items():
    tot = sh.cell_value(TOTAL_ROW, col)
    tot = float(tot) if isinstance(tot, (int, float)) else None
    if tot:
        rows.append(dict(country='JP', year=2024, age_band=band, category='TOTAL',
                         mean_value=round(tot), share_pct=100.0,
                         unit='JPY per household per month'))
    for r, name in CATS.items():
        v = sh.cell_value(r, col)
        if isinstance(v, (int, float)) and tot:
            rows.append(dict(country='JP', year=2024, age_band=band, category=name,
                             mean_value=round(float(v)), share_pct=round(float(v) / tot * 100, 1),
                             unit='JPY per household per month'))
    sv = sh.cell_value(SIZE_ROW, col)
    if isinstance(sv, (int, float)):
        sizes.append(dict(country='JP', year=2024, age_band=band,
                          hh_size_people=float(sv), note='平均世帯人員 (two-or-more-person households)'))

with open('data/intl_age_consumption.csv', 'a', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['country', 'year', 'age_band', 'category', 'mean_value',
                                      'share_pct', 'unit', 'source_table', 'source_url'])
    for r in rows:
        r = dict(r); r['source_table'] = SRC; r['source_url'] = URL
        w.writerow(r)

with open('data/intl_household_size.csv', 'a', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['country', 'year', 'age_band', 'hh_size_people', 'note'])
    for r in sizes:
        w.writerow(r)

print(len(rows), 'jp rows')
for r in rows:
    print(r['age_band'], r['category'], r['mean_value'], r['share_pct'])
