# 1BM130 – Group 5: Descriptive Analytics
## Topic 1 and 2:  Notebook Usage Guide

---

## 1. Overview
This readme is for both Topic 1 and Topic 2.

The notebook for topic 1 (`topic1.ipynb`) produces all figures for **Section 1 (Descriptive Analytics)** of the Report. It combines four datasets to analyse 10-minute cycling access and local cycling behaviour across Dutch municipalities.

The notebook for Topic 2 (`topic2.ipynb`) develops and evaluates a **travel mode prediction model** using ODiN trip data and neighbourhood-level accessibility indicators generated in Topic 1. The notebook performs data preprocessing, feature engineering, feature selection, model training, hyperparameter tuning, model evaluation, and model export.

Two machine learning models are considered:

- Random Forest

- XGBoost

The final output is a trained XGBoost model together with evaluation results and metadata, which are later used by the Topic 3 policy dashboard for scenario analysis and mode-choice predictions.

---

## 2. Setup

Every dataset and file except from "buurt_to_buurt.csv" is currently included in this workspace. As this csv is 17GB, only it couldnt be uploaded.

See the current file hierarchy below:

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
 |____outputs/
      |______combined_neighbourhood_dataset.csv
```
See note below in 2.2 for what to do for this 17GB csv file.
---


## 2.1 Python Environment

The dependencies are installed automatically with the first cell of both notebooks.

Both notebooks tested with Python 3.10+. The notebook uses a virtual environment at `.venv` if you use the project's existing setup.

---
## 2.2 The 17 GB Routing File

The "buurt_to_buurt.csv" file was supplied to us by the professor in Canvas:
    https://canvas.tue.nl/courses/32238/files/7055066?wrap=1
    As this csv is 17GB, only it couldnt be uploaded.
     Please insert this file to the correct folder as given in the hierarchy above in Section 2. Setup .
---

## 3. Running the Notebook
Run the notebook "topic1.ipynb" for topic 1.
Run the notebook "topic2.ipynb" for topic 2.
Run cells **top to bottom in order**. The sections depend on each other.
---


