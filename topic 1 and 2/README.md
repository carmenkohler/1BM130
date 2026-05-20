# 1BM130 – Group 5: Descriptive Analytics
## Notebook Usage Guide

---

## Overview

The notebook (`DescriptiveAnalysiseTopic1.ipynb`) produces all figures for **Section 1 (Descriptive Analytics)** of the Report. It combines four datasets to analyse 10-minute cycling access and local cycling behaviour across Dutch municipalities.

---

## Required Folder Structure

Place everything as follows relative to the notebook file:

```
project/
├── DescriptiveAnalysiseTopic1.ipynb
├── images/                         ← auto-created on first run
├── cache/                          ← auto-created on first run
└── Data/
    ├── CBS/
    │   ├── kwb2024.xlsx
    │   └── wijkenbuurten_2025_v1.gpkg
    ├── OdiN/
    │   └── ODiN2024 Updated with Header/
    │       └── ODiN2024_DANS_Databestand_ Updated.xlsx
    └── Extra data/
        ├── buurt_to_buurt.csv          ← ~17 GB, see note below
        ├── buurt_2025.csv
        ├── wijk_2025.csv
        ├── pc6hnr20250801_gwb.csv
        └── voorzieningen_per_buurt_klasse.csv
```

---

## Datasets

| File | Source | Description |
|------|--------|-------------|
| `kwb2024.xlsx` | CBS | Neighbourhood socioeconomic indicators (income, population, urbanisation) |
| `wijkenbuurten_2025_v1.gpkg` | CBS | GeoPackage with municipality and neighbourhood geometries for maps |
| `ODiN2024_DANS_Databestand_ Updated.xlsx` | ODiN / DANS | National travel survey 2024 — trip-level data with mode, distance, purpose, demographics |
| `buurt_to_buurt.csv` | SmartwayZ | Network routing distances between all Dutch neighbourhoods (~17 GB) |
| `buurt_2025.csv` | CBS | Neighbourhood reference table with codes and names |
| `wijk_2025.csv` | CBS | District reference table |
| `pc6hnr20250801_gwb.csv` | CBS | Postcode-6 to neighbourhood crosswalk |
| `voorzieningen_per_buurt_klasse.csv` | SmartwayZ | Amenity counts per neighbourhood and category |

---

## The 17 GB Routing File

`buurt_to_buurt.csv` is large and slow to process. The notebook handles this automatically:

- **First run:** the file is read in chunks of 250,000 rows and the results are cached to `cache/access_pipeline_v1.pkl`. This will take a while.
- **Subsequent runs:** the cache is loaded instantly — the 17 GB file is not read again.

> If you update `buurt_to_buurt.csv` or change the processing logic, delete `cache/access_pipeline_v1.pkl` to force a rebuild.

---

## Python Environment

Install dependencies with:

```bash
pip install pandas numpy matplotlib seaborn scipy geopandas openpyxl polars
```

Or with conda:

```bash
conda install pandas numpy matplotlib seaborn scipy geopandas openpyxl
pip install polars
```

Tested with Python 3.10+. The notebook uses a virtual environment at `.venv` if you use the project's existing setup.

---

## Running the Notebook

Run cells **top to bottom in order**. The sections depend on each other:

1. **Setup & Imports** — loads libraries and defines folder paths
2. **Data Loading** — reads all datasets into memory
3. **Data Preprocessing** — builds `df` (neighbourhood) and `df_trips` (ODiN trips) with all derived columns
4. **Neighbourhood merge** — joins CBS, SmartwayZ, and ODiN into one analysis dataframe; runs or loads the routing cache
5. **Build `df_access`** — filters to inhabited neighbourhoods with valid access scores
6. **Figures 1.1 – 1.15** — generate and save all report figures to `images/`

> Do **not** skip or reorder cells. Several dataframes (`df_trips`, `df_access`, `df_paired`, `df_social_exposure`) are built incrementally and used by later figure cells.

---

