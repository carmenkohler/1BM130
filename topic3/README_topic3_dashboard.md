# 10-Minute Cycling City Policy Dashboard

---

## 1. Introduction
This project is a minimum viable urban policy dashboard for **Topic 3: LLM-based decision-support interface**.  
It translates the analytical results from Topic 1 and Topic 2 into an interactive dashboard where policymakers can select local CSV files from the project workspace, inspect access and usage patterns, run simple what-if scenarios, and ask an AI policy assistant for recommendations.

The dashboard is built with:

- **Python**
- **Streamlit** for the interface
- **Plotly** for interactive charts
- **Pandas / NumPy** for data handling
- **Gemini API** for the optional LLM-based policy assistant

The dashboard does **not** replace the predictive models.  
Instead, it acts as an explanation and policy-support layer on top of the existing analysis.

---

## 2. Project Folder Setup

Place `topic3_dashboard.py` inside your project folder.

The important thing is that the CSV files you want to use are somewhere inside the same workspace folder or one of its subfolders.

The dashboard scans the workspace using:

```python
WORKSPACE.glob("**/*.csv")
```

So it can find CSV files in nested folders such as:


---

## 3. What the Dashboard Does

The dashboard supports the following Topic 3 requirements:

### 3.1 Access–Usage View

The dashboard visualizes the relationship between:

- 10-minute cycling access to essential amenities
- local cycling usage or estimated usage

It classifies areas into simple policy cases:

- high access / high usage
- high access / low usage
- low access / high usage
- low access / low usage

These categories help identify where policy intervention may be needed.

---

### 3.2 Essential Function Audit

The dashboard checks which amenity/access variables are available in the selected CSV.

Examples of accepted variables include:

- `access_supermarket`
- `access_school`
- `access_gp`
- `dist_gp`
- `AfstandTotSchool`
- `AfstandTotGroteSupermarkt`
- `access_station`

The user can select one of these variables and inspect its distribution.

---

### 3.3 What-If Scenario Builder

The user can simulate simple interventions, such as:

- adding a grocery store / supermarket
- adding a GP / healthcare function
- adding a school
- improving cycling accessibility by 10%
- improving cycling accessibility by 20%

The dashboard updates:

- access score
- usage score
- policy case
- recommendation

This is a simple MVP scenario model, not a causal model.

---

### 3.4 AI-Agent Policy Assistant

The dashboard includes an optional Gemini-based AI assistant.

The assistant can answer questions such as:

```text
What intervention is most useful here?
```

```text
Explain the trade-off between adding amenities and improving cycling routes.
```

```text
Give me a short policy recommendation for this area.
```

The AI assistant only uses the dashboard context.  
It does not create new predictions and does not replace the model.

---

## 4. Main CSV Requirements

The main CSV is required.

The dashboard will scan your local workspace and ask you to select the main Topic 3 CSV from a dropdown.

The selected CSV must contain at least:

| Topic 3 component | Required meaning | Example variable names |
|---|---|---|
| Area name | Municipality, neighborhood, or region name | `municipality`, `Gemeentenaam`, `gm_naam`, `region`, `WijkenEnBuurten` |
| Access score | 10-minute cycling access score | `essential_access_score`, `bike10_weighted_score`, `access_score`, `bike10_score` |

Optional but useful columns:

| Component | Example variable names |
|---|---|
| Usage score | `pct_within_3km`, `usage_score`, `local_cycling_usage`, `cycling_usage` |
| Income context | `income`, `p_ink_li`, `low_income`, `inkomen` |
| Urbanisation context | `urbanisation`, `stedelijkheid`, `MateVanStedelijkheid` |
| Amenity audit variables | `access_supermarket`, `access_school`, `dist_gp`, `AfstandTotSchool` |

If the CSV does not contain a usage score, the dashboard creates a simple estimated usage score from the access score.

---

## 5. Optional Topic 2 CSV Requirements

The Topic 2 CSV is optional.

It is used to show lowest-income mode-choice context.

It should contain:

| Required meaning | Example variable names |
|---|---|
| Region | `region`, `RegioS_title`, `Regio` |
| Mode | `mode`, `mode_class`, `Vervoerwijzen` |
| Mode share | `mode_share`, `share`, `percentage`, `value` |

If no Topic 2 CSV is selected, the dashboard still works.  
The mode-choice section will simply show a warning that no valid Topic 2 file was selected.

---

## 6. Automatic Variable Detection

When you select a CSV file, the dashboard automatically detects the columns.

It prints:

- detected area column
- detected access score column
- detected usage column
- detected income column
- detected urbanisation column
- detected amenity audit columns

If the selected CSV does not contain the minimum required columns, the dashboard shows an error and asks you to select another file.

The minimum required columns are:

1. an area name column  
2. an access score column  

Without these two, the dashboard cannot run.

---

## 7. Installation

Open Terminal in the project folder and install the required packages:

```bash
pip install streamlit pandas numpy plotly google-genai
```

If you do not want to use the Gemini AI assistant, the dashboard still works without an API key.  
In that case, it uses a rule-based fallback response.

---

## 8. Gemini API Key Setup
For this project we will be using Google Gemini.

