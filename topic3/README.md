# 10-Minute Cycling City Policy Dashboard

## 1. Introduction

This project is a minimum viable urban policy dashboard for **Topic 3: LLM-based decision-support interface**.

The dashboard translates the results from Topic 1 and Topic 2 into a simple interactive tool for policymakers. It focuses on **low-income residents** and helps users explore whether selected municipalities have good 10-minute cycling access to essential amenities, where low-access neighbourhoods are located, how low-income mode choice behaves in the ODiN data, and what policy actions may be useful under simple what-if scenarios.

The dashboard is built with:

- **Python**
- **Streamlit** for the interface
- **Plotly** for interactive graphs
- **Pandas / NumPy** for data handling
- **Gemini API** for the optional LLM-based policy assistant

The LLM assistant does **not** replace the predictive or descriptive models. It acts as an explanation layer that summarizes dashboard results and gives policy-oriented recommendations based on the selected municipality and scenario.

---

## 2. Main Workflow

The current version of the dashboard no longer asks the user to manually upload or choose many files. Instead, it automatically searches the local `datasets/` folder and detects the three expected project datasets.

The interface contains:

1. **Three dataset bubbles** showing whether the required datasets were found.
2. **Dashboard controls** in the sidebar for selecting a municipality and a what-if scenario.
3. **Municipality summary cards** showing access score, low-income share, and low-access neighbourhood share.
4. **A graph carousel** where the user can move through different result graphs with Previous / Next buttons.
5. **A Gemini scenario assistant** at the bottom for natural-language policy questions.

---

## 3. Folder Setup

Use this folder structure:

```text
Q4-HW/
├── topic3py
└── datasets/
    ├── kwb2025.xlsx
    ├── ODiN2024_DANS_Databestand_ Updated.xlsx
    ├── Bike_Trip purpose.xlsx
    └── Codeboek_DANS_ODiN_2024.xlsx   # optional but recommended
```

The dashboard expects all data files to be inside the `datasets/` folder.

The script automatically searches for files with names matching:

```text
kwb2025.xlsx
ODiN2024_DANS_Databestand_ Updated.xlsx
Bike_Trip purpose.xlsx
```

If a required file is missing, the dashboard shows a clear warning in the interface.

---

## 4. Required Dataset 1: CBS KWB 2025

### Expected file

```text
kwb2025.xlsx
```

### Expected sheet

```text
KWB2025
```

### Purpose in the dashboard

This is the main spatial-access dataset. It provides neighbourhood and municipality-level information about population, income, urbanisation, and distances to essential amenities.

The dashboard uses it to create a **continuous Bike-10 access score**.

### Required columns

```text
regio
gm_naam
a_inw
bev_dich
p_ink_li
ste_mvs
g_afs_hp
g_afs_gs
g_afs_kv
g_afs_sc
g_3km_sc
```

### Meaning of key columns

| Column | Meaning |
|---|---|
| `regio` | Neighbourhood name |
| `gm_naam` | Municipality name |
| `a_inw` | Number of residents |
| `bev_dich` | Population density |
| `p_ink_li` | Share of low-income residents |
| `ste_mvs` | Urbanisation code |
| `g_afs_hp` | Distance to GP / doctor |
| `g_afs_gs` | Distance to large supermarket |
| `g_afs_kv` | Distance to childcare |
| `g_afs_sc` | Distance to school |
| `g_3km_sc` | Number of schools within 3 km |

---

## 5. Bike-10 Access Score

The dashboard creates a **continuous access score** instead of only using a binary yes/no score.

The score is calculated from five amenity-access components:

```text
score_gp
score_supermarket
score_childcare
score_school_distance
score_schools_within_3km
```

For distance-based amenities, the logic is:

```text
0 km distance = 100 access score
3 km or more = 0 access score
```

For the number of schools within 3 km, the score is scaled up to a maximum of 5 schools:

```text
0 schools = 0
5 or more schools = 100
```

The final `bike10_access_score` is the average of these components.

