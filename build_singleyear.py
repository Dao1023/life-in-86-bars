"""BLS CE PUMD (Interview/FMLI) -> single-year-of-age x 9-category expenditure table.

Outputs
  data/us_singleyear.csv          long table, age x category, CU-level and per-person
  data/us_singleyear_5y.csv       micro 5-year groups vs official Table 1300, with replicate SEs
  data/us_singleyear_meta.json    run metadata

Method
  * one PUMD interview record = 3 months of expenditure, reported as PQ ("last
    quarter" part) + CQ ("this quarter" part).  annual = 4 * (PQ + CQ).
  * every CU appears once per year in the pooled calendar-year file set, weight
    FINLWT21; replicate weights WTREP01..44 give design-based standard errors.
  * per-person columns divide by FAM_SIZE (number of CU members) and weight by
    FINLWT21 * FAM_SIZE, i.e. the average over *persons*, not over CUs.
"""
import io, json, os, zipfile
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw", "bls")

QUARTERS = {
    2023: ("intrvw23.zip", ["fmli232.csv", "fmli233.csv", "fmli234.csv", "fmli241.csv"]),
    2024: ("intrvw24.zip", ["fmli241x.csv", "fmli242.csv", "fmli243.csv", "fmli244.csv"]),
}

# 9 official Table 1300 headings. Each entry: (PQ cols, CQ cols).
# GROCERPQ/GROCERCQ only exist in the 2024 Q2-Q4 files, where they replace
# FDHOMEPQ/FDHOMECQ (those are all zero there).
CATS = {
    "food": (["FDHOMEPQ", "FDAWAYPQ", "GROCERPQ"], ["FDHOMECQ", "FDAWAYCQ", "GROCERCQ"]),
    "housing": (["HOUSPQ"], ["HOUSCQ"]),
    "transport": (["TRANSPQ"], ["TRANSCQ"]),
    "healthcare": (["HEALTHPQ"], ["HEALTHCQ"]),
    "entertainment": (["ENTERTPQ"], ["ENTERTCQ"]),
    "apparel": (["APPARPQ"], ["APPARCQ"]),
    "education": (["EDUCAPQ"], ["EDUCACQ"]),
    "personal_insurance_pensions": (["PERINSPQ"], ["PERINSCQ"]),
    "total": (["TOTEXPPQ"], ["TOTEXPCQ"]),
}
OTHER_PARTS = {  # residual = total - (8 named) ; these document what is inside
    "alcohol": (["ALCBEVPQ"], ["ALCBEVCQ"]),
    "personal_care": (["PERSCAPQ"], ["PERSCACQ"]),
    "reading": (["READPQ"], ["READCQ"]),
    "tobacco": (["TOBACCPQ"], ["TOBACCCQ"]),
    "misc": (["MISCPQ"], ["MISCCQ"]),
    "cash_contributions": (["CASHCOPQ"], ["CASHCOCQ"]),
}
REPS = [f"WTREP{i:02d}" for i in range(1, 45)]


def load_year(year):
    zipname, files = QUARTERS[year]
    base = zipname.replace(".zip", "")
    z = zipfile.ZipFile(os.path.join(RAW, zipname))
    frames = []
    for fn in files:
        with z.open(f"{base}/{fn}") as f:
            head = pd.read_csv(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"),
                               nrows=0).columns.tolist()
        need = ["NEWID", "AGE_REF", "FAM_SIZE", "FINLWT21"] + REPS
        for pq, cq in list(CATS.values()) + list(OTHER_PARTS.values()):
            need += pq + cq
        use = [c for c in dict.fromkeys(need) if c in head]
        with z.open(f"{base}/{fn}") as f:
            d = pd.read_csv(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"),
                            usecols=use, low_memory=False)
        d["qfile"] = fn
        frames.append(d)
    df = pd.concat(frames, ignore_index=True, sort=False)
    for c in REPS:
        if c not in df:
            df[c] = np.nan
    return df


def build(df):
    vals = {}
    for name, (pq, cq) in {**CATS, **OTHER_PARTS}.items():
        pq = [c for c in pq if c in df.columns]
        cq = [c for c in cq if c in df.columns]
        vals[name] = 4.0 * (df[pq].sum(axis=1).fillna(0) + df[cq].sum(axis=1).fillna(0))
    out = pd.DataFrame(vals)
    named = ["food", "housing", "transport", "healthcare", "entertainment",
             "apparel", "education", "personal_insurance_pensions"]
    out["other"] = out["total"] - out[named].sum(axis=1)
    out["AGE_REF"] = df["AGE_REF"].astype(float)
    out["FAM_SIZE"] = df["FAM_SIZE"].astype(float).clip(lower=1)
    out["FINLWT21"] = df["FINLWT21"].astype(float)
    for c in REPS:
        out[c] = df[c].astype(float)
    # sanity: residual should stay >= 0 for the vast majority
    return out