## Output Files

All figures are saved to the `images/` folder automatically when the relevant cell runs:

| File | Figure | Description |
|------|--------|-------------|
| `fig1_modal_split.png` | Additional | National modal split |
| `fig2_distance_dist.png` | 1.1 | Trip distance distribution by mode |
| `fig3_bikeusage_income.png` | 1.10 | Local cycling usage by income group |
| `fig4_modal_urbanisation.png` | 1.14 | Modal split by urbanisation class |
| `fig5_local_biking_province.png` | 1.5 | Local cycling share by province |
| `fig6_purpose_bike_vs_car.png` | 1.4 | Trip purpose: cycling vs. car |
| `fig7_biketype_agegroup.png` | 1.3 | Bike type share by age group |
| `fig8_time_dist.png` | Extra | Cycling trip time distribution |
| `fig9_modal_income.png` | Additional | Modal split by income group |
| `fig10_heatmap_income_urban.png` | 1.12 | Local cycling: income × urbanisation heatmap |
| `fig11_local_cycling_age.png` | Additional | Local cycling rate by age group |
| `fig12_biketype_participation.png` | Additional | Bike type by societal participation group |
| `fig13_access_usage_scatter.png` | Extra | Access vs. usage scatter plot |
| `fig14_access_by_income.png` | Extra | Bike-10 access score by income group |
| `fig15_usage_by_income_buurt.png` | Extra | Cycling usage by income (neighbourhood level) |
| `fig16_bike_vs_walk_access.png` | Extra | Bike-10 vs Walk-15 access by income |
| `fig17_municipality_ranking.png` | 1.6 | Top & bottom municipalities by access score |
| `fig18_access_boxplot_urban.png` | 1.13 | Access score distribution by urbanisation |
| `fig19_top_bottom_usage_mun.png` | 1.7 | Top & bottom municipalities by cycling usage |
| `fig20_ammenity_coverage.png` | 1.11 | Amenity coverage within 10-min bike-shed |
| `fig21_geopandas_maps_cbs.png` | 1.8 | Side-by-side choropleth: access vs. usage |
| `fig22_mismatch_map.png` | 1.8 | Policy opportunity map: access vs. usage mismatch |
| `fig23_direct_routing_bike_gain.png` | 1.9 | High-detour municipalities: projected access gain |
| `fig24_social_exposure_reachable_income_mix.png` | — | Social exposure: reachable population composition |
| `fig25_social_exposure_diversity_walk_vs_bike.png` | — | Diversity: Walk-15 vs Bike-10 |
| `fig26_social_exposure_gain_by_origin_income.png` | — | Diversity gain by origin income group |
| `fig27_social_exposure_gain_by_urbanity.png` | — | Diversity gain by urbanisation class |
| `fig28_social_exposure_municipality_gain.png` | — | Top & bottom municipalities by added social exposure |

---

## Key Variables

| Variable | Type | Description |
|----------|------|-------------|
| `df_trips` | DataFrame | ODiN 2024 trip-level data, filtered to regular trips (`Verpl == 1`) |
| `df_access` | DataFrame | Neighbourhood-level data, filtered to ≥200 inhabitants with valid access score |
| `df_paired` | DataFrame | Subset of `df_access` where ODiN usage data is also available |
| `df_social_exposure` | DataFrame | `df_access` merged with walk/bike social exposure tables |
| `bike10_weighted_score` | float | Weighted access score (0–100) for cycling within 3 km / 10 min |
| `pct_within_3km` | float | Share of essential cycling trips within 3 km (from ODiN) |


---

## Notes

- The `prov_map`, `sted_map`, and `age_labels` dictionaries are defined in the `df` preprocessing cell and must run before the `df_trips` cell.
- The maps figure (Fig 1.8) requires `geopandas` and reads `wijkenbuurten_2025_v1.gpkg` directly at runtime — it is not cached.
- Resolution for map figures is `dpi=300`; all other figures use `dpi=150`.