# pages/2_Hazard Levels.py

import io
import re
from typing import Optional, Tuple
import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from api.thinkhazard import get_hazards, adm0_iso3_by_name, adm0_iso2_by_iso3
from api.cie import get_cie_band
from api.iso_map import fuzzy_match_region

st.set_page_config(
    page_title="Hazards & Climate Projections — Climate Hazard Explorer",
    layout="wide",
)

if "selected_row" not in st.session_state:
    st.warning("Please choose a location on the search page first.")
    st.page_link("1_Location Search.py", label="← Go to Search")
    st.stop()

row = st.session_state["selected_row"]

def pick_display_name(r: dict) -> str:
    for k in ["ADM2_NAME", "ADM1_NAME", "ADM0_NAME"]:
        v = r.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return str(next(iter(r.values())))

def report_id_from_row(r: dict) -> Optional[int]:
    lvl = str(r.get("level", "")).upper()
    if lvl == "ADM2" and "ADM2_CODE" in r:
        return int(r["ADM2_CODE"])
    if lvl == "ADM1" and "ADM1_CODE" in r:
        return int(r["ADM1_CODE"])
    if "ADM0_CODE" in r:
        return int(r["ADM0_CODE"])
    if "id" in r:
        try:
            return int(r["id"])
        except Exception:
            return None
    return None

def level_color(level: str) -> str:
    if not level or level == "No Data":
        return "#BBBBBB"
    m = level.lower()
    if "very high" in m:
        return "#8B0000"
    if "high" in m:
        return "#FF0000"
    if "medium" in m:
        return "#E6C200"
    if "low" in m and "very" not in m:
        return "#228B22"
    if "very low" in m:
        return "#66BB66"
    return "#555555"

def _normalize_region_code(
    iso2: Optional[str],
    candidate: Optional[str],
    fallback_name: Optional[str] = None,
) -> str:
    iso2 = str(iso2 or "").strip().upper()
    fallback_name = str(fallback_name or "").strip()
    cand = str(candidate or "").strip().upper().replace("-", ".")

    abbr = "".join(ch for ch in fallback_name if ch.isalpha())[:2].upper()

    if abbr:
        return f"{iso2}.{abbr}"

    import re as _re
    if _re.fullmatch(r"[A-Z]{2}\.[A-Z0-9]{1,3}", cand):
        return cand
    if _re.fullmatch(r"[A-Z]{2}", cand):
        return f"{iso2}.{cand}"
    return iso2


