# pages/3_Comparison_Tool.py

import io
import re
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import requests
from api.thinkhazard import find_division, adm0_iso3_by_name, adm0_iso2_by_iso3
from api.cie import get_cie_band
from api.iso_map import fuzzy_match_region

st.set_page_config(
    page_title="Compare Climate Projections — Climate Hazard Explorer",
    layout="wide",
)

st.title("Compare climate projections between two locations")
st.caption("Type two locations (country, city, or administrative region).")
st.markdown("---")

VAR_LABELS = {
    "leh": "Heatwaves (land fraction exposed)",
    "peh": "Heatwaves (population exposed)",
    "fldfrc": "River floods (land fraction exposed)",
    "flddph": "River floods (max depth)",
    "lec": "Crop failure (land fraction exposed)",
    "pec": "Crop failure (population exposed)",
    "lew": "Wildfires (land fraction exposed)",
    "pew": "Wildfires (population exposed)",
    "ec1": "Labour productivity loss (heat stress)",
    "ec2": "Annual flood damage",
    "ec3": "Cyclone damage (annual expected)",
    "ec4": "Cyclone damage (1-in-100 year)",
    "prAdjust": "Precipitation (expressed in millimeter per day)",
    "tasAdjust": "Air temperature (mean)",
    "tasmaxAdjust": "Air temperature (daily max)",
    "tasminAdjust": "Air temperature (daily min)",
}

SCEN_LABELS = {
    "h_cpol": "NGFS current policies",
    "o_1p5c": "NGFS net-zero",
    "d_delfrag": "NGFS delayed 2°C",
    "cat_current": "CAT current policies",
    "rcp26": "RCP2.6",
    "rcp45": "RCP4.5",
    "rcp60": "RCP6.0",
    "rcp85": "RCP8.5",
}

def cleaned_var(v): return VAR_LABELS.get(v, v)
def cleaned_scen(s): return SCEN_LABELS.get(s, s)


def _normalize_region_code(iso2, candidate, fallback_name=None):
    iso2 = str(iso2 or "").strip().upper()
    fallback_name = str(fallback_name or "").strip()
    cand = str(candidate or "").strip().upper().replace("-", ".")
    abbr = "".join(ch for ch in fallback_name if ch.isalpha())[:2].upper()
    if abbr:
        return f"{iso2}.{abbr}"
    if re.fullmatch(r"[A-Z]{2}\.[A-Z0-9]{1,3}", cand):
        return cand
    if re.fullmatch(r"[A-Z]{2}", cand):
        return f"{iso2}.{cand}"
    return iso2

def resolve_cie_region_code(row_dict):
    iso3 = row_dict.get("ISO3166_a3")
    if not iso3:
        iso3 = adm0_iso3_by_name(row_dict.get("ADM0_NAME", ""))
    if not iso3:
        return None, None, None

    iso2 = adm0_iso2_by_iso3(iso3)
    best = row_dict.get("ADM2_NAME") or row_dict.get("ADM1_NAME") or row_dict.get("ADM0_NAME") or ""

    region_code = None
    if best:
        matches = fuzzy_match_region(best, iso2, threshold=80)
        if matches:
            region_code = matches[0][0].upper()

    if region_code:
        region_code = region_code.replace("-", ".")
        suffix = region_code.replace(f"{iso2}.", "")
        if suffix.isdigit():
            abbr = "".join(c for c in best if c.isalpha())[:2].upper()
            if abbr:
                region_code = f"{iso2}.{abbr}"
    else:
        abbr = "".join(c for c in best if c.isalpha())[:2].upper()
        region_code = f"{iso2}.{abbr}" if abbr else iso3
    return iso3, region_code, None

def build_region_info(row_dict):
    iso3, region_code, _ = resolve_cie_region_code(row_dict)
    iso2 = adm0_iso2_by_iso3(iso3)

    if region_code and region_code != iso3:
        region_code = _normalize_region_code(
            iso2,
            region_code,
            fallback_name=row_dict.get("ADM1_NAME") or row_dict.get("ADM2_NAME")
        )

    name = (
        row_dict.get("ADM2_NAME") or
        row_dict.get("ADM1_NAME") or
        row_dict.get("ADM0_NAME") or ""
    )

    return {
        "code": region_code,
        "country": iso2,
        "country_iso3": iso3,
        "name": name,
        "display": name,
    }

def resolve_location(name: str):
    try:
        matches = find_division(name)
    except Exception:
        return None
    if matches is None or matches.empty:
        return None
    row = matches.iloc[0]
    return build_region_info(row.to_dict())

def fetch_cie_shape_codes(iso3: str):
    try:
        r = requests.get(
            "https://cie-api.climateanalytics.org/api/shapes/",
            params={"iso": iso3},
            timeout=20,
        )
        js = r.json()
    except:
        return []
    codes = []
    if isinstance(js, list):
        for item in js:
            if isinstance(item, dict):
                for k in ["code", "id", "region", "ISO3166-2"]:
                    v = item.get(k)
                    if isinstance(v, str):
                        codes.append(v.upper())
    return list(dict.fromkeys(codes))