CATS9 = ["food", "housing", "transport", "healthcare", "entertainment",
         "apparel", "education", "personal_insurance_pensions", "other"]


def wmean(v, w):
    v = np.asarray(v, float); w = np.asarray(w, float)
    m = np.isfinite(v) & np.isfinite(w) & (w > 0)
    return float((v[m] * w[m]).sum() / w[m].sum()) if m.any() else np.nan


def single_year_table(cu, per_person=False):
    """Weighted mean by exact AGE_REF, with replicate-weight SE."""
    v_scale = 1.0 / cu["FAM_SIZE"].values if per_person else np.ones(len(cu))
    w_base = cu["FINLWT21"].values * (cu["FAM_SIZE"].values if per_person else 1.0)
    ages = cu["AGE_REF"].values.astype(int)
    uages = np.arange(ages.min(), ages.max() + 1)
    idx = np.searchsorted(uages, ages)
    rows = []
    # blank replicate weight = CU not in that replicate half-sample -> weight 0
    wh = np.nan_to_num(np.vstack([cu[c].values for c in REPS]), nan=0.0)
    if per_person:
        wh = wh * cu["FAM_SIZE"].values[None, :]
    for cat in CATS9:
        v = cu[cat].values * v_scale
        num = np.bincount(idx, weights=v * w_base, minlength=len(uages))
        den = np.bincount(idx, weights=w_base, minlength=len(uages))
        est = np.divide(num, den, out=np.full(len(uages), np.nan), where=den > 0)
        # replicate estimates
        reps = np.empty((len(REPS), len(uages)))
        for r in range(len(REPS)):
            wr = wh[r]
            n_r = np.bincount(idx, weights=v * wr, minlength=len(uages))
            d_r = np.bincount(idx, weights=wr, minlength=len(uages))
            reps[r] = np.divide(n_r, d_r, out=np.full(len(uages), np.nan), where=d_r > 0)
        se = np.sqrt(np.nansum((reps - est) ** 2, axis=0) / (len(REPS) * (len(REPS) - 1)))
        n = np.bincount(idx, minlength=len(uages))
        for j, a in enumerate(uages):
            rows.append(dict(age=int(a), category=cat, value=est[j], se=se[j], n=int(n[j])))
    return pd.DataFrame(rows), uages


def five_year_groups(age):
    a = np.asarray(age, float)
    g = np.full(a.shape, "65+", dtype=object)
    g[a < 25] = "<25"
    g[(a >= 25) & (a < 35)] = "25-34"
    g[(a >= 35) & (a < 45)] = "35-44"
    g[(a >= 45) & (a < 55)] = "45-54"
    g[(a >= 55) & (a < 65)] = "55-64"
    g[(a >= 65) & (a < 75)] = "65-74"
    g[a >= 75] = "75+"
    return g


