# -*- coding: utf-8 -*-
"""Rebuild data/intl_age_consumption.csv and data/intl_household_size.csv from raw official files.

Sources (all downloaded by fetch.py, kept in raw/):
  US: BLS CE Table 1300 (reference person age ranges) 2023/2024/2025 xlsx
  JP: e-Stat 家計調査 2024 年報 第3表 (statInfId 000040297516)
  UK: ONS LCF Table A9 / A10, FYE2018 (latest published edition of the by-age tables)

Every row keeps the original published unit; share_pct is either the published share
(US) or computed as item/total*100 from the same table (JP, UK).
"""
import csv, os, warnings
import openpyxl, xlrd

warnings.filterwarnings('ignore')
os.makedirs('data', exist_ok=True)

HARM = {  # original category -> harmonised bucket used in the cross-country summary table
    # US
    'Food': 'food', 'Housing': 'housing', 'Transportation': 'transport',
    'Healthcare': 'healthcare', 'Apparel and services': 'apparel',
    'Entertainment': 'leisure', 'Education': 'education',
    'Personal insurance and pensions': 'other', 'Other (residual)': 'other',
    # JP
    '食料': 'food', '住居': 'housing', '光熱・水道': 'housing',
    '家具・家事用品': 'other', '被服及び履物': 'apparel', '保健医療': 'healthcare',
    '交通・通信': 'transport', '教育': 'education', '教養娯楽': 'leisure',
    'その他の消費支出': 'other',
    # UK
    'Food & non-alcoholic drinks': 'food',
    'Alcoholic drinks, tobacco & narcotics': 'other',
    'Clothing & footwear': 'apparel',
    'Housing(net), fuel & power': 'housing',
    'Household goods & services': 'other',
    'Health': 'healthcare',
    'Transport': 'transport',
    'Communication': 'housing',
    'Recreation & culture': 'leisure',
    'Education': 'education',
    'Restaurants & hotels': 'other',
    'Miscellaneous goods & services': 'other',
    'Other expenditure items': 'other',
    'TOTAL': 'TOTAL',
}

rows_out, size_out = [], []


def add(country, year, band, cat, mean, share, unit, hh, table, url, note=''):
    rows_out.append(dict(country=country, year=year, age_band=band, category=cat,
                         category_harmonized=HARM.get(cat, ''), mean_value=mean,
                         share_pct=share, unit=unit, hh_size_people=hh,
                         source_table=table, source_url=url, note=note))


# ---------------------------------------------------------------- US / BLS
AGE_COLS = {2: 'all', 3: '<25', 4: '25-34', 5: '35-44', 6: '45-54',
            7: '55-64', 8: '65+', 9: '65-74', 10: '75+'}
ITEMS = ['Food', 'Housing', 'Transportation', 'Healthcare', 'Entertainment',
         'Apparel and services', 'Education', 'Personal insurance and pensions']

for year in (2023, 2024, 2025):
    wb = openpyxl.load_workbook(f'raw/bls_age_{year}.xlsx', data_only=True)
    ws = wb[wb.sheetnames[0]]
    mean_row, share_row, total_mean, size_row = {}, {}, {}, {}
    for r in range(1, ws.max_row + 1):
        a = ws.cell(r, 1).value
        if not isinstance(a, str):
            continue
        a = a.strip()
        if a in ITEMS and ws.cell(r + 1, 1).value == 'Mean':
            mean_row[a] = r + 1
            share_row[a] = r + 2
        if a == 'Average annual expenditures' and ws.cell(r + 1, 1).value == 'Mean':
            total_mean = {c: ws.cell(r + 1, c).value for c in range(2, 11)}
        if a == 'People':
            size_row = {c: ws.cell(r, c).value for c in range(2, 11)}

    url = ('https://www.bls.gov/cex/tables/calendar-year/mean-item-share-average-standard-error/'
           f'reference-person-age-ranges-{year}.xlsx')
    tbl = f'BLS Consumer Expenditure Survey, Table 1300 (Age of reference person), {year}'
    unit = 'USD per consumer unit per year'
    for col, band in AGE_COLS.items():
        tot = total_mean.get(col)
        hh = size_row.get(col)
        note = '' if isinstance(tot, (int, float)) else 'not published for this age band'
        if isinstance(tot, (int, float)):
            add('US', year, band, 'TOTAL', tot, 100.0, unit, hh, tbl, url)
        s = 0.0
        for it in ITEMS:
            mr = mean_row.get(it)
            if not mr:
                continue
            mv = ws.cell(mr, col).value
            sv = ws.cell(share_row[it], col).value
            if not isinstance(mv, (int, float)):
                add('US', year, band, it, '', '', unit, hh, tbl, url, 'not published')
                continue
            add('US', year, band, it, mv,
                sv if isinstance(sv, (int, float)) else round(mv / tot * 100, 1),
                unit, hh, tbl, url)
            s += mv
        if isinstance(tot, (int, float)):
            other = round(tot - s, 1)
            add('US', year, band, 'Other (residual)', other, round(other / tot * 100, 1),
                unit, hh, tbl, url, 'TOTAL minus the 8 listed categories (insurance/pensions, cash contributions, misc.)')
        if isinstance(hh, (int, float)):
            size_out.append(dict(country='US', year=year, age_band=band,
                                 hh_size_people=hh, note='people per consumer unit (Table 1300)'))