def load_cie(region_info, variable, scenario):
    region_code = region_info["code"]
    iso2 = region_info["country"]
    iso3 = region_info["country_iso3"]
    country = iso3 or iso2
    name = region_info["name"]
    abbrev = "".join(c for c in name if c.isalpha()).upper()[:2]
    shapes = fetch_cie_shape_codes(iso3)

    candidates = []
    if region_code:
        region_code_s = str(region_code)
        candidates.append(region_code_s)
        if "-" in region_code_s:
            candidates.append(region_code_s.split("-")[1])
            candidates.append(region_code_s.replace("-", "."))

    if iso2 and abbrev:
        candidates.append(f"{iso2}-{abbrev}")
        candidates.append(f"{iso2}.{abbrev}")

    candidates.extend(shapes)
    candidates.append(country)
    candidates.append(iso2)
    candidates.append("")

    tried = []
    for cand in candidates:
        tried.append(str(cand))
        try:
            df = get_cie_band(
                iso=country,
                region=str(cand),
                var=variable,
                scenario=scenario,
            )
        except:
            df = pd.DataFrame()
        if df is not None and not df.empty:
            return df, cand, tried

    return pd.DataFrame(), "", tried


def standardize(df: pd.DataFrame, label: str):
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if "year" in df:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
    elif "time" in df:
        df.rename(columns={"time": "year"}, inplace=True)
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
    else:
        return pd.DataFrame()

    if "median" not in df:
        return pd.DataFrame()

    df = df.dropna(subset=["year", "median"])
    df["year"] = df["year"].astype(int)
    return df[["year", "median"]].rename(columns={"median": label})

colA, colB = st.columns(2)
with colA:
    locA = st.text_input("Location A", placeholder="e.g. Wien")
with colB:
    locB = st.text_input("Location B", placeholder="e.g. Lisboa")

if not locA or not locB:
    st.stop()

infoA = resolve_location(locA)
infoB = resolve_location(locB)

if not infoA:
    st.error(f"Could not resolve: {locA}")
    st.stop()
if not infoB:
    st.error(f"Could not resolve: {locB}")
    st.stop()

st.success(f"Comparing **{infoA['display']}** and **{infoB['display']}**")
st.markdown("---")

c1, c2 = st.columns(2)
with c1:
    variable = st.selectbox("Variable", list(VAR_LABELS.keys()), format_func=cleaned_var)
with c2:
    scenario = st.selectbox("Scenario", list(SCEN_LABELS.keys()), format_func=cleaned_scen)

dfA_raw, usedA, triedA = load_cie(infoA, variable, scenario)
dfB_raw, usedB, triedB = load_cie(infoB, variable, scenario)

if dfA_raw.empty:
    st.error(f"No data found for {infoA['display']}.")
    st.stop()
if dfB_raw.empty:
    st.error(f"No data found for {infoB['display']}.")
    st.stop()

dfA = standardize(dfA_raw, infoA["display"])
dfB = standardize(dfB_raw, infoB["display"])

combined = dfA.merge(dfB, on="year", how="outer").sort_values("year")

ymin = int(combined["year"].min())
ymax = int(combined["year"].max())

yr_range = st.slider(
    "Year range",
    min_value=ymin,
    max_value=ymax,
    value=(ymin, ymax),
)

df_plot = combined[(combined["year"] >= yr_range[0]) & (combined["year"] <= yr_range[1])]

chart_type = st.radio("Chart type", ["Line", "Scatter"], horizontal=True)

fig = go.Figure()

mode = "lines" if chart_type == "Line" else "markers"

for col in df_plot.columns:
    if col != "year":
        fig.add_trace(
            go.Scatter(
                x=df_plot["year"],
                y=df_plot[col],
                mode=mode,
                name=col,
                line=dict(width=3),
            )
        )

fig.update_layout(
    title=f"{cleaned_var(variable)} — {cleaned_scen(scenario)}",
    xaxis_title="Year",
    yaxis_title=cleaned_var(variable),
    height=540,
)

st.plotly_chart(fig, use_container_width=True)

def metric_val(df, y):
    row = df[df["year"] == y]
    return float(row.iloc[0, 1]) if not row.empty else None

st.subheader("Snapshot values")

summary = pd.DataFrame({
    "Region": [infoA["display"], infoB["display"]],
    "2025": [metric_val(dfA, 2025), metric_val(dfB, 2025)],
    "2050": [metric_val(dfA, 2050), metric_val(dfB, 2050)],
    "2100": [metric_val(dfA, 2100), metric_val(dfB, 2100)],
})

st.dataframe(summary, use_container_width=True)

st.markdown("---")
st.subheader("Raw comparison data")

st.dataframe(combined, use_container_width=True)

st.download_button(
    label="Download CSV",
    data=combined.to_csv(index=False),
    file_name=f"comparison_{variable}_{scenario}.csv",
    mime="text/csv",
)

st.page_link("1_Location Search.py", label="← Back to Search")
st.page_link("pages/2_Hazard Levels.py", label="← Hazard Dashboard")
