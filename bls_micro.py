"""BLS CE PUMD (Interview / FMLI) -> single-year-of-age expenditure table.

python bls_micro.py --diag        # diagnostics only
python bls_micro.py               # writes data/us_singleyear.csv etc.
"""
import io, os, sys, zipfile
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw", "bls")

QUARTERS = {
    2023: ("intrvw23.zip", ["fmli232.csv", "fmli233.csv", "fmli234.csv", "fmli241.csv"]),
    2024: ("intrvw24.zip", ["fmli241x.csv", "fmli242.csv", "fmli243.csv", "fmli244.csv"]),
}

CATS = {
    "food": (["FDHOMEPQ", "FDAWAYPQ"], ["FDHOMECQ", "FDAWAYCQ"]),
    "housing": (["HOUSPQ"], ["HOUSCQ"]),
    "transport": (["TRANSPQ"], ["TRANSCQ"]),
    "healthcare": (["HEALTHPQ"], ["HEALTHCQ"]),
    "entertainment": (["ENTERTPQ"], ["ENTERTCQ"]),
    "apparel": (["APPARPQ"], ["APPARCQ"]),
    "education": (["EDUCAPQ"], ["EDUCACQ"]),
}
DETAIL = {
    "personal_insurance_pensions": (["PERINSPQ"], ["PERINSCQ"]),
    "alcohol": (["ALCBEVPQ"], ["ALCBEVCQ"]),
    "personal_care": (["PERSCAPQ"], ["PERSCACQ"]),
    "reading": (["READPQ"], ["READCQ"]),
    "tobacco": (["TOBACCPQ"], ["TOBACCCQ"]),
    "misc": (["MISCPQ"], ["MISCCQ"]),
    "cash_contributions": (["CASHCOPQ"], ["CASHCOCQ"]),
    "total": (["TOTEXPPQ"], ["TOTEXPCQ"]),
}


def load_year(year):
    zipname, files = QUARTERS[year]
    base = zipname.replace(".zip", "")
    z = zipfile.ZipFile(os.path.join(RAW, zipname))
    frames = []
    for fn in files:
        with z.open(f"{base}/{fn}") as f:
            head = pd.read_csv(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"),
                               nrows=0).columns.tolist()
        need = ["NEWID", "AGE_REF", "FAM_SIZE", "FINLWT21"]
        for pq, cq in list(CATS.values()) + list(DETAIL.values()):
            need += pq + cq
        use = [c for c in dict.fromkeys(need) if c in head]
        with z.open(f"{base}/{fn}") as f:
            d = pd.read_csv(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"),
                            usecols=use, low_memory=False)
        d["qfile"] = fn
        frames.append(d)
    return pd.concat(frames, ignore_index=True, sort=False)


def build_cu_year(year, df):
    """One row per CU, annual (12-month) totals.

    Each interview covers 3 months, reported as PQ ('last quarter' part) +
    CQ ('this quarter' part).  A CU interviewed k times in the year is covered
    for 3k months, so annual = sum(PQ+CQ) * 4/k.
    """
    vals = pd.DataFrame({name: df[[c for c in pq if c in df.columns]].sum(axis=1).fillna(0)
                         + df[[c for c in cq if c in df.columns]].sum(axis=1).fillna(0)
                         for name, (pq, cq) in {**CATS, **DETAIL}.items()})
    vals["NEWID"] = df["NEWID"].values
    vals["AGE_REF"] = df["AGE_REF"].values
    vals["FAM_SIZE"] = df["FAM_SIZE"].values
    vals["FINLWT21"] = df["FINLWT21"].values
    vals["qfile"] = df["qfile"].values
    vals["n_q"] = vals.groupby("NEWID")["qfile"].transform("nunique")
    vals["mult"] = 4.0 / vals["n_q"]
    g = vals.groupby("NEWID", as_index=False).agg(
        {**{c: "sum" for c in list(CATS) + list(DETAIL)},
         "AGE_REF": "first", "FAM_SIZE": "first", "FINLWT21": "first",
         "n_q": "first", "mult": "first"})
    for c in list(CATS) + list(DETAIL):
        g[c + "_ann"] = g[c] * g["mult"]
    return g


def wmean(v, w):
    v = np.asarray(v, float); w = np.asarray(w, float)
    m = np.isfinite(v) & np.isfinite(w) & (w > 0)
    return float((v[m] * w[m]).sum() / w[m].sum()) if m.any() else np.nan


if __name__ == "__main__":
    off = pd.read_csv(os.path.join(HERE, "data", "intl_age_consumption.csv"), encoding="utf-8-sig")
    off = off[(off.country == "US") & (off.age_band == "all")]
    for year in (2023, 2024):
        df = load_year(year)
        cu = build_cu_year(year, df)
        print(f"== {year}: rows {len(df)}, CUs {len(cu)}, median interviews {cu.n_q.median():.0f}")
        oy = off[off.year == year].set_index("category_harmonized")["mean_value"]
        rows = []
        for name in list(CATS) + list(DETAIL):
            m = wmean(cu[name + "_ann"], cu.FINLWT21)
            o = oy.get(name if name in oy.index else ("other" if name == "misc" else ""),
                       np.nan)
            rows.append((name, m, o))
        for name, m, o in rows:
            print(f"   {name:30s} micro {m:9.0f}   official {o if pd.notna(o) else '':>9}")
        print("   age range", cu.AGE_REF.min(), cu.AGE_REF.max(),
              "| n<25", int((cu.AGE_REF < 25).sum()), "| n>=85", int((cu.AGE_REF >= 85).sum()))
