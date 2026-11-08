"""Batch literature verification via OpenAlex + Crossref. Writes markdown evidence table."""
import sys, json, os, urllib.parse, importlib.util, time

_here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("f", os.path.join(_here, "fetch.py"))
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)

QUERIES = [
 ("Modigliani-Brumberg1954", "Utility analysis and the consumption function"),
 ("Ando-Modigliani1963", "The Life Cycle Hypothesis of Saving: Aggregate Implications and Tests"),
 ("Modigliani1966", "The Life Cycle Hypothesis of Saving, the Demand for Wealth and the Supply of Capital"),
 ("Browning-Crossley2001", "The Life-Cycle Model of Consumption and Saving"),
 ("Gourinchas-Parker2002", "Consumption over the Life Cycle Gourinchas Parker Econometrica"),
 ("FV-Krueger2007", "Consumption over the Life Cycle: Facts from Consumer Expenditure Survey Data"),
 ("Attanasio-Browning1995", "Consumption over the Life Cycle and over the Business Cycle"),
 ("Banks-Blundell-Tanner1998", "Is There a Retirement-Savings Puzzle"),
 ("Deaton-Paxson1994", "Intertemporal Choice and Inequality"),
 ("Wells-Gubar1966", "Life cycle concept in marketing research"),
 ("Murphy-Staples1979", "A modernized family life cycle"),
 ("Gilly-Enis1982", "Recycling the family life cycle: a proposal for redefinition"),
 ("Carroll1997", "Buffer-stock saving and the life cycle/permanent income hypothesis"),
 ("Lee-Mason2011", "Population Aging and the Generational Economy"),
 ("Attanasio-Pistaferri2016", "Consumption Inequality"),
 ("Skinner2007?", "The dynamics of housing and consumption over the life cycle"),
 ("USDA2015", "Expenditures on Children by Families"),
 ("Browning-Crossley2009", "Shocks, Stocks, and Socks: Smoothing Consumption Over a Temporary Income Loss"),
 ("Hurd1990", "Research on the elderly: economic status, retirement, and consumption and saving"),
 ("Fernandez-Villaverde2007b", "Consumption over the life cycle facts from consumer expenditure survey data"),
]

def oa(q, n=4, extra=""):
    u = "https://api.openalex.org/works?" + urllib.parse.urlencode(
        {"search": q, "per-page": n, "mailto": "research@example.org"}) + extra
    st, _, t = f.get(u, timeout=30)
    d = json.loads(t)
    out = []
    for w in d.get("results", []):
        src = (w.get("primary_location") or {}).get("source") or {}
        bib = w.get("biblio") or {}
        out.append({
            "year": w.get("publication_year"),
            "title": w.get("display_name"),
            "venue": src.get("display_name"),
            "vol": bib.get("volume"), "issue": bib.get("issue"),
            "fp": bib.get("first_page"), "lp": bib.get("last_page"),
            "doi": w.get("doi"),
            "cites": w.get("cited_by_count"),
            "authors": [a["author"]["display_name"] for a in w.get("authorships", [])][:4],
            "oa_url": (w.get("primary_location") or {}).get("landing_page_url"),
        })
    return out

lines = []
for tag, q in QUERIES:
    try:
        res = oa(q)
    except Exception as e:
        lines.append(f"### {tag}\n- QUERY FAILED: {e}\n")
        continue
    lines.append(f"### {tag}\nquery: `{q}`")
    if not res:
        lines.append("- (no results)")
    for r in res[:3]:
        au = ", ".join(r["authors"])
        lines.append(f"- {r['year']} | {r['title']} | {au} | *{r['venue']}* {r['vol']}({r['issue']}) {r['fp']}-{r['lp']} | doi:{r['doi']} | cites={r['cites']}")
    lines.append("")
    time.sleep(0.3)

out = os.path.join(os.path.dirname(_here), "research", "_evidence-lit.md")
open(out, "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