This continuous scoring method was chosen because the earlier binary method made many municipalities look like they had almost perfect access. The continuous score preserves differences between stronger and weaker access areas.

---

## 6. Required Dataset 2: Detailed ODiN 2024

### Expected file

```text
ODiN2024_DANS_Databestand_ Updated.xlsx
```

### Expected sheet

```text
ODiN2024_DANS_Databestand_v2.0
```

### Purpose in the dashboard

This dataset is used to focus on the **lowest-income group** and inspect mode choice patterns.

The dashboard filters the data to the lowest available `HHGestInkG` group and summarizes how that group travels by:

- national mode choice,
- first-10-minute trips,
- trip purpose,
- urbanisation class.

### Required columns

```text
HHGestInkG
Hvm
MotiefV
Sted
Prov
Reisduur
FactorV
```

### Optional column

```text
AfstV
```

### Meaning of key columns

| Column | Meaning |
|---|---|
| `HHGestInkG` | Household income group |
| `Hvm` | Main transport mode |
| `MotiefV` | Trip purpose |
| `Sted` | Urbanisation class |
| `Prov` | Province |
| `Reisduur` | Travel duration |
| `FactorV` | Trip weight |
| `AfstV` | Trip distance, optional |

### Performance note

The ODiN file is large, so the dashboard avoids loading it repeatedly. It:

- reads only the required columns,
- loads ODiN only when an ODiN graph is opened in the carousel,
- caches the resulting summaries with `st.cache_data`.

The first ODiN graph may still take some time to load, but after that it should be faster.

---

## 7. Optional Dataset 3: Bike Trip Purpose Context

### Expected file

```text
Bike_Trip purpose.xlsx
```

### Expected sheet

```text
Bike_Trip purpse
```

### Purpose in the dashboard

This file provides lighter ODiN-derived cycling context. It is not municipality-specific, but it helps interpret cycling behaviour by trip purpose, bike type, and whether essential cycling trips are within 3 km.

### Required columns

```text
AfstV
Bike type (main mode)
Urbanization level
Trip purpose
Total Trips
Sample Trips
```

If this file is missing, the dashboard still works, but the cycling-purpose context graph is skipped.

---

## 8. Optional Dataset 4: ODiN Codebook

The script can use an ODiN codebook if it is found in the `datasets/` folder.

The codebook helps translate coded values in ODiN, such as `Hvm`, `MotiefV`, `Sted`, and `Prov`, into readable labels.

The script searches for a file with a name matching:

```text
Codeboek.*ODiN
ODiN.*Codeboek
```

If the codebook is missing, the dashboard still runs, but mode and urbanisation mapping may be less readable.

---

## 9. Graph Carousel

The dashboard uses a carousel instead of a long list of graphs. Use the **Previous graph** and **Next graph** buttons to cycle through the available result views.

Current graph list:

1. **Selected municipality in national access-income context**  
   Shows the selected municipality compared with other municipalities. If income data is missing, it falls back to an access-vulnerability graph.

2. **Selected municipality essential function audit**  
   Compares GP, supermarket, childcare, school-distance, and school-count access for the selected municipality against national averages.

3. **Low-access neighbourhoods in selected municipality**  
   Shows which neighbourhoods inside the selected municipality have the weakest Bike-10 access scores.

4. **Neighbourhood access vs low-income share in selected municipality**  
   Checks whether lower-access neighbourhoods also have higher low-income shares. If income is missing, it falls back to a neighbourhood access ranking.

5. **Low-income national mode choice**  
   Uses detailed ODiN to show the national mode split for the lowest-income group.

6. **Low-income first-10-minute mode choice**  
   Uses `Reisduur <= 10` to compare transport modes within the first 10 minutes. This keeps the comparison equal across bike, car, and public transport instead of using only a 3 km cycling threshold.

7. **Low-income mode choice by trip purpose**  
   Shows whether the lowest-income group relies more on car, bike, or public transport for different purposes.

8. **Low-income mode choice by urbanisation**  
   Shows how low-income mode choice changes across urbanisation classes.

