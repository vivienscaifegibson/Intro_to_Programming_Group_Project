# 1_Location Search.py

import os
from typing import Optional
import folium
import requests
import streamlit as st
import time
from streamlit_folium import st_folium
from api.thinkhazard import find_division

st.set_page_config(page_title="Climate Hazard Explorer", layout="wide")
st.title("Climate Hazard Explorer")
st.write("Enter a country, region, or district name (e.g. *Lisboa*, *Wien*, or *Portugal*):")
query = st.text_input("Search location", key="search_input_main")
HAZARDS_PAGE = os.path.join("pages", "2_Hazard Levels.py")

def geocode_place(name: str) -> Optional[tuple[float, float]]:
    try:
        url = "https://nominatim.openstreetmap.org/search"
        r = requests.get(
            url,
            params={"q": name, "format": "json", "limit": 5},
            headers={"User-Agent": "CIE-Explorer/1.0"},
            timeout=15
        )
        r.raise_for_status()
        js = r.json()
        if js:
            return float(js[0]["lat"]), float(js[0]["lon"])
    except Exception as e:
        st.warning(f"⚠️ Geocoding failed: {e}")
    return None


def pick_display_name(row):
    for k in ["ADM2_NAME", "ADM1_NAME", "ADM0_NAME"]:
        if k in row.index and isinstance(row[k], str) and row[k].strip():
            return row[k].strip()
    return str(row.iloc[1])

def render_map(center, zoom):
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="CartoDB positron",
        control_scale=True,
        dragging=False,
        scrollWheelZoom=False,
        doubleClickZoom=False,
        boxZoom=False,
        zoomControl=False,
    )
    st_folium(m, width="100%", height=520, key="main_map_canvas")

center = st.session_state.get("map_center", (20.0, 0))
zoom = st.session_state.get("map_zoom", 2)
render_map(center, zoom)

matches = None
if query:
    matches = find_division(query)
    if matches is None or matches.empty:
        st.warning("⚠️ No city or region found. Trying national level…")

        from api.thinkhazard import load_admin_data, _norm

        adm0, _, _ = load_admin_data()
        q_norm = _norm(query)
        nat_hit = adm0[adm0["ADM0_NAME"].apply(_norm) == q_norm]
        if nat_hit.empty:
            nat_hit = adm0[adm0["ADM0_NAME"].apply(_norm).str.contains(q_norm, na=False)]

        if not nat_hit.empty:
            nat_hit = nat_hit.copy()
            nat_hit["level"] = "ADM0"
            matches = nat_hit.reset_index(drop=True)
            st.success(f"Defaulted to national level: {matches.iloc[0]['ADM0_NAME']}")
        else:
            st.error("No matching location found at any level. Try another name (e.g. Lisboa → Lisbon).")
            st.stop()

    level_order = {"ADM2": 0, "ADM1": 1, "ADM0": 2}
    if "level" in matches.columns:
        matches = matches.sort_values(
            by="level",
            key=lambda s: s.map(level_order).fillna(99)
        )

    matches.columns = matches.columns.map(str)
    matches = matches.loc[:, ~matches.columns.duplicated()]


    def safe_get(row, key):
        try:
            if key in row.index:
                val = row[key]
                if isinstance(val, (list, tuple)) and len(val) > 0:
                    return val[0]
                if hasattr(val, "iloc"):
                    if len(val) == 1:
                        return val.iloc[0]
                return val
            return ""
        except Exception:
            return ""


    def lbl(r):
        adm2 = str(safe_get(r, "ADM2_NAME") or "").strip()
        adm1 = str(safe_get(r, "ADM1_NAME") or "").strip()
        adm0 = str(safe_get(r, "ADM0_NAME") or "").strip()
        level = str(safe_get(r, "level") or "").strip()
        parts = [p for p in [adm2, adm1, adm0] if p]
        name = " • ".join(parts) if parts else "(Unnamed)"
        return f"{name} ({level}) • ID={r.iloc[0]}"

    options = matches.apply(lbl, axis=1).tolist()
    sel = st.selectbox("Select exact location:", options, key="loc_pick_main")
    proceed = st.button("Continue", type="primary", key="go_next")

    if proceed:
        st.session_state["clicked_continue"] = True
        sid = int(sel.split("ID=")[-1])
        row = matches[matches.iloc[:, 0] == sid].iloc[0]

        name = pick_display_name(row)
        coords = geocode_place(name)
        if not coords:
            st.error("❌ Could not geolocate this place.")
            st.stop()

        st.session_state["map_center"] = coords
        st.session_state["map_zoom"] = 5 if str(row.get("level", "")).upper() == "ADM0" else 8
        st.session_state["selected_row"] = row.to_dict()

        st.rerun()

if st.session_state.get("clicked_continue"):
    time.sleep(1)
    st.session_state.pop("clicked_continue", None)
    st.switch_page(HAZARDS_PAGE)