if __name__ == "__main__":
    meta = {}
    official = pd.read_excel(os.path.join(RAW, "table1300_2024.xlsx"), header=None)
    official23 = pd.read_excel(os.path.join(RAW, "table1300_2023.xlsx"), header=None)

    def parse_table(d):
        out = {}
        for i in range(len(d) - 1):
            name = str(d.iloc[i, 0]).strip()
            if str(d.iloc[i + 1, 0]).strip() == "Mean":
                try:
                    out[name] = float(d.iloc[i + 1, 1])
                except (TypeError, ValueError):
                    pass
        return out

    off = {2023: parse_table(official23), 2024: parse_table(official)}

    all_frames = {}
    for year in (2023, 2024):
        df = load_year(year)
        cu = build(df)
        all_frames[year] = cu
        print(year, "records", len(cu), "age", cu.AGE_REF.min(), cu.AGE_REF.max(),
              "median n/age", int(np.median(np.bincount(cu.AGE_REF.astype(int))[
                  np.bincount(cu.AGE_REF.astype(int)) > 0])))

    # ---------- primary year = 2023 (complete, consistent schema) ----------
    year = 2023
    cu = all_frames[year]
    cu["age_grp"] = five_year_groups(cu.AGE_REF)

    out_rows = []
    for per_person, suffix in ((False, "cu"), (True, "person")):
        tab, uages = single_year_table(cu, per_person=per_person)
        tidx = tab.pivot(index="age", columns="category", values="value")
        tidx = tidx.dropna(how="all")
        age_total = tidx.sum(axis=1, min_count=1)
        for _, r in tab.iterrows():
            if r.age not in age_total.index or not np.isfinite(age_total.loc[r.age]) or age_total.loc[r.age] <= 0:
                continue
            out_rows.append(dict(
                age=int(r.age), category=r.category,
                mean_usd=round(float(r.value), 1),
                share_pct=round(100 * float(r.value) / float(age_total.loc[r.age]), 2),
                se_usd=round(float(r.se), 1), n=int(r.n),
                low_n=bool(r.n < 30),
                year=year, weight_var="FINLWT21",
                measure="per_consumer_unit" if not per_person else "per_person",
                source="BLS CE Interview Survey (PUMD) FMLI 2023, own aggregation",
            ))
    long = pd.DataFrame(out_rows)

    # ---------- 5-year comparison ----------
    comp_rows = []
    GMASK = {
        "<25": lambda a: a < 25,
        "25-34": lambda a: (a >= 25) & (a < 35),
        "35-44": lambda a: (a >= 35) & (a < 45),
        "45-54": lambda a: (a >= 45) & (a < 55),
        "55-64": lambda a: (a >= 55) & (a < 65),
        "65+": lambda a: a >= 65,
        "65-74": lambda a: (a >= 65) & (a < 75),
        "75+": lambda a: a >= 75,
    }
    for grp in ["<25", "25-34", "35-44", "45-54", "55-64", "65+", "65-74", "75+"]:
        sub = cu[GMASK[grp](cu["AGE_REF"].values)]
        for cat, label in [("food", "Food"), ("housing", "Housing"),
                           ("transport", "Transportation"), ("healthcare", "Healthcare"),
                           ("entertainment", "Entertainment"),
                           ("apparel", "Apparel and services"), ("education", "Education"),
                           ("personal_insurance_pensions", "Personal insurance and pensions"),
                           ("total", "Total expenditures")]:
            m = wmean(sub[cat], sub.FINLWT21)
            se = np.nan
            reps = [wmean(sub[cat], sub[r]) for r in REPS]
            reps = np.array([x for x in reps if np.isfinite(x)])
            if len(reps) > 2:
                se = float(np.sqrt(np.sum((reps - m) ** 2) / (len(reps) * (len(reps) - 1))))
            comp_rows.append(dict(age_group=grp, category=cat, micro_mean=round(m, 1),
                                  micro_se=round(se, 1) if se == se else None,
                                  n_cu=int(len(sub)), year=year))
    comp = pd.DataFrame(comp_rows)

    # official values by 5-year group, read from the harmonised official CSV
    # (data/intl_age_consumption.csv, already transcribed from Table 1300).
    # We do NOT parse the xlsx here: footnote markers ("c/") shift its columns
    # row by row, which produced silently misaligned values.
    label_map = {"Food": "food", "Housing": "housing", "Transportation": "transport",
                 "Healthcare": "healthcare", "Entertainment": "entertainment",
                 "Apparel and services": "apparel", "Education": "education",
                 "Personal insurance and pensions": "personal_insurance_pensions",
                 "Other (residual)": "other", "TOTAL": "total"}
    csv = pd.read_csv(os.path.join(HERE, "data", "intl_age_consumption.csv"), encoding="utf-8-sig")
    csv["year_s"] = csv["year"].astype(str).str.strip()
    csv = csv[(csv.country == "US") & (csv.year_s == str(year))]
    offgrp = {(r.age_band, label_map[r.category]): float(r.mean_value)
              for r in csv.itertuples()
              if r.category in label_map and np.isfinite(r.mean_value)}
    comp["official_mean"] = [offgrp.get((r.age_group, r.category), np.nan)
                             for r in comp.itertuples()]
    comp["diff_pct"] = (100 * (comp.micro_mean - comp.official_mean) / comp.official_mean).round(1)
    comp["z"] = ((comp.micro_mean - comp.official_mean) / comp.micro_se).round(1)
    comp["within_sampling_error"] = comp.z.abs() < 1.96

    # all-CU totals check
    allcu = {cat: wmean(cu[cat], cu.FINLWT21) for cat in CATS9 + ["total"]}
    offall = {cat: offgrp.get(("all", cat), np.nan) for cat in CATS9 + ["total"]}
    check = pd.DataFrame([dict(category=c, micro=round(allcu[c], 1),
                               official=round(float(offall[c]), 1),
                               diff_pct=round(100 * (allcu[c] - float(offall[c])) / float(offall[c]), 1))
                          for c in CATS9 + ["total"]])

    long.to_csv(os.path.join(HERE, "data", "us_singleyear.csv"), index=False, encoding="utf-8-sig")
    comp.to_csv(os.path.join(HERE, "data", "us_singleyear_5y.csv"), index=False, encoding="utf-8-sig")
    check.to_csv(os.path.join(HERE, "data", "us_singleyear_check.csv"), index=False, encoding="utf-8-sig")
    meta = dict(year=year, n_cu=int(len(cu)), age_min=int(cu.AGE_REF.min()),
                age_max=int(cu.AGE_REF.max()),
                median_n_per_age=float(np.median(np.bincount(cu.AGE_REF.astype(int))[
                    np.bincount(cu.AGE_REF.astype(int)) > 0])),
                interpolated=False, weights="FINLWT21 (calibration final weight)",
                replicate_weights="WTREP01-WTREP44")
    json.dump(meta, open(os.path.join(HERE, "data", "us_singleyear_meta.json"), "w"), indent=1)
    print(check.to_string(index=False))
    print(meta)
    print(long.groupby("measure").size())
