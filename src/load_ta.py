"""Households in temporary accommodation (TA) at quarter end, London boroughs.

Source: MHCLG statutory homelessness, detailed local authority tables, sheet TA1
(H-CLIC, quarterly). Layouts change between releases, so columns are found
by header text. Missing or suppressed cells ('..', '[x]', '[c]') become NaN.
"""
import re, glob, warnings
import pandas as pd
warnings.filterwarnings("ignore")

COLS = {  # output name -> function(header) -> bool
    "ta_households": lambda h: ("total number of households in ta" in h or "households in ta total" in h)
                               and "per" not in h and "chil" not in h,
    "households_k": lambda h: "households in area" in h,
    "ta_with_children": lambda h: "households in ta with chil" in h,
    "ta_nightly_paid": lambda h: "nightly paid" in h and "chil" not in h,
    "ta_other_district": lambda h: "another local authority district" in h or "in another la" in h,
}

def num(v):
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return float("nan")

def read_ta1(path):
    xl = pd.ExcelFile(path, engine="odf" if path.endswith(".ods") else None)
    sheet = next(s for s in xl.sheet_names if re.sub(r"[\W_]", "", s.upper()) == "TA1")
    df = xl.parse(sheet, header=None)
    first = df.index[df.iloc[:, 0].astype(str).str.startswith("E92")][0]
    head = (df.iloc[:first].astype(str)
              .apply(lambda c: " ".join(v for v in c if v != "nan")).str.lower()
              .str.replace(r"\s+", " ", regex=True))
    idx = {k: next(i for i, h in enumerate(head) if f(h)) for k, f in COLS.items()}
    lon = df[df.iloc[:, 0].astype(str).str.strip().str.match(r"E09|E12000007")]
    out = pd.DataFrame({"code": lon.iloc[:, 0].str.strip(), "borough": lon.iloc[:, 1].astype(str).str.strip()})
    for k, i in idx.items():
        out[k] = lon.iloc[:, i].map(num).values
    return out

if __name__ == "__main__":
    QEND = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}  # calendar quarter of the snapshot
    frames = []
    for f in sorted(glob.glob("data/raw/hl_20??Q?.*")):
        y, q = map(int, re.search(r"(20\d\d)Q(\d)", f).groups())
        d = read_ta1(f)
        d["date"] = pd.Timestamp(f"{y}-{QEND[q]}")
        frames.append(d)
        print(f, len(d), "boroughs,", int(d.ta_households.isna().sum()), "missing")
    ta = pd.concat(frames, ignore_index=True).sort_values(["code", "date"])
    ta.to_csv("data/clean/ta_london_quarterly.csv", index=False)