A free API key can be generated under https://aistudio.google.com .

Once you get your API key, follow below:
	
In `topic3_dashboard.py`, find this line:

```python
GEMINI_API_KEY = "PASTE_YOUR_GEMINI_API_KEY_HERE"
```

Replace it with your Gemini API key:

```python
GEMINI_API_KEY = "your_actual_api_key_here"
```

Example:

```python
GEMINI_API_KEY = "AIzaSy..."
```

Do not upload your API key to GitHub or include it in the final report.

If you do not paste a key, the dashboard still works.  
The AI assistant will use a basic rule-based fallback answer instead of Gemini.

---

## 9. How to Run the Dashboard

From the project folder, run:

```bash
streamlit run topic3_dashboard.py
```

A browser window should open automatically.

If it does not open, Streamlit will print a local URL such as:

```text
http://localhost:8501
```

Open that URL in your browser.

---

## 10. How to Use the Dashboard

### Step 1: Put CSV files in the workspace
as explained
### Step 2: Run Streamlit
as explained
### Step 3: Select the main CSV

At the top of the dashboard, select the main Topic 3 access/access-usage CSV from the dropdown.

The dashboard will show the selected local path, for example:

```text
/Users/yourname/Desktop/Q4-HW/data_cache/municipality_essential_access_scores.csv
```

Then it will detect and print the variables it found.

If the file does not match, select another CSV from the dropdown.

---

### Step 4: Optionally select the Topic 2 CSV

Select a Topic 2 mode-choice CSV if available.

Example:

```text
data_cache/topic2/topic2_lowest_income_mode_share_by_region.csv
```

If you do not select this file, the rest of the dashboard still works.

---

### Step 5: Select an area

Use the sidebar to select a municipality, neighborhood, or region.

The dashboard will show:

- Bike-10 access score
- local usage score
- policy case
- recommendation

---

### Step 6: Explore the Access–Usage chart

The scatterplot shows whether areas have:

- high access and high usage
- high access and low usage
- low access and high usage
- low access and low usage

This helps identify policy opportunities.

---

### Step 7: Use the Essential Function Audit

Select one amenity/access variable.

The dashboard shows:

- summary statistics
- distribution plot

This helps identify whether neighborhoods are well-served or underserved for specific amenities.

---

### Step 8: Run a What-If Scenario

Choose a scenario from the sidebar.

Examples:

- Add grocery / supermarket
- Add GP / healthcare
- Add school
- Improve cycling accessibility by 10%
- Improve cycling accessibility by 20%

The dashboard updates the scenario access score, usage score, policy case, and recommendation.

---

### Step 9: Ask the AI Policy Assistant

Use the chat box at the bottom.

Example questions:

```text
What intervention is most useful here?
```

```text
Explain the trade-off between adding amenities and improving cycling routes.
```

```text
Give me a short policy recommendation for this area.
```

The AI assistant responds using only the selected dashboard context.

---

## 11. What the Dashboard Outputs Mean

### Bike-10 Access Score

This is the 10-minute cycling accessibility score.

If the score is between 0 and 1, the dashboard converts it to 0–100 automatically.

### Local Usage Score

This is the local cycling usage score.

If the selected CSV does not contain a usage column, the dashboard creates a simple estimated usage proxy.

### Policy Case

The dashboard classifies each area as:

| Policy case | Meaning |
|---|---|
| High access / high usage | The area already performs well |
| High access / low usage | Amenities are nearby, but people may not cycle enough |
| Low access / high usage | Cycling demand exists despite weaker access |
| Low access / low usage | Both access and cycling conditions may need improvement |

---

## 12. Important Limitations

This dashboard is a minimum viable product.

It has the following limitations:

- The what-if scenario model is simple and illustrative.
- The dashboard does not prove causal effects.
- If no observed usage score is selected, usage is estimated using a basic proxy.
- The AI assistant explains the dashboard outputs but does not create independent predictions.
- The quality of the dashboard depends on the selected CSV columns.
- The dashboard can only scan CSV files inside the local workspace folder, not arbitrary files elsewhere on the computer.

---

## 13. Troubleshooting

### Problem: No CSV files appear in the dropdown

Make sure your CSV files are inside the same folder as `topic3_dashboard.py` or inside a subfolder.

Then refresh the Streamlit page.

---

### Problem: The selected CSV gives an error

The file probably does not contain the minimum required columns.

The main CSV must contain:

- an area column
- an access score column

Try selecting another CSV, such as:

```text
processed_buurt_essential_access_scores.csv
municipality_essential_access_scores.csv
```

---

### Problem: The dashboard says no usage column was found

This is not fatal.

The dashboard will create an estimated usage score from the access score.

For a better dashboard, use a CSV that contains one of:

```text
pct_within_3km
usage_score
local_cycling_usage
cycling_usage
```

---

### Problem: Gemini does not answer

Check that:

1. `google-genai` is installed:

```bash
pip install google-genai
```

2. You pasted your API key into:

```python
GEMINI_API_KEY = "PASTE_YOUR_GEMINI_API_KEY_HERE"
```

If no Gemini key is provided, the dashboard uses a rule-based fallback.

