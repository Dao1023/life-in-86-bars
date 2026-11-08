"""Add chart-ready columns to data/us_singleyear.csv.

* category8      : 8-way grouping for the stacked chart (personal insurance and
                   pensions folded into "other", matching the harmonised
                   category set used in data/intl_age_consumption.csv)
* cu_size_mean   : mean FAM_SIZE (persons per consumer unit) at that age
* mean_usd_cal   : category level calibrated to the official Table 1300 value
                   (micro / official ratio applied at the all-CU level, one
                   factor per category). This is a level fix, NOT interpolation:
                   every age still carries its own observed micro mean.
* age_topcoded   : True for AGE_REF = 87, which is BLS's top code and behaves
                   like an "83 and older" bucket (no CUs are coded 83-86).
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "data", "us_singleyear.csv")
long = pd.read_csv(P)

CAT8 = {
    "food": "food",
    "housing": "housing",
    "transport": "transport",
    "healthcare": "healthcare",
    "entertainment": "entertainment",
    "apparel": "apparel",
    "education": "education",
    "personal_insurance_pensions": "other",
    "other": "other",
}
long["category8"] = long.category.map(CAT8)
long["age_topcoded"] = long.age >= 87
long["interpolated"] = False

# mean household size by age (CU level only; it is a property of the CU)
hh = (long[long.measure == "per_consumer_unit"]
      .groupby("age")["n"].first())
cu_size = json.load(open(os.path.join(HERE, "data", "us_cu_size_by_age.json")))
cu_size = {int(k): float(v) for k, v in cu_size.items()}
long["cu_size_mean"] = long.age.map(cu_size).round(3)

# category-level calibration factors, fitted on the all-CU row
chk = pd.read_csv(os.path.join(HERE, "data", "us_singleyear_check.csv"))
fac = {r.category: (r.official / r.micro) for r in chk.itertuples() if r.micro}
long["mean_usd_cal"] = [round(r.mean_usd * fac.get(r.category, 1.0), 1)
                        for r in long.itertuples()]

cols = ["age", "category", "category8", "mean_usd", "mean_usd_cal", "share_pct",
        "se_usd", "n", "low_n", "age_topcoded", "year", "weight_var", "measure",
        "cu_size_mean", "interpolated", "source"]
long = long[cols]
long.to_csv(P, index=False, encoding="utf-8-sig")
print(long.shape, long.measure.value_counts().to_dict())
print(long.head(3).to_string())
