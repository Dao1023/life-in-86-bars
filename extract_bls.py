import openpyxl, csv, warnings, os
warnings.filterwarnings('ignore')

AGE_COLS = {  # col index -> label
    2: 'all', 3: '<25', 4: '25-34', 5: '35-44', 6: '45-54',
    7: '55-64', 8: '65+', 9: '65-74', 10: '75+',
}
ITEMS = ['Food', 'Housing', 'Transportation', 'Healthcare', 'Entertainment',
         'Apparel and services', 'Education', 'Personal insurance and pensions']

os.makedirs('data', exist_ok=True)
rows_out = []
size_out = []

for year in (2023, 2024, 2025):
    path = f'raw/bls_age_{year}.xlsx'
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    # index rows by label
    mean_row, share_row, size_row = {}, {}, {}
    total_mean = {}
    for r in range(1, ws.max_row + 1):
        a = ws.cell(r, 1).value
        if not isinstance(a, str):
            continue
        a = a.strip()
        if a in ITEMS:
            nxt = ws.cell(r + 1, 1).value
            if nxt == 'Mean':
                mean_row[a] = r + 1
                share_row[a] = r + 2
        if a == 'Average annual expenditures':
            # mean is r+1 ('Mean')
            if ws.cell(r + 1, 1).value == 'Mean':
                total_mean = {c: ws.cell(r + 1, c).value for c in range(2, 11)}
        if a == 'Average number in consumer unit':
            pass
        if a == 'People':
            size_row = {c: ws.cell(r, c).value for c in range(2, 11)}

    for col, band in AGE_COLS.items():
        tot = total_mean.get(col)
        if isinstance(tot, (int, float)):
            rows_out.append(dict(country='US', year=year, age_band=band, category='TOTAL',
                                 mean_value=tot, share_pct=100.0, unit='USD per consumer unit per year'))
        s = 0.0
        for it in ITEMS:
            mr = mean_row.get(it)
            if not mr:
                continue
            mv = ws.cell(mr, col).value
            sv = ws.cell(share_row[it], col).value
            if not isinstance(mv, (int, float)):
                continue
            rows_out.append(dict(country='US', year=year, age_band=band, category=it,
                                 mean_value=mv, share_pct=sv if isinstance(sv, (int, float)) else '',
                                 unit='USD per consumer unit per year'))
            s += mv
        if isinstance(tot, (int, float)):
            other = tot - s
            rows_out.append(dict(country='US', year=year, age_band=band, category='Other (residual)',
                                 mean_value=round(other, 1),
                                 share_pct=round(other / tot * 100, 1),
                                 unit='USD per consumer unit per year'))
    for col, band in AGE_COLS.items():
        v = size_row.get(col)
        if isinstance(v, (int, float)):
            size_out.append(dict(country='US', year=year, age_band=band, hh_size_people=v, note='people per consumer unit'))

with open('data/intl_age_consumption.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['country', 'year', 'age_band', 'category', 'mean_value',
                                      'share_pct', 'unit', 'source_table', 'source_url'])
    w.writeheader()
    for r in rows_out:
        r = dict(r)
        r['source_table'] = f'BLS CE Table 1300 (Age of reference person), {year}'
        r['source_url'] = f'https://www.bls.gov/cex/tables/calendar-year/mean-item-share-average-standard-error/reference-person-age-ranges-{year}.xlsx'
        w.writerow(r)

with open('data/intl_household_size.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['country', 'year', 'age_band', 'hh_size_people', 'note'])
    w.writeheader()
    for r in size_out:
        w.writerow(r)

print('rows', len(rows_out), 'sizes', len(size_out))
for r in rows_out:
    if r['year'] == 2024 and r['category'] in ('TOTAL', 'Other (residual)'):
        print(r)
