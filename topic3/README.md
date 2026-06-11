# 10-Minute Cycling City Policy Dashboard
#Topic 3

## 1. Overview

This readme is for  Topic 3 and its code "topic3.py".

---

## 1.1 What the Dashboard Does

The dashboard builds an interface with:

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

## 2. Setup

The existing setup for this topic 3 has been already set up as follows:

```text
topic3/
├── topic3.py
├── datasets/
│   ├── combined_neighbourhood_dataset.csv
│   └── Bike_Trip purpose.xlsx              
└── data_cache/
    └── topic3/                             # created automatically
```

Please do not change this setup as the code assumes this file hierarchy. Every file is all set up in their correct locations.

---

## 2.1 Installation

Install the required packages:

```bash
python3 -m pip install streamlit plotly pandas numpy openpyxl requests folium streamlit-folium google-genai
```

## 2.2 Gemini Setup

This project uses Google Gemini API, for Gemini 3.5 Flash.
Get your own free API key in https://aistudio.google.com/.  You can create you own API key under Dashboard.


In the code "topic3.py", find:

```python
GEMINI_API_KEY = ""
```

Paste your key inside the quotes:

```python
GEMINI_API_KEY = "your_actual_api_key_here"
```
---
## 2.3 Running the Dashboard

From the project folder, run:

```bash
streamlit run topic3.py
```

Streamlit will open the dashboard in your browser.  
If it does not open automatically, copy the local URL from the terminal, usually:

```text
http://localhost:8501
```

---

## 3. Details

## 3.1 Datasets used

### `combined_neighbourhood_dataset.csv`

### `Bike_Trip purpose.xlsx`

These are already in the correct place as described above in 2. Setup. 

## 3.2 How the Access Score Works

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

## 3.3 Main Dashboard Views

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

## 3.4 What-If Scenario Section

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


---

##  3.5 AI Policy Assistant

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

## 3.6 Quick Use Steps

1. Run the Streamlit command.
2. Check that the dataset cards show the files as found.
3. Select a municipality from the map or dropdown.
4. Cycle through the graph explorer.
5. Choose a what-if scenario in the sidebar.
6. Read the updated scenario graphs.
7. Ask the assistant for a policy recommendation.

