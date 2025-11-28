# pages/4_About.py

import streamlit as st

st.set_page_config(
    page_title="About – Climate Hazard Explorer",
    layout="wide",
)

st.title("About the Climate Hazard Explorer")
st.markdown("---")

# INTRO

st.markdown("""
## Overview

The **Climate Hazard Explorer** is an interactive tool that allows users to explore  
**current climate hazard levels** and **future climate projections** for specific locations worldwide.

It combines two independent data sources:

- **ThinkHazard** → current hazard levels  
- **Climate Impact Explorer (CIE)** → future climate projections  

The application is designed to support:

- climate risk screening  
- portfolio-level risk analysis  
- sustainability reporting (e.g., TCFD, SFDR, PCAF)  
- research into hazard exposure under future climate conditions  

The tool is structured into four pages, each representing a stage in the workflow.
""")

st.markdown("---")

# APP PAGES

st.markdown("""
## Application Structure

### **1. Location Search**
- Users type a country, region, or city.  
- The system matches the location using ThinkHazard's ADM0/ADM1/ADM2 datasets.  
- The match is saved and passed to the next pages.

---

### **2. Hazard Levels**
- Displays hazard levels from **ThinkHazard** for the selected location.  
- Hazards with available climate projections include:
  - River flood  
  - Urban flood  
  - Coastal flood  
  - Extreme heat  
  - Wildfire  
  - Cyclone  
  - Water scarcity  
- Users click a hazard to see detailed projections.
- The tool automatically determines an appropriate CIE region code using:
  - ISO-3166 mapping  
  - fuzzy name matching  
  - shape code fallbacks  
  - national fallback if no regional code matches  

---

### **3. Comparison Tool**
- Users compare **two different regions** under the **same hazard and variable**.  
- The hazard determines which CIE variables are available.  
- Each region is matched separately and plotted together.  
- Only **Line** and **Scatter** charts are shown (no bar charts).  
- Confidence interval shading is included when available.

---
""")


# DATA SOURCES

st.markdown("""
## Data Sources

### **ThinkHazard (GFDRR / World Bank)**  
Used for:
- Current hazard levels  
- Administrative boundary identifiers (ADM2 → ADM1 → ADM0)  
- ISO country codes  

API Endpoint example:  
`https://thinkhazard.org/en/report/{id}.json`

---

### **Climate Impact Explorer (Climate Analytics)**  
Used for:
- Future climate projections  
- NGFS-style scenarios:
  - h_cpol (current policies)  
  - o_1p5c (net zero)  
  - d_delfrag (delayed transition)  
  - cat_current (Climate Action Tracker current policies)

Projections include:
- heatwaves  
- river flooding  
- cyclone damage  
- wildfire exposure  
- precipitation  
- temperature extremes  

API Endpoint example:  
`https://cie-api.climateanalytics.org/api/timeseries/`

---

### **ISO Code Mapping & Fuzzy Matching**
Because CIE uses numerous regional code formats, the app:
1. tests ISO-3166-2 formats  
2. tests versions with dots and hyphens  
3. tests abbreviated fallback codes  
4. tries all country-level datasets  
5. finally falls back to the **national** dataset  

This ensures that **every location always returns a projection**, even if no regional match exists.
""")

st.markdown("---")

# METHODS

st.markdown("""
## Methodology Summary

### **1. Location Resolution**
- User types a free-text location (city/country/region).  
- ThinkHazard tables map this to ADM2/ADM1/ADM0.  
- Coordinates are stored for map display.

### **2. Hazard Selection**
- Hazard levels from ThinkHazard are shown visually with color-coded severity.  
- Only hazards **supported by CIE** appear for projections.

### **3. Variable Selection**
- Each hazard corresponds to **specific climate variables** from CIE  
  (e.g., river flood → `fldfrc`, `flddph`, `ec2`).  
- The user chooses the variable from a dropdown.

### **4. Scenario Selection**
- Users select a future climate scenario.  
- Changing the scenario resets cached projection data.

### **5. Projection Retrieval**
For each selected hazard + region + scenario:
- Build region code candidates  
- Query CIE API  
- On failure → try next fallback  
- Store results in session state for speed  

### **6. Visualization**
- Line + Scatter charts only  
- Confidence interval shading when available  
- Metrics for key years (2025, 2050, 2100)  
- Raw dataset and descriptive statistics provided  
""")

st.markdown("---")

# LIMITATIONS

st.markdown("""
## Important Limitations

1. **Not all hazards have projections**  
   Hazards like tsunami, volcano, landslide, earthquake do not exist in the CIE dataset.

2. **Regional boundaries differ across datasets**  
   CIE’s region codes do not perfectly match ISO standards.

3. **City-level matches depend on ThinkHazard ADM tables**  
   If a city is missing → the tool falls back to the country.

4. **Fuzzy matching is not perfect**  
   Though improved, administrative names can still produce ambiguous results.

5. **Visualizations are indicative**  
   Values beyond 2060 are shown as *model-indicative*, not precise predictions.
""")

st.markdown("---")

# END / CONTACT / DEVELOPERS

st.markdown("""
## Further Information

If you need:
- documentation for deployment  
- data extraction  
- API endpoints  
- methodology extensions  

feel free to contact the maintainers or extend this page.

---

## Developers

**Andrea Lundal Forland** – Student at NOVA SBE  
**Gustav Emil Skoglund** – Student at NOVA SBE  
**Kristin Handland Hoff** – Student at NOVA SBE  
**Vivien Scaife Gibson** – Student at NOVA SBE  
""")

st.page_link("1_Location Search.py", label="← Back to App")