# ---------------------------------------------------------------- JP / 家計調査
JP_TBL = ('e-Stat 家計調査 2024年(令和6年) 年報 家計収支編 二人以上の世帯 第3表 '
          '「世帯人員・世帯主の年齢階級別 1世帯当たり1か月間の収入と支出」')
JP_URL = 'https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040297516&fileKind=4'
JP_AGE = {16: 'all', 22: '~29', 23: '30-39', 24: '40-49', 25: '50-59', 26: '60-69',
          27: '70+', 28: '65+'}
JP_CATS = {23: '食料', 36: '住居', 39: '光熱・水道', 44: '家具・家事用品',
           51: '被服及び履物', 60: '保健医療', 65: '交通・通信', 69: '教育',
           73: '教養娯楽', 78: 'その他の消費支出'}

sh = xlrd.open_workbook('raw/jp_age_4.xlsx').sheet_by_index(0)
for col, band in JP_AGE.items():
    tot = sh.cell_value(22, col)
    tot = float(tot) if isinstance(tot, (int, float)) and tot else None
    hh = sh.cell_value(17, col)
    hh = float(hh) if isinstance(hh, (int, float)) else ''
    if tot:
        add('JP', 2024, band, 'TOTAL', round(tot), 100.0, 'JPY per household per month', hh, JP_TBL, JP_URL)
    for r, name in JP_CATS.items():
        v = sh.cell_value(r, col)
        if isinstance(v, (int, float)) and tot:
            add('JP', 2024, band, name, round(float(v)), round(float(v) / tot * 100, 1),
                'JPY per household per month', hh, JP_TBL, JP_URL)
    if hh != '':
        size_out.append(dict(country='JP', year=2024, age_band=band, hh_size_people=hh,
                             note='平均世帯人員, two-or-more-person households (第3表 世帯人員)'))

# ---------------------------------------------------------------- UK / ONS LCF A9
UK_URL = ('https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/personalandhouseholdfinances/'
          'expenditure/datasets/householdexpenditurebyageofhouseholdreferencepersonuktablea9/'
          'financialyearending2018/a9201718rerun.xls')
UK_TBL = 'ONS Living Costs and Food Survey, Table A9 (household expenditure by age of HRP), FYE2018'
UK_AGE = {4: '<30', 5: '30-49', 6: '50-64', 7: '65-74', 8: '75+', 9: 'all'}
UK_ROWS = {21: 'Food & non-alcoholic drinks', 23: 'Alcoholic drinks, tobacco & narcotics',
           25: 'Clothing & footwear', 27: 'Housing(net), fuel & power',
           29: 'Household goods & services', 31: 'Health', 33: 'Transport',
           35: 'Communication', 37: 'Recreation & culture', 39: 'Education',
           41: 'Restaurants & hotels', 43: 'Miscellaneous goods & services',
           49: 'Other expenditure items'}
uk = xlrd.open_workbook('raw/uk_a9_fye2018.xls').sheet_by_index(0)
uk_size = {c: uk.cell_value(15, c) for c in UK_AGE}
for col, band in UK_AGE.items():
    tot = uk.cell_value(52, col)
    hh = uk_size.get(col)
    hh = hh if isinstance(hh, (int, float)) else ''
    if isinstance(tot, (int, float)):
        add('UK', 'FYE2018', band, 'TOTAL', tot, 100.0, 'GBP per household per week', hh, UK_TBL, UK_URL)
    for r, name in UK_ROWS.items():
        v = uk.cell_value(r, col)
        if isinstance(v, (int, float)) and isinstance(tot, (int, float)):
            add('UK', 'FYE2018', band, name, v, round(v / tot * 100, 2),
                'GBP per household per week', hh, UK_TBL, UK_URL)
        else:
            add('UK', 'FYE2018', band, name, '', '', 'GBP per household per week', hh,
                UK_TBL, UK_URL, 'published as ".." (not available / sample too small)')
    if hh != '':
        size_out.append(dict(country='UK', year='FYE2018', age_band=band,
                             hh_size_people=hh, note='weighted average persons per household (Table A9)'))

# ---------------------------------------------------------------- write
F = ['country', 'year', 'age_band', 'category', 'category_harmonized', 'mean_value',
     'share_pct', 'unit', 'hh_size_people', 'source_table', 'source_url', 'note']
with open('data/intl_age_consumption.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=F)
    w.writeheader()
    for r in rows_out:
        w.writerow(r)

with open('data/intl_household_size.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['country', 'year', 'age_band', 'hh_size_people', 'note'])
    w.writeheader()
    for r in size_out:
        w.writerow(r)

print('consumption rows', len(rows_out), 'size rows', len(size_out))
from collections import Counter
print(Counter((r['country'], str(r['year'])) for r in rows_out))
