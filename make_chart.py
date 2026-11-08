# -*- coding: utf-8 -*-
"""Draw the 3-country harmonised stacked bar comparison from data/intl_age_consumption.csv."""
import pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
df = pd.read_csv('data/intl_age_consumption.csv')
d = df[df.category_harmonized != 'TOTAL']
order = ['food', 'housing', 'transport', 'healthcare', 'education', 'apparel', 'leisure', 'other']
labels = {'food': 'Food', 'housing': 'Housing(+utilities)', 'transport': 'Transport(+comm.)',
          'healthcare': 'Healthcare', 'education': 'Education', 'apparel': 'Apparel',
          'leisure': 'Leisure', 'other': 'Other'}

cfg = [('US', '2024', ['<25', '25-34', '35-44', '45-54', '55-64', '65-74', '75+'],
        'US BLS CE 2024 (USD/yr, per consumer unit)'),
       ('JP', '2024', ['~29', '30-39', '40-49', '50-59', '60-69', '70+'],
        'Japan 家計調査 2024 (JPY/mo, per household)'),
       ('UK', 'FYE2018', ['<30', '30-49', '50-64', '65-74', '75+'],
        'UK ONS LCF FYE2018 (GBP/wk, per household)')]

fig, axes = plt.subplots(1, 3, figsize=(17, 5.6))
cmap = plt.get_cmap('tab20')
for ax, (c, y, bands, title) in zip(axes, cfg):
    g = d[(d.country == c) & (d.year.astype(str) == str(y))]
    p = g.pivot_table(index='age_band', columns='category_harmonized', values='mean_value', aggfunc='sum')
    p = p.reindex(index=bands, columns=order)
    s = p.div(p.sum(axis=1), axis=0) * 100
    bot = pd.Series(0.0, index=s.index)
    for i, cat in enumerate(order):
        ax.bar(s.index, s[cat].fillna(0), bottom=bot, label=labels[cat],
               color=cmap(i / len(order)), width=.75)
        bot += s[cat].fillna(0)
    ax.set_title(title, fontsize=10)
    ax.set_ylim(0, 100)
    ax.tick_params(axis='x', rotation=45, labelsize=8)
    ax.set_ylabel('share of total consumption (%)')
axes[0].legend(fontsize=7, ncol=2, loc='lower right', framealpha=.9)
plt.suptitle('Consumption structure by age of household head — harmonised 8-bucket shares', fontsize=12)
plt.tight_layout()
plt.savefig('viz/harmonised_shares_by_age.png', dpi=150)
print('saved viz/harmonised_shares_by_age.png')