def resolve_cie_region_code(r: dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    iso3 = r.get("ISO3166_a3")
    if not isinstance(iso3, str) or not iso3.strip():
        base = r.get("ADM0_NAME", "")
        iso3 = adm0_iso3_by_name(str(base))
    if not iso3:
        return None, None, "❌ Could not determine ISO3 code."

    iso2 = adm0_iso2_by_iso3(iso3)
    adm2 = str(r.get("ADM2_NAME", "") or "")
    adm1 = str(r.get("ADM1_NAME", "") or "")
    adm0 = str(r.get("ADM0_NAME", "") or "")
    best_name = adm2 or adm1 or adm0

    region_code = None
    if best_name:
        cands = fuzzy_match_region(best_name, iso2, threshold=80)
        if cands:
            region_code = cands[0][0].upper()  # ISO-3166-2 code

    if region_code:
        region_code = region_code.replace("-", ".")
        suffix = region_code.replace(f"{iso2}.", "")
        if suffix.isdigit():
            abbr = "".join(ch for ch in best_name if ch.isalpha())[:2].upper()
            if abbr:
                region_code = f"{iso2}.{abbr}"
    else:
        abbr = "".join(ch for ch in best_name if ch.isalpha())[:2].upper()
        region_code = f"{iso2}.{abbr}" if abbr else iso3

    return iso3, region_code, None

def build_region_info(r: dict) -> dict:
    iso3_val, region_code_val, _ = resolve_cie_region_code(r)
    iso2_val = adm0_iso2_by_iso3(iso3_val) if iso3_val else ""
    if region_code_val and region_code_val != iso3_val:
        region_code_val = _normalize_region_code(
            iso2_val,
            region_code_val,
            fallback_name=(r.get("ADM1_NAME") or r.get("ADM2_NAME") or ""),
        )

    adm2 = r.get("ADM2_NAME") or ""
    adm1 = r.get("ADM1_NAME") or ""
    adm0 = r.get("ADM0_NAME") or ""
    name = adm2 or adm1 or adm0 or ""

    return {
        "code": region_code_val or "",
        "country": iso2_val,
        "country_iso3": iso3_val or iso2_val,
        "name": name,
    }

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

HAZARD_VAR_MAP = {
    "River flood": ["fldfrc", "flddph", "ec2"],
    "Urban flood": ["fldfrc", "flddph", "ec2"],
    "Coastal flood": ["fldfrc", "flddph", "ec2"],
    "Extreme heat": ["leh", "peh", "tasmaxAdjust"],
    "Wildfire": ["lew", "pew"],
    "Cyclone": ["ec3", "ec4"],
    "Water scarcity": ["prAdjust"],
}

def cleaned_var(var_id: str) -> str:
    return VAR_LABELS.get(var_id, var_id.upper())

def cleaned_scen(scen_id: str) -> str:
    return SCEN_LABELS.get(scen_id, scen_id.upper())

def is_all_zero(df: pd.DataFrame) -> bool:
    if "median" not in df.columns:
        return False
    med = pd.to_numeric(df["median"], errors="coerce")
    return med.notna().any() and med.abs().sum() == 0

def median_for_year(df: pd.DataFrame, year: int) -> Optional[float]:
    s = df.loc[df["year"].astype(int) == int(year), "median"]
    return float(s.iloc[0]) if not s.empty else None

def render_map(center, zoom: int = 8, label: str = ""):
    if not center:
        return
    m = folium.Map(location=center, zoom_start=zoom, tiles="CartoDB positron", control_scale=True)
    if label:
        folium.Marker(center, popup=label, tooltip=label, icon=folium.Icon(color="red")).add_to(m)
    st_folium(m, width="100%", height=420, key="proj_map")

def fetch_cie_shape_codes(iso3: str) -> list:
    if not iso3:
        return []
    try:
        r = requests.get(
            "https://cie-api.climateanalytics.org/api/shapes/",
            params={"iso": iso3},
            headers={"User-Agent": "CIE-shapes/1.0"},
            timeout=20,
        )
        r.raise_for_status()
        js = r.json()
    except Exception:
        return []

    codes = []
    if isinstance(js, list):
        for item in js:
            if isinstance(item, dict):
                for key in ["code", "id", "ISO3166-2", "iso", "region", "region_code"]:
                    val = item.get(key)
                    if isinstance(val, str):
                        codes.append(val.upper())
    elif isinstance(js, dict):
        feats = js.get("features", [])
        for feat in feats:
            if not isinstance(feat, dict):
                continue
            props = feat.get("properties", {})
            if not isinstance(props, dict):
                continue
            val = (
                props.get("code")
                or props.get("id")
                or props.get("iso")
                or props.get("region")
                or props.get("ISO3166-2")
            )
            if isinstance(val, str):
                codes.append(val.upper())

    seen = set()
    uniq = []
    for c in codes:
        if c in seen:
            continue
        seen.add(c)
        uniq.append(c)
    return uniq

def load_cie(region_info, variable, scenario):
    region_code = region_info.get("code", "")
    country_iso2 = region_info.get("country", "")
    country_iso3 = region_info.get("country_iso3", country_iso2)
    country = country_iso3 or country_iso2
    region_label = region_info.get("name", "") or region_info.get("region_name", "")
    abbrev = "".join(ch for ch in region_label if ch.isalpha()).upper()[:2]
    shape_codes = fetch_cie_shape_codes(country_iso3)

    candidates = []
    if region_code:
        candidates.append(region_code)
        if "-" in region_code:
            candidates.append(region_code.split("-", 1)[1])
            candidates.append(region_code.replace("-", "."))
    if country_iso2 and abbrev:
        candidates.append(f"{country_iso2}-{abbrev}")
        candidates.append(f"{country_iso2}.{abbrev}")
    candidates.extend(shape_codes)
    if country:
        candidates.append(country)
    if country_iso2 and country_iso2 != country_iso3:
        candidates.append(country_iso2)
    candidates.append("")

    seen = set()
    uniq = []
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        uniq.append(c)
    candidates = uniq

    tried = []
    for candidate in candidates:
        tried.append(candidate)
        try:
            df_try = get_cie_band(iso=country, region=candidate, var=variable, scenario=scenario)
        except Exception:
            df_try = pd.DataFrame()
        if df_try is not None and not df_try.empty:
            return df_try, candidate, tried
    return pd.DataFrame(), tried[0] if tried else "", tried

region_label = pick_display_name(row)
st.header(f"Hazard levels & climate projections for: {region_label}")
st.caption(
    f"ADM2={row.get('ADM2_NAME')} · ADM1={row.get('ADM1_NAME')} · ADM0={row.get('ADM0_NAME')}"
)

st.markdown(
    """
<style>
div.stButton > button {
    background-color:#f2f2f2 !important;
    color:#000 !important;
    border-radius:6px;
    border:1px solid #ddd;
}
div.stButton > button:hover {
    background-color:#e5e5e5 !important;
}
</style>
""",
    unsafe_allow_html=True,
)

report_id = report_id_from_row(row)
if report_id is None:
    st.error("Could not determine the ThinkHazard report id for this selection.")
    st.stop()

try:
    hazards_json = get_hazards(report_id)
except Exception as e:
    st.error(f"Failed to fetch ThinkHazard report: {e}")
    st.stop()

hazard_list = []
levels_by_hazard = {}

if isinstance(hazards_json, dict) and "hazards" in hazards_json:
    for h in hazards_json["hazards"]:
        nm = h["hazard"]
        hazard_list.append(nm)
        levels_by_hazard[nm] = h.get("level")
elif isinstance(hazards_json, list):
    for h in hazards_json:
        nm = h["hazardtype"]["hazardtype"]
        hazard_list.append(nm)
        levels_by_hazard[nm] = h.get("hazardlevel", {}).get("title")
else:
    st.warning("No hazard data available for this location.")
    st.stop()

if not hazard_list:
    st.warning("No hazards returned from ThinkHazard for this location.")
    st.stop()

st.subheader("Hazard levels (ThinkHazard)")
st.write("Click a hazard to explore detailed climate projections from the Climate Impact Explorer.")

cols_h = st.columns(2)
for idx, hz in enumerate(hazard_list):
    level_label = levels_by_hazard.get(hz, "No Data")
    color = level_color(level_label)
    col_btn = cols_h[idx % 2]

    with col_btn:
        c1, c2 = st.columns([2, 3])
        with c1:
            if st.button(hz, key=f"btn_{hz}"):
                st.session_state["selected_hazard"] = hz
                for k in [
                    "climate_data",
                    "climate_variable",
                    "climate_scenario",
                    "last_region_used",
                    "region_candidates_tried",
                    "_prev_climate_scenario",
                ]:
                    st.session_state.pop(k, None)
        with c2:
            st.markdown(
                f"<p style='margin-top:0.45rem; color:{color}; font-weight:600'>{level_label}</p>",
                unsafe_allow_html=True,
            )

st.markdown("---")

sel_hazard = st.session_state.get("selected_hazard")
if not sel_hazard or sel_hazard not in hazard_list:
    sel_hazard = hazard_list[0]
    st.session_state["selected_hazard"] = sel_hazard

st.subheader(f"{sel_hazard} — Projections from the Climate Impact Explorer")

allowed_vars = HAZARD_VAR_MAP.get(sel_hazard)
if not allowed_vars:
    allowed_vars = ["leh", "prAdjust", "tasAdjust"]

variable = allowed_vars[0]
st.session_state["climate_variable"] = variable

scenario = st.session_state.get("climate_scenario", "h_cpol")
prev_scenario = st.session_state.get("_prev_climate_scenario", scenario)

scen_keys = list(SCEN_LABELS.keys())
scen_index = scen_keys.index(scenario) if scenario in scen_keys else 0
scenario = st.selectbox(
    "Scenario",
    scen_keys,
    index=scen_index,
    format_func=cleaned_scen,
)

st.session_state["climate_scenario"] = scenario

if scenario != prev_scenario:
    st.session_state.pop("climate_data", None)
    st.session_state.pop("last_region_used", None)
    st.session_state.pop("region_candidates_tried", None)

st.session_state["_prev_climate_scenario"] = scenario

coords = st.session_state.get("map_center")
zoom = st.session_state.get("map_zoom", 8)
render_map(coords, zoom, region_label)

region_info = build_region_info(row)

raw = st.session_state.get("climate_data")
df = pd.DataFrame()
error_msg = None

if raw is None:
    with st.spinner("Loading projections from CIE..."):
        df_tmp, used_region, tried = load_cie(region_info, variable, scenario)
        if hasattr(df_tmp, "attrs") and df_tmp.attrs.get("cie_error"):
            error_msg = df_tmp.attrs.get("cie_error")
        if df_tmp is not None and not df_tmp.empty:
            try:
                serial = df_tmp.to_dict(orient="list")
            except Exception:
                buf = io.StringIO()
                df_tmp.to_csv(buf, index=False)
                serial = buf.getvalue()
            st.session_state["climate_data"] = serial
            st.session_state["last_region_used"] = used_region
            st.session_state["region_candidates_tried"] = tried
            df = df_tmp
else:
    if isinstance(raw, dict):
        df = pd.DataFrame(raw)
    elif isinstance(raw, str):
        try:
            df = pd.read_csv(io.StringIO(raw))
        except Exception:
            df = pd.DataFrame()
    elif isinstance(raw, pd.DataFrame):
        df = raw
    else:
        try:
            df = pd.DataFrame(raw)
        except Exception:
            df = pd.DataFrame()

    if hasattr(df, "attrs") and df.attrs.get("cie_error"):
        error_msg = df.attrs.get("cie_error")

for c in ["year", "median", "lower", "upper"]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

if df is None or df.empty or is_all_zero(df):
    with st.spinner("Retrying CIE fetch..."):
        df_tmp, used_region, tried = load_cie(region_info, variable, scenario)
    if hasattr(df_tmp, "attrs") and df_tmp.attrs.get("cie_error"):
        error_msg = df_tmp.attrs.get("cie_error")
    if df_tmp is not None and not df_tmp.empty:
        try:
            serial = df_tmp.to_dict(orient="list")
        except Exception:
            buf = io.StringIO()
            df_tmp.to_csv(buf, index=False)
            serial = buf.getvalue()
        st.session_state["climate_data"] = serial
        st.session_state["last_region_used"] = used_region
        st.session_state["region_candidates_tried"] = tried
        df = df_tmp

if df is None or df.empty:
    if error_msg:
        st.error(f"CIE API message: {error_msg}")
    tried = st.session_state.get("region_candidates_tried", [])
    if tried:
        st.caption(f"Region codes tried: {', '.join([t for t in tried if t])}")
    st.warning("No projection data available for this hazard/variable/scenario.")
    st.stop()

st.caption(
    f"Data source attempt: country={region_info.get('country','')} region='{st.session_state.get('last_region_used','')}'"
)

year_min = int(df["year"].min()) if "year" in df.columns else 2020
year_max = int(df["year"].max()) if "year" in df.columns else 2100
yr_range = st.slider(
    "Year range",
    min_value=year_min,
    max_value=year_max,
    value=(year_min, year_max),
    key=f"year_range_{sel_hazard}_{scenario}",
)

chart_type = st.radio(
    "Chart type",
    ["Line", "Scatter"],
    horizontal=True,
)

df_plot = df.copy()
if "year" in df_plot.columns:
    df_plot = df_plot[df_plot["year"].astype(int).between(int(yr_range[0]), int(yr_range[1]))].reset_index(drop=True)

fig = None

if chart_type in ("Line", "Scatter"):
    mode = "lines" if chart_type == "Line" else "markers"
    fig = go.Figure()

    if "upper" in df_plot.columns and "lower" in df_plot.columns:
        fig.add_trace(
            go.Scatter(
                x=list(df_plot["year"]) + list(df_plot["year"])[::-1],
                y=list(df_plot["upper"]) + list(df_plot["lower"])[::-1],
                fill="toself",
                fillcolor="rgba(100,150,250,0.12)",
                line=dict(color="rgba(255,255,255,0)"),
                hoverinfo="skip",
                name="Confidence band - 5-95% confidence interval",
            )
        )

    if "median" in df_plot.columns:
        fig.add_trace(
            go.Scatter(
                x=df_plot["year"],
                y=df_plot["median"],
                mode=mode,
                name="Median - Indicative model results after 2060",
                line=dict(width=2),
            )
        )

    fig.update_layout(
        title=f"{cleaned_var(variable)} — {cleaned_scen(scenario)} — {region_label}",
        xaxis_title="Year",
        yaxis_title=cleaned_var(variable),
        hovermode="x unified",
        height=540,
    )


if fig is not None:
    st.plotly_chart(fig, use_container_width=True)

c1, c2, c3 = st.columns(3)
cur = median_for_year(df, 2025)
mid = median_for_year(df, 2050)
endc = median_for_year(df, 2100)
with c1:
    st.metric("Current (2025)", f"{cur:.2f}" if cur is not None else "N/A")
with c2:
    st.metric("Mid-century (2050)", f"{mid:.2f}" if mid is not None else "N/A")
with c3:
    st.metric("End-century (2100)", f"{endc:.2f}" if endc is not None else "N/A")


st.markdown("---")
st.subheader("Raw data")
st.dataframe(df, use_container_width=True)
st.download_button(
    "Download CSV",
    df.to_csv(index=False),
    file_name=f"climate_{region_info.get('code','')}_{variable}_{scenario}.csv",
    mime="text/csv",
)

st.markdown("---")
st.subheader("Statistical summary")
cols = [c for c in ["median", "lower", "upper"] if c in df.columns]
if cols:
    st.dataframe(df[cols].describe(), use_container_width=True)
else:
    st.info("No statistical columns available to summarise.")

if st.button("Clear hazard & projection selection"):
    for k in [
        "selected_hazard",
        "climate_data",
        "climate_variable",
        "climate_scenario",
        "last_region_used",
        "region_candidates_tried",
        "_prev_climate_scenario",
    ]:
        st.session_state.pop(k, None)
    st.rerun()

st.page_link("1_Location Search.py", label="← Back to Location Search")

st.page_link("pages/3_Comparison_Tool.py", label="→ Open Comparison Tool")
