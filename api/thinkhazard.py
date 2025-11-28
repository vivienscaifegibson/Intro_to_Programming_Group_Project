# api/thinkhazard.py

import io
import requests
import pandas as pd
import streamlit as st
from typing import Optional
import unicodedata

ADM0_URL = "https://raw.githubusercontent.com/GFDRR/thinkhazardmethods/master/source/download/ADM0_TH.csv"
ADM1_URL = "https://raw.githubusercontent.com/GFDRR/thinkhazardmethods/master/source/download/ADM1_TH.csv"
ADM2_URL = "https://raw.githubusercontent.com/GFDRR/thinkhazardmethods/master/source/download/ADM2_TH.csv"

def _norm(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.strip().lower()


@st.cache_data(show_spinner=False)
def load_admin_data():
    def fetch_csv(url: str) -> pd.DataFrame:
        r = requests.get(url)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text), sep=";")

    adm0 = fetch_csv(ADM0_URL)
    adm1 = fetch_csv(ADM1_URL)
    adm2 = fetch_csv(ADM2_URL)
    return adm0, adm1, adm2


def _search_level(df, level, code_col, name_col, query_norm, exact: bool):
    if name_col not in df.columns:
        return pd.DataFrame()

    df2 = df.copy()
    df2["_norm"] = df2[name_col].apply(_norm)

    if exact:
        hit = df2[df2["_norm"] == query_norm]
    else:
        hit = df2[df2["_norm"].str.contains(query_norm, na=False)]

    if hit.empty:
        return pd.DataFrame()

    hit = hit.copy()
    hit["level"] = level
    keep = [code_col, name_col, "level"]
    for extra in ["ISO3166_a3", "ISO3166_a2", "ADM0_NAME", "ADM1_NAME", "ADM2_NAME", "ADM0_CODE"]:
        if extra in hit.columns:
            keep.append(extra)
    return hit[keep]


def find_division(name: str) -> pd.DataFrame:

    adm0, adm1, adm2 = load_admin_data()
    q = _norm(name)

    for df, lvl, code_col, name_col in [
        (adm2, "ADM2", "ADM2_CODE", "ADM2_NAME"),
        (adm1, "ADM1", "ADM1_CODE", "ADM1_NAME"),
        (adm0, "ADM0", "ADM0_CODE", "ADM0_NAME"),
    ]:
        hit = _search_level(df, lvl, code_col, name_col, q, exact=True)
        if not hit.empty:
            return hit.reset_index(drop=True)

    for df, lvl, code_col, name_col in [
        (adm2, "ADM2", "ADM2_CODE", "ADM2_NAME"),
        (adm1, "ADM1", "ADM1_CODE", "ADM1_NAME"),
        (adm0, "ADM0", "ADM0_CODE", "ADM0_NAME"),
    ]:
        hit = _search_level(df, lvl, code_col, name_col, q, exact=False)
        if not hit.empty:
            return hit.reset_index(drop=True)

    return pd.DataFrame()


def get_hazards(report_id: int):
    url = f"http://thinkhazard.org/en/report/{report_id}.json"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()

@st.cache_data(show_spinner=False)
def adm0_iso3_by_name(adm0_name: str) -> Optional[str]:
    adm0, _, _ = load_admin_data()
    hit = adm0[adm0["ADM0_NAME"].str.lower() == str(adm0_name).lower()]
    if hit.empty:
        return None
    return hit.iloc[0]["ISO3166_a3"]

@st.cache_data(show_spinner=False)
def adm0_iso2_by_iso3(iso3: str) -> Optional[str]:
    adm0, _, _ = load_admin_data()
    hit = adm0[adm0["ISO3166_a3"].str.upper() == str(iso3).upper()]
    if hit.empty:
        return None
    return hit.iloc[0]["ISO3166_a2"]