9. **Cycling-purpose context from Bike Trip file**  
   Uses the lighter Bike Trip file to show essential cycling trips within 3 km and cycling trips by purpose and bike type.

The first four graphs change when the selected municipality changes. The ODiN graphs are national low-income summaries, so they do not change by municipality in this MVP.

---

## 10. Low-Income Focus

The dashboard focuses on low-income residents in two ways:

1. From CBS KWB, it uses `p_ink_li` as the municipality and neighbourhood low-income context.
2. From ODiN, it filters to the lowest available `HHGestInkG` group.

The ODiN low-income filter is displayed in the interface, for example:

```text
ODiN filter: lowest HHGestInkG group = 1; filtered rows = 12,828.
```

This means the ODiN mode-choice graphs are only describing the lowest-income group.

---

## 11. Policy Case Logic

The dashboard classifies municipalities based on access and low-income context.

The current policy cases are:

| Policy case | Meaning |
|---|---|
| High access / lower low-income pressure | Access is strong and low-income pressure is relatively lower |
| High access / higher low-income pressure | Access is strong, but equity attention is still important |
| Low access / lower low-income pressure | Access weakness exists, but low-income pressure is less concentrated |
| Low access / higher low-income pressure | Priority equity case: weaker access and stronger low-income pressure overlap |

These are decision-support labels, not causal claims.

---

## 12. What-If Scenario Section

At the bottom of the dashboard, the user can select a scenario from the sidebar:

```text
No scenario
Add grocery / supermarket
Add GP / healthcare
Add school / childcare access
Improve cycling accessibility by 10%
Improve cycling accessibility by 20%
```

The selected scenario changes the scenario access score and policy case.

The scenario model is simple and illustrative. It is used for demonstration and policy discussion, not for causal prediction.

---

## 13. Gemini Policy Assistant

The dashboard includes a Gemini-based AI policy assistant at the bottom.

Example questions shown in the interface include:

```text
What if we add a supermarket to the lowest-access neighbourhoods?
```

```text
Should this municipality prioritise amenities or cycling infrastructure?
```

```text
How does the low-income focus change the recommendation?
```

```text
Give me a short policy recommendation for a presentation slide.
```

The assistant receives the selected municipality, current access score, low-income share, low-access neighbourhood share, selected scenario, and scenario score. It is instructed to:

- focus on low-income equity,
- avoid causal claims,
- avoid inventing numbers,
- provide concise policy-oriented advice.

If Gemini is unavailable, the dashboard uses a rule-based fallback response.

---

## 14. Gemini API Key Setup

Install the Gemini package:

```bash
pip install google-genai
```

In `topic3_dashboard.py`, find:

```python
GEMINI_API_KEY = "PASTE_YOUR_GEMINI_API_KEY_HERE"
```

Replace it with your own API key:

```python
GEMINI_API_KEY = "your_actual_api_key_here"
```

Do not upload your real API key to GitHub or include it in the final report.

The script tries Gemini models with available quota. If a model fails due to quota, the script can fall back to another model or to the rule-based assistant.

---

## 15. Installation

From the project folder, install the required packages:

```bash
pip install streamlit pandas numpy plotly openpyxl google-genai
```

If you do not want to use Gemini, the dashboard can still run without a working API key, but the assistant will use the fallback response.

---

## 16. How to Run

From the project folder, run:

```bash
streamlit run topic3_dashboard.py
```

If your file has a different name, run that file instead, for example:

```bash
streamlit run topic3_dashboard_low_income_simplified_muni_fix_v4.py
```

Streamlit will open a browser window. If it does not open automatically, copy the local URL shown in the terminal, usually:

```text
http://localhost:8501
```

---

## 17. How to Use the Dashboard

1. Put the required files in the `datasets/` folder.
2. Start the dashboard with Streamlit.
3. Check the three dataset bubbles at the top.
4. Select a municipality in the sidebar.
5. Select a what-if scenario in the sidebar.
6. Use Previous / Next to cycle through graphs.
7. Use the Gemini assistant at the bottom to ask policy questions.

