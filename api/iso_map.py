# api/iso_map.py

import requests
import unicodedata
from typing import List, Dict, Tuple, Optional
import streamlit as st
from rapidfuzz import fuzz

ISO2_JSON_URL = ("https://raw.githubusercontent.com/biter777/countries/master/data/iso-codes/data_iso_3166-2.json")

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower().strip()

@st.cache_data(show_spinner=False)
def load_iso3166_2() -> List[Dict]:
    r = requests.get(ISO2_JSON_URL, timeout=20)
    r.raise_for_status()
    payload = r.json()
    return payload.get("3166-2", [])

def filter_country_entries(iso2: str, entries: List[Dict]) -> List[Dict]:
    prefix = f"{iso2}-"
    return [
        e for e in entries
        if isinstance(e.get("code"), str) and e["code"].startswith(prefix)
    ]

def fuzzy_match_region(name: str, country_iso2: str, threshold: int = 85) -> List[Tuple[str, str, int]]:
    entries = filter_country_entries(country_iso2, load_iso3166_2())
    q = _norm(name)
    if not q or not entries:
        return []

    aliases = {e["code"]: e.get("name", "") for e in entries}
    for e in entries:
        alt_names = e.get("translations", [])
        if isinstance(alt_names, dict):
            for val in alt_names.values():
                aliases[e["code"]] += " " + val

    scored = []
    for code, nm in aliases.items():
        score = fuzz.token_sort_ratio(q, _norm(nm))
        if score >= threshold:
            scored.append((code, nm.strip(), score))

    def _bias(entry: Tuple[str, str, int]) -> float:
        code, nm, score = entry
        nm_l = nm.lower()
        bonus = 0
        if any(k in nm_l for k in ["region", "province", "state", "governorate", "metropolitan"]):
            bonus += 5
        if any(k in nm_l for k in ["district", "county", "municipality"]):
            bonus -= 5
        return score + bonus

    scored = [(c, n, int(_bias((c, n, s)))) for c, n, s in scored]
    scored.sort(key=lambda x: x[2], reverse=True)

    if not scored:
        rough = []
        for e in entries:
            nm = e.get("name", "")
            score = fuzz.token_sort_ratio(q, _norm(nm))
            rough.append((e["code"], nm, score))
        rough.sort(key=lambda x: x[2], reverse=True)
        top = rough[:3]
        return top
    return scored
