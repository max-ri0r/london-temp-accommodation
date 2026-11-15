"""Reasons for homelessness, London: households owed a prevention duty (A2P)
or relief duty (A2R), by reason for loss of last settled home. Quarterly flows.

Source: MHCLG statutory homelessness detailed LA tables. Uses the London
regional row (E12000007); figures are rounded to the nearest 10 by MHCLG.
"""
import re, glob, warnings
import pandas as pd
warnings.filterwarnings("ignore")

COLS = {
    "total": lambda h: "owed a prevention duty" in h or "owed a relief duty" in h,
    "end_ast": lambda h: "total end of ast" in h or "end of asttotal" in h,
    "end_ast_landlord_sell_relet": lambda h: "landlord wishing to sell or re" in h,
    "end_ast_arrears_rent_increase": lambda h: "increase in rent" in h,
    "family_friends": lambda h: "family or friends" in h,
    "domestic_abuse": lambda h: "domestic abuse" in h,
    "asylum_support": lambda h: "home office as asylum" in h,
}

def num(v):
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return float("nan")

def read(path, table):
    xl = pd.ExcelFile(path, engine="odf" if path.endswith(".ods") else None)
    sheet = next((s for s in xl.sheet_names if re.sub(r"[\W_]", "", s.upper()) == table), None)
    if sheet is None:  # early files combine prevention and relief in one sheet; skip them
        return None
    df = xl.parse(sheet, header=None)
    first = df.index[df.iloc[:, 0].astype(str).str.startswith("E92")][0]
    head = (df.iloc[:first].astype(str).apply(lambda c: " ".join(v for v in c if v != "nan"))
              .str.lower().str.replace(r"\s+", " ", regex=True).str.replace("asttotal", "ast total ").str.replace("ast total", "asttotal"))
    row = df[df.iloc[:, 0].astype(str).str.strip() == "E12000007"].iloc[0]
    out = {}
    for k, f in COLS.items():
        i = next((i for i, h in enumerate(head) if i > 1 and f(h)), None)  # skip code/name cols (title text)
        out[k] = num(row.iloc[i]) if i is not None else float("nan")
    return out

if __name__ == "__main__":
    QEND = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
    rows = []
    for f in sorted(glob.glob("data/raw/hl_20??Q?.*")):
        y, q = map(int, re.search(r"(20\d\d)Q(\d)", f).groups())
        for t, duty in [("A2P", "prevention"), ("A2R", "relief")]:
            r = read(f, t)
            if r is not None:
                rows.append({"date": f"{y}-{QEND[q]}", "duty": duty, **r})
    d = pd.DataFrame(rows)
    d.to_csv("data/clean/reasons_london_quarterly.csv", index=False)
    print(d.to_string(index=False))
