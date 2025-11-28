# api/cie.py

import pandas as pd
import numpy as np
import requests

CIE_BASE = "https://cie-api.climateanalytics.org/api/timeseries/"

def get_cie_band(
    iso: str,
    region: str,
    var: str = "leh",
    scenario: str = "h_cpol",
    season: str = "annual",
    aggregation_spatial: str = "area",
) -> pd.DataFrame:

    region_norm = str(region).replace("-", ".").upper().strip()
    params = {
        "iso": iso,
        "region": region_norm,
        "scenario": scenario,
        "var": var,
        "season": season,
        "aggregation_spatial": aggregation_spatial,
        "format": "json",
    }

    headers = {"User-Agent": "CIE-client/3.1"}

    try:
        r = requests.get(CIE_BASE, params=params, headers=headers, timeout=20)
        r.raise_for_status()
        js = r.json()
    except Exception as e:
        return pd.DataFrame(columns=["year", "lower", "median", "upper"])

    def to_float_list(x):
        if not isinstance(x, (list, tuple)):
            return []
        vals = []
        for v in x:
            try:
                vals.append(float(v))
            except Exception:
                vals.append(np.nan)
        return vals

    if isinstance(js, dict):
        years  = to_float_list(js.get("year", []))
        lower  = to_float_list(js.get("lower", []))
        median = to_float_list(js.get("median", []))
        upper  = to_float_list(js.get("upper", []))

        if any(len(lst) > 0 for lst in [years, lower, median, upper]):
            maxlen = max(len(years), len(lower), len(median), len(upper))
            def pad(lst): return lst + [np.nan] * (maxlen - len(lst))
            years, lower, median, upper = map(pad, [years, lower, median, upper])

            df = pd.DataFrame({
                "year": years,
                "lower": lower,
                "median": median,
                "upper": upper,
            })
            df = df.dropna(how="all", subset=["median", "lower", "upper"])
            df = df.sort_values("year").reset_index(drop=True)
            print(f"CIE: Parsed {len(df)} rows for {region_norm}")
            if len(df) > 0:
                print(df.head(3))
            return df

    if isinstance(js, dict) and isinstance(js.get("data"), list):
        df = pd.DataFrame(js["data"])
        if "time" in df.columns:
            df = df.rename(columns={"time": "year"})
        for c in ["year", "lower", "median", "upper"]:
            df[c] = pd.to_numeric(df.get(c, np.nan), errors="coerce")
        df = df.dropna(how="all", subset=["median", "lower", "upper"])
        df = df.sort_values("year").reset_index(drop=True)
        print(f"CIE: Parsed {len(df)} rows for {region_norm}")
        return df

    print(f"CIE WARNING: Unexpected JSON shape for {region_norm}")
    print("RAW JSON snippet:", str(js)[:400])
    return pd.DataFrame(columns=["year", "lower", "median", "upper"])
