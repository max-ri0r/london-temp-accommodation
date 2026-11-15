"""Rents, pay and temporary accommodation in London.

The chain examined: private rents rise faster than low pay -> private tenancies end
-> households cannot find another affordable home -> councils place them in
temporary accommodation (TA).

Inputs (built by load_ta.py / load_reasons.py, or downloaded to data/raw):
  data/clean/ta_london_quarterly.csv       MHCLG H-CLIC TA1, quarter-end snapshots
  data/clean/reasons_london_quarterly.csv  MHCLG H-CLIC A2P/A2R, reasons for homelessness
  data/clean/rents_london_monthly.csv      ONS Price Index of Private Rents (PIPR)
  data/raw/ashe_resident_ft_annual.csv     ONS ASHE (resident), full-time gross annual pay
  data/raw/cpih_l522.csv                   ONS CPIH all-items index (L522)

Each figure is saved with a full caption (title, notes, source) underneath, and the
captions are also written to figures/captions.md for the README.
"""
import textwrap
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mt

plt.rcParams.update({"figure.dpi": 150, "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.3})
LONDON = "E12000007"
FIG = "figures/"
PAY = {"pay_p25": "lower quartile (25th percentile)", "pay_median": "median",
       "pay_p75": "upper quartile (75th percentile)"}
CAPTIONS = []

SRC_TA = "MHCLG, Statutory homelessness in England, detailed local authority tables, Table TA1 (H-CLIC)."
SRC_REASONS = "MHCLG, Statutory homelessness in England, detailed local authority tables, Tables A2P and A2R (H-CLIC)."
SRC_RENT_PAY = ("ONS, Price Index of Private Rents (PIPR), October 2026 release; ONS, Annual Survey of Hours and "
                "Earnings (ASHE), resident analysis, via Nomis; ONS, CPIH index (series L522).")


def save(fig, ax, n, name, title, notes, source):
    """Save a figure with an academic-style caption underneath (Figure n. Title. Notes. Source.)."""
    ax.set_title("")
    width = 120 if fig.get_figwidth() >= 7 else 100
    text = (textwrap.fill(f"Figure {n}. {title}", width) + "\n\n"
            + textwrap.fill("Notes: " + notes, width) + "\n\n"
            + textwrap.fill("Source: " + source, width))
    fig.tight_layout()
    fig.text(0.01, -0.01, text, ha="left", va="top", fontsize=7.2, wrap=False,
             transform=fig.transFigure, linespacing=1.35)
    fig.savefig(FIG + name, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    CAPTIONS.append((n, name, title, notes, source))


# ---------- load ----------
ta = pd.read_csv("data/clean/ta_london_quarterly.csv", parse_dates=["date"]).drop_duplicates(["code", "date"])
reasons = pd.read_csv("data/clean/reasons_london_quarterly.csv", parse_dates=["date"])
rent = pd.read_csv("data/clean/rents_london_monthly.csv", parse_dates=["date"])
rent["rent_mean"] = pd.to_numeric(rent["rent_mean"], errors="coerce")
ashe = pd.read_csv("data/raw/ashe_resident_ft_annual.csv").rename(columns=str.lower)
ashe["item"] = ashe.item_name.map({"25 percentile": "pay_p25", "Median": "pay_median", "75 percentile": "pay_p75"})
ashe = (ashe.pivot_table(index=["geography_code", "date_name"], columns="item", values="obs_value")
            .reset_index().rename(columns={"geography_code": "code", "date_name": "year"}))
cpi = pd.read_csv("data/raw/cpih_l522.csv", skiprows=8, header=None, names=["period", "cpih"])
cpi = cpi[cpi.period.str.match(r"^\d{4} [A-Z]{3}$")].assign(
    date=lambda d: pd.to_datetime(d.period, format="%Y %b"), cpih=lambda d: d.cpih.astype(float))
names = rent.drop_duplicates("code").set_index("code").area

# April rents matched to April ASHE pay (ASHE reference date is April)
apr = rent[rent.date.dt.month == 4].assign(year=lambda d: d.date.dt.year)
panel = apr.merge(ashe, on=["code", "year"]).merge(cpi[["date", "cpih"]], on="date")
for p in PAY:
    panel[f"rent_share_{p}"] = 12 * panel.rent_mean / panel[p]
panel.to_csv("data/clean/rent_pay_panel.csv", index=False)
lon = panel[panel.code == LONDON].sort_values("year")
y0, y1 = int(lon.year.min()), int(lon.year.max())

lon_ta = ta[ta.code == LONDON].set_index("date").sort_index()
t0, t1 = lon_ta.index.min(), lon_ta.index.max()

# ---------- Figure 1. London TA over time ----------
fig, ax = plt.subplots(figsize=(7.5, 3.8))
ax.plot(lon_ta.index, lon_ta.ta_households, lw=2, label="All households in TA")
ax.plot(lon_ta.index, lon_ta.ta_with_children, lw=2, label="of which: households with children")
ax.plot(lon_ta.index, lon_ta.ta_nightly_paid, lw=2, ls="--", label="of which: in nightly-paid private accommodation")
ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: f"{v/1000:.0f}k"))
ax.set_ylabel("Households (end of quarter)")
ax.set_ylim(0, None)
ax.legend(frameon=False, fontsize=8, loc="lower left")
save(fig, ax, 1, "1_london_ta_trend.png",
     f"Households in temporary accommodation arranged by London boroughs, {t0:%B %Y} to {t1:%B %Y}.",
     "Number of households living in temporary accommodation (TA) arranged by London borough councils under "
     "homelessness legislation, measured on the last day of each quarter. 'Households with children' and "
     "'nightly-paid accommodation' are subsets of the total, not additional households. Nightly-paid, privately "
     "managed, self-contained accommodation is booked by the night from private providers and is generally the most "
     "expensive form of TA for councils. Figures are MHCLG's London regional totals, which include MHCLG's imputed "
     "values for boroughs that did not submit data in a given quarter. Households placed outside London by a London "
     "borough are included.",
     SRC_TA)

# ---------- Figure 2. TA rate by borough, latest quarter ----------
ta_b = ta[ta.code.str.startswith("E09")].copy()
latest = ta_b[ta_b.date == ta_b.date.max()].assign(
    borough=lambda d: d.code.map(names).fillna(d.borough),
    ta_rate=lambda d: d.ta_households / d.households_k).sort_values("ta_rate")
lon_rate = lon_ta.ta_households.iloc[-1] / lon_ta.households_k.iloc[-1]
fig, ax = plt.subplots(figsize=(7.5, 7))
ax.barh(latest.borough, latest.ta_rate)
ax.axvline(lon_rate, color="black", lw=1, ls="--")
ax.text(lon_rate + 0.5, 0, f"London: {lon_rate:.0f}", fontsize=7.5)
ax.set_xlabel("Households in temporary accommodation per 1,000 households")
ax.tick_params(axis="y", labelsize=7.5)
ax.grid(axis="y", visible=False)
save(fig, ax, 2, "2_ta_rate_by_borough.png",
     f"Households in temporary accommodation per 1,000 households, by London borough, {t1:%d %B %Y}.",
     "Households in TA arranged by each borough divided by MHCLG's estimate of the total number of households "
     "in that borough. The dashed line is the rate for London as a whole. Households are counted by the borough that "
     "owes them the homelessness duty, not by where they are living: a household placed by one borough in "
     "accommodation in another (or outside London) counts towards the placing borough. City of London has very few "
     "households, so its rate is sensitive to small changes in numbers.",
     SRC_TA)

# ---------- Figure 3. Real rents vs real pay across the pay distribution ----------
base = lon[lon.year == y0].iloc[0]
fig, ax = plt.subplots(figsize=(7.5, 3.8))
ax.plot(lon.year, 100 * (lon.rent_mean / lon.cpih) / (base.rent_mean / base.cpih), lw=2.5, color="black",
        marker="o", ms=3, label="Average private rent")
for p, lab in PAY.items():
    ax.plot(lon.year, 100 * (lon[p] / lon.cpih) / (base[p] / base.cpih), lw=1.8, marker="o", ms=3,
            label=f"Full-time pay, {lab}")
ax.axhline(100, color="grey", lw=0.8)
ax.set_ylabel(f"Index, {y0} = 100")
ax.legend(frameon=False, fontsize=8)
save(fig, ax, 3, "3_real_rents_vs_pay.png",
     f"Real private rents and real full-time pay in London, {y0} to {y1} (index, {y0} = 100).",
     "Rent is the mean monthly private rent across all property sizes in London from the ONS Price Index of Private "
     "Rents, taken in April of each year to match ASHE's April reference date. Pay is gross annual pay of full-time "
     "employees living in London at the 25th percentile, median and 75th percentile of the London pay distribution. "
     "All series are deflated by CPIH for April and indexed to their own 2015 value, so the chart compares growth "
     "since 2015, not levels (see Figure 4 for levels). PIPR covers rents on all existing private tenancies, not "
     "only new lets, so it adjusts gradually and rises more slowly than advertised rents when the market is rising. "
     "Pay in 2020 and 2021 is affected by the pandemic: furlough and job losses concentrated among lower-paid "
     "workers changed the mix of people in work, which can raise measured pay, and ONS advises caution when "
     "comparing these years. The 2020 peak should be read with this in mind.",
     SRC_RENT_PAY)

# ---------- Figure 4. Rent as a share of pay, by pay level ----------
fig, ax = plt.subplots(figsize=(7.5, 3.8))
for p, lab in PAY.items():
    ax.plot(lon.year, 100 * lon[f"rent_share_{p}"], lw=2, marker="o", ms=3, label=f"Full-time pay, {lab}")
ax.axhline(30, color="grey", lw=0.8, ls=":")
ax.text(y0, 31, "30% affordability threshold", fontsize=7, color="grey")
ax.yaxis.set_major_formatter(mt.PercentFormatter())
ax.set_ylim(0, None)
ax.set_ylabel("Annual rent as % of gross pay")
ax.legend(frameon=False, fontsize=8, loc="lower left")
save(fig, ax, 4, "4_rent_share_of_pay.png",
     f"Average London private rent as a percentage of one full-time salary, by pay level, {y0} to {y1}.",
     "Annual rent (12 times the mean monthly PIPR rent for London in April) divided by the gross annual pay of a "
     "single full-time employee at the 25th percentile, median or 75th percentile of the London resident pay "
     "distribution (ASHE, April). Both are in cash terms, so inflation cancels out of the ratio. This compares the "
     "average rent for all property sizes with one gross salary, so it is not a household affordability ratio: "
     "households may have more than one earner or receive benefits, may rent smaller or cheaper homes than the "
     "average, and pay is shown before tax. Levels are therefore higher than in ONS's private rental affordability "
     "statistics, which use modelled household income; the chart is intended to show the trend and the gap between "
     "pay levels. The dotted line marks the 30% threshold commonly used to define affordable rent.",
     SRC_RENT_PAY)

# ---------- Figure 5. Why households become homeless ----------
q = reasons.groupby("date")[["end_ast", "asylum_support", "family_friends", "end_ast_landlord_sell_relet",
                             "end_ast_arrears_rent_increase", "total"]].sum()
fig, ax = plt.subplots(figsize=(7.5, 3.8))
ax.plot(q.index, q.end_ast, lw=2, label="End of private (assured shorthold) tenancy")
ax.plot(q.index, q.asylum_support, lw=2, label="Required to leave Home Office asylum accommodation")
ax.plot(q.index, q.family_friends, lw=1.5, ls="--", color="grey", label="Family or friends no longer able to accommodate")
ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
ax.set_ylabel("Households per quarter")
ax.set_ylim(0, None)
ax.legend(frameon=False, fontsize=8, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=1)
save(fig, ax, 5, "5_reasons_for_homelessness.png",
     f"Households in London owed a homelessness duty, by selected reason for loss of last settled home, "
     f"quarterly, {q.index.min():%B %Y} to {q.index.max():%B %Y} (quarter ending).",
     "Households assessed by London boroughs as owed a prevention duty (threatened with homelessness within 56 days) "
     "or a relief duty (already homeless), added together, by the main reason for losing or being at risk of losing "
     "their last settled home. Each household is counted in the quarter of its assessment, so these are flows of new "
     "cases, not the number of households in TA. Three reasons are shown: the end of a private assured shorthold "
     "tenancy, the most common type of private letting; having to leave accommodation provided by the Home Office "
     "to people seeking asylum, which happens once a claim has been decided (for example, after a person is granted "
     "refugee status); and family or friends no longer being "
     "able to provide accommodation, shown for comparison as a long-standing leading reason. Other reasons (such as "
     "domestic abuse or the end of a social tenancy) are not shown. Low private-tenancy figures in 2020 and early "
     "2021 reflect Covid-19 restrictions on evictions in England, which were fully lifted at the end of May 2021. "
     "MHCLG rounds these regional figures to the nearest 10.",
     SRC_REASONS)

# ---------- Figure 6. Why private tenancies ended ----------
split = pd.DataFrame({
    "Landlord wishing to sell or re-let": q.end_ast_landlord_sell_relet,
    "Rent arrears caused by a rent increase": q.end_ast_arrears_rent_increase,
    "All other reasons": (q.end_ast - q.end_ast_landlord_sell_relet - q.end_ast_arrears_rent_increase).clip(lower=0),
})
fig, ax = plt.subplots(figsize=(7.5, 3.8))
ax.stackplot(split.index, split.T.values, labels=split.columns, alpha=0.85)
ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
ax.set_ylabel("Households per quarter")
ax.legend(frameon=False, fontsize=8, loc="upper left")
save(fig, ax, 6, "6_why_private_tenancies_ended.png",
     "Households in London owed a homelessness duty after the end of a private assured shorthold tenancy, "
     "by reason the tenancy ended, quarterly.",
     "Breakdown of the 'end of private tenancy' series in Figure 5 (prevention and relief duties combined) by the "
     "recorded reason the tenancy ended. 'Landlord wishing to sell or re-let' covers landlords ending the tenancy in "
     "order to sell the property or let it again; the data do not record whether a re-let was at a higher rent. "
     "'Rent arrears caused by "
     "a rent increase' is the specific case where the tenant fell into arrears after the rent went up. 'All other "
     "reasons' includes other rent arrears (difficulty budgeting, falls in income, benefit changes, changes in "
     "circumstances), breach of tenancy, tenants who complained about disrepair, illegal eviction, abandonment and "
     "reasons not known. Arrears following a rent increase are a small share of cases throughout; the largest single "
     "recorded reason is the landlord wishing to sell or re-let. Rounded to the nearest 10 by MHCLG.",
     SRC_REASONS)

# ---------- borough table: where did rents outpace low pay? ----------
b = panel[panel.code.str.startswith("E09")].pivot_table(index="code", columns="year", values="rent_share_pay_p25")
bt = pd.DataFrame({"borough": names.reindex(b.index), "share_p25_2020": 100 * b[2020], "share_p25_2025": 100 * b[2025]})
bt["change_pp"] = bt.share_p25_2025 - bt.share_p25_2020
bt = bt.join(latest.set_index("code").ta_rate.rename("ta_per_1000_mar2026")).sort_values("change_pp", ascending=False)
bt.round(1).to_csv("data/clean/borough_rent_burden.csv")

# ---------- captions file for the README ----------
with open(FIG + "captions.md", "w") as f:
    for n, name, title, notes, source in CAPTIONS:
        f.write(f"![Figure {n}](figures/{name})\n\n**Figure {n}. {title}**\n\n"
                f"*Notes:* {notes}\n\n*Source:* {source}\n\n")

print(split.round(0).tail(8).to_string())
