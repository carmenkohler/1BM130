# 10-Minute Cycling City Policy Dashboard

## Overview

This dashboard is the minimum viable product for **Topic 3: LLM-based decision-support interface**.  
It turns the project outputs into a simple policy tool where a user can inspect 10-minute cycling accessibility, low-income context, local usage patterns, and simple what-if scenarios.

The current dashboard focuses on:

- **10-minute cycling access** to essential amenities.
- **Low-income neighbourhood context** using `p_ink_li`.
- **First-10-minute usage** using `pct_within_10min`.
- **Municipality and neighbourhood inspection** through maps and interactive graphs.
- **Scenario testing** for amenity or accessibility improvements.
- **Gemini / fallback assistant** for policy-oriented explanations.


---

## What the Dashboard Does

The dashboard automatically searches the local `datasets/` folder for the required project data and then builds an interface with:

1. Dataset status cards showing whether the required files were found.
2. A Netherlands municipality map for selecting a municipality.
3. A fallback municipality dropdown if the map is unavailable.
4. A selected municipality summary with:
   - Bike-10 access score,
   - low-income share,
   - low-access neighbourhood share.
5. A graph explorer with original dataset views.
6. A separate what-if scenario section with updated scenario graphs.
7. A policy assistant that explains the selected municipality and scenario.

---

## Folder Setup

Place the dashboard script in the project folder and create a `datasets/` folder next to it.

```text
Q4-HW/
├── topic3_dashboard_final.py
├── datasets/
│   ├── combined_neighbourhood_dataset.csv
│   └── Bike_Trip purpose.xlsx              # optional
└── data_cache/
    └── topic3/                             # created automatically
```

The dashboard creates and uses `data_cache/topic3/` automatically for downloaded map boundary files.

---

## Required Dataset

### `combined_neighbourhood_dataset.csv`

This is the main dataset used by the dashboard. It should be placed inside:

```text
datasets/combined_neighbourhood_dataset.csv
```

The dashboard expects this file to already contain the merged neighbourhood-level information from the earlier project stages.

### Required columns

```text
regio
gm_naam
a_inw
bev_dich
p_ink_li
ste_mvs
pct_within_10min
```

### Important expected columns

The dashboard also looks for `bike10_klasse_*` amenity columns, for example:

```text
bike10_klasse_apotheek
bike10_klasse_basisschool
bike10_klasse_bushalte
bike10_klasse_huisarts
bike10_klasse_kinderopvang
bike10_klasse_supermarkt
bike10_klasse_treinstation
bike10_klasse_voortgezet_onderwijs
bike10_klasse_ziekenhuis
```

These are used to build the amenity-specific access scores.

---

## Optional Dataset

### `Bike_Trip purpose.xlsx`

This file is optional. If it exists, the dashboard adds a cycling-purpose context graph.

Expected location:

```text
datasets/Bike_Trip purpose.xlsx
```

Expected sheet:

```text
Bike_Trip purpse
```

Required columns:

```text
AfstV
Bike type (main mode)
Urbanization level
Trip purpose
Total Trips
Sample Trips
```

If this file is missing, the dashboard still runs.

---

## How the Access Score Works

The dashboard builds a consistent amenity-class access score from the `bike10_klasse_*` variables.

Each amenity class is scored as:

```text
0 reachable amenities  = 0
1 reachable amenity    = 70
2+ reachable amenities = 100
```

The final `bike10_access_score` is the average of the available amenity scores.

If `bike10_weighted_score` already exists in the dataset, the dashboard uses it as the main access score. If not, it uses the calculated class-based access score.

---

## Main Dashboard Views

The graph explorer contains the original, unchanged dataset views:

1. **Access-Usage Heatmap**  
   Shows municipalities by Bike-10 access score and first-10-minute usage. It highlights:
   - environmental success: high access and high usage,
   - policy opportunity: high access but lower usage,
   - access gaps: lower access with cycling demand.

2. **3 km bike-shed for selected neighbourhood**  
   Lets the user choose a neighbourhood inside the selected municipality and displays an approximate 3 km cycling radius.  
   Boundary matching now tries:
   - neighbourhood code,
   - municipality + neighbourhood name,
   - unique neighbourhood-name match,
   - municipality-centre fallback if no safe match is found.

3. **National access-income context**  
   Shows where the selected municipality sits compared with other municipalities using access score and low-income share.

4. **Essential function audit**  
   Compares the selected municipality with the national average for each amenity category.

5. **Low-access neighbourhood ranking**  
   Lists the weakest-access neighbourhoods in the selected municipality.

6. **Neighbourhood access vs low-income share**  
   Checks whether low-access neighbourhoods overlap with higher low-income shares.

7. **Cycling-purpose context**  
   Uses the optional Bike Trip Purpose file to summarize essential cycling trips and bike type patterns.

---

## What-If Scenario Section

The sidebar lets the user choose one scenario:

```text
No scenario
Add grocery / supermarket
Add GP / healthcare
Add school / childcare access
Improve cycling accessibility by 10%
Improve cycling accessibility by 20%
```

The original graphs stay unchanged.  
The scenario section separately shows the updated views after applying the scenario:

- updated Bike-10 access score,
- updated policy case,
- updated Access-Usage Heatmap,
- updated Essential Function Audit,
- updated Low-Access Neighbourhood Ranking.

The scenario model is intentionally simple and illustrative. It supports policy discussion, not causal prediction.

---

## AI Policy Assistant

At the bottom of the dashboard, users can ask questions such as:

```text
What if we add a supermarket to the lowest-access neighbourhoods?
Should this municipality prioritise amenities or cycling infrastructure?
How does the low-income focus change the recommendation?
Give me a short policy recommendation for a presentation slide.
```

The assistant receives only the current dashboard context, including:

- selected municipality,
- original access and usage scores,
- low-income share,
- low-access neighbourhood share,
- selected scenario,
- updated access and usage scores.

If Gemini is unavailable or the API key is empty, the dashboard uses a rule-based fallback answer.

---

## Gemini Setup

Install the Gemini package:

```bash
python3 -m pip install google-genai
```

In the dashboard script, find:

```python
GEMINI_API_KEY = ""
```

Paste your key inside the quotes:

```python
GEMINI_API_KEY = "your_actual_api_key_here"
```

Do not upload your real API key to GitHub or submit it in the report.

---

## Installation

Install the required packages:

```bash
python3 -m pip install streamlit plotly pandas numpy openpyxl requests folium streamlit-folium google-genai
```

If Gemini is not used, the dashboard still runs with the fallback assistant.

---

## Running the Dashboard

From the project folder, run:

```bash
streamlit run topic3_dashboard_final.py
```

Streamlit will open the dashboard in your browser.  
If it does not open automatically, copy the local URL from the terminal, usually:

```text
http://localhost:8501
```

---

## Quick Use Steps

1. Put `combined_neighbourhood_dataset.csv` in the `datasets/` folder.
2. Optionally add `Bike_Trip purpose.xlsx`.
3. Run the Streamlit command.
4. Check that the dataset cards show the files as found.
5. Select a municipality from the map or dropdown.
6. Cycle through the graph explorer.
7. Choose a what-if scenario in the sidebar.
8. Read the updated scenario graphs.
9. Ask the assistant for a policy recommendation.

---

## Summary of the Final MVP

The final dashboard provides a practical, low-income-focused urban planning interface. It combines neighbourhood access data, municipality-level summaries, map-based selection, scenario testing, and an LLM-style explanation layer. The tool is designed to help policymakers quickly identify where 10-minute cycling access is strong, where access is weak, where low-income residents may be more affected, and what type of intervention is most reasonable to discuss.
