# ============================================================
# Descriptive analytics figures for 10-minute cycling city
#
# Inputs in project root:
# - Bike_Trip purpose.xlsx
# - gem_2025.csv
#
# Pulled automatically:
# - CBS KWB 2025 buurt-level table 86165NED through CBS OData API
#
# Outputs:
# - Figures/1. Descriptive analytics/*.png
# - data_cache/cbs_kwb_2025_buurten_86165NED.csv
# - data_cache/processed_buurt_essential_access_scores.csv
# - data_cache/municipality_essential_access_scores.csv
# ============================================================

from pathlib import Path
import re
import time
import warnings
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 0. Paths
# ============================================================

WORKSPACE = Path(__file__).resolve().parent

BIKE_FILE = WORKSPACE / "Bike_Trip purpose.xlsx"
GEM_FILE = WORKSPACE / "gem_2025.csv"

CACHE_DIR = WORKSPACE / "data_cache"
OUT_DIR = WORKSPACE / "Figures" / "1. Descriptive analytics"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

CBS_KWB_CACHE = CACHE_DIR / "cbs_kwb_2025_buurten_86165NED.csv"


# ============================================================
# 1. Helper functions
# ============================================================

def clean_numeric(series):
    """
    Convert CBS-style numeric columns to float.
    Handles decimal commas, missing values, and non-numeric symbols.
    """
    return (
        series.astype(str)
        .str.replace(",", ".", regex=False)
        .str.replace(" ", "", regex=False)
        .replace({
            ".": np.nan,
            "nan": np.nan,
            "None": np.nan,
            "": np.nan,
            "x": np.nan,
            "X": np.nan
        })
        .pipe(pd.to_numeric, errors="coerce")
    )


def find_col(df, patterns, required=False):
    """
    Find the first column matching one of the regex patterns.
    """
    for pat in patterns:
        regex = re.compile(pat, re.IGNORECASE)
        matches = [c for c in df.columns if regex.search(str(c))]
        if matches:
            return matches[0]

    if required:
        raise ValueError(f"No column found for patterns: {patterns}")

    return None


def save_fig(filename):
    path = OUT_DIR / filename
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


def show_columns_like(df, keywords, max_results=100):
    """
    Print columns matching keywords.
    Useful for checking CBS column names.
    """
    pattern = re.compile("|".join(keywords), re.IGNORECASE)
    cols = [c for c in df.columns if pattern.search(str(c))]

    print(f"\nColumns matching {keywords}:")
    for c in cols[:max_results]:
        print("  ", c)

    if len(cols) > max_results:
        print(f"  ... and {len(cols) - max_results} more")


# ============================================================
# 2. CBS API functions
# ============================================================

def fetch_cbs_json(url, timeout=120):
    """
    Fetch CBS OData JSON and return all records.
    Follows @odata.nextLink if CBS paginates.
    """
    rows = []
    page = 1

    while url:
        print(f"  Fetching page {page}...")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        if "value" in data:
            rows.extend(data["value"])
            url = data.get("@odata.nextLink")
        elif "d" in data:
            rows.extend(data["d"].get("results", []))
            url = data["d"].get("__next")
        else:
            raise ValueError("Unexpected CBS OData response format.")

        page += 1
        time.sleep(0.1)

    return rows


def fetch_cbs_dimension(table_id, dimension_name):
    """
    Fetch one dimension table from CBS OData.
    For KWB 2025, the region dimension is WijkenEnBuurten.
    """
    url = f"https://opendata.cbs.nl/ODataApi/OData/{table_id}/{dimension_name}?$format=json"
    rows = fetch_cbs_json(url)
    return pd.DataFrame(rows)


def detect_region_key_column(region_df):
    """
    CBS dimension tables usually contain Key and Title.
    """
    for c in ["Key", "key", "Id", "ID"]:
        if c in region_df.columns:
            return c

    raise ValueError(f"Could not find region key column. Columns: {list(region_df.columns)}")


def build_or_filter(column, values):
    """
    Build OData filter:
    WijkenEnBuurten eq 'BU00030000' or WijkenEnBuurten eq 'BU00030001'
    """
    return " or ".join([f"{column} eq '{v}'" for v in values])


def fetch_cbs_kwb_2025_buurten_chunked(
    cache_path,
    table_id="86165NED",
    region_dimension="WijkenEnBuurten",
    chunk_size=100,
    force_download=False
):
    """
    Download CBS KWB 2025 only for buurt/neighborhood rows.

    This avoids the CBS 10,000-record query limit by:
    1. Downloading the WijkenEnBuurten dimension.
    2. Selecting region keys starting with BU.
    3. Querying TypedDataSet in chunks.
    """

    cache_path = Path(cache_path)

    if cache_path.exists() and not force_download:
        print(f"Loading cached CBS KWB buurt table: {cache_path}")
        return pd.read_csv(cache_path, low_memory=False)

    print("Downloading CBS WijkenEnBuurten dimension...")
    regions = fetch_cbs_dimension(table_id, region_dimension)

    print("\nRegion dimension columns:")
    print(list(regions.columns))

    key_col = detect_region_key_column(regions)

    buurt_keys = (
        regions[key_col]
        .astype(str)
        .loc[lambda s: s.str.startswith("BU")]
        .dropna()
        .unique()
        .tolist()
    )

    print(f"\nFound {len(buurt_keys):,} buurt region keys.")

    all_rows = []
    total_chunks = (len(buurt_keys) + chunk_size - 1) // chunk_size

    for start in range(0, len(buurt_keys), chunk_size):
        chunk = buurt_keys[start:start + chunk_size]
        chunk_no = start // chunk_size + 1

        filter_query = build_or_filter(region_dimension, chunk)

        url = (
            f"https://opendata.cbs.nl/ODataApi/OData/{table_id}/TypedDataSet"
            f"?$filter={filter_query}"
            f"&$format=json"
        )

        print(f"\nDownloading KWB buurt chunk {chunk_no}/{total_chunks} ({len(chunk)} buurten)...")

        try:
            rows = fetch_cbs_json(url)
            all_rows.extend(rows)
            print(f"  total rows downloaded: {len(all_rows):,}")

        except requests.exceptions.HTTPError as e:
            print(f"  Chunk failed with: {e}")
            print("  Retrying this chunk with smaller subchunks of 20...")

            for sub_start in range(0, len(chunk), 20):
                subchunk = chunk[sub_start:sub_start + 20]

                sub_filter_query = build_or_filter(region_dimension, subchunk)

                sub_url = (
                    f"https://opendata.cbs.nl/ODataApi/OData/{table_id}/TypedDataSet"
                    f"?$filter={sub_filter_query}"
                    f"&$format=json"
                )

                rows = fetch_cbs_json(sub_url)
                all_rows.extend(rows)
                print(f"    total rows downloaded: {len(all_rows):,}")

        time.sleep(0.2)

    df = pd.DataFrame(all_rows)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)

    print(f"\nSaved CBS KWB buurt table to: {cache_path}")
    print("Shape:", df.shape)

    return df


# ============================================================
# 3. Download / load CBS KWB buurt table
# ============================================================

kwb = fetch_cbs_kwb_2025_buurten_chunked(
    cache_path=CBS_KWB_CACHE,
    table_id="86165NED",
    region_dimension="WijkenEnBuurten",
    chunk_size=100,
    force_download=False
)

print("\nCBS KWB loaded.")
print("Shape:", kwb.shape)


# ============================================================
# 4. Bike behavior figures from Bike_Trip purpose.xlsx
# ============================================================

if not BIKE_FILE.exists():
    raise FileNotFoundError(f"Missing file: {BIKE_FILE}")

bike_trips = pd.read_excel(BIKE_FILE, sheet_name="Bike_Trip purpse")
bike_decay = pd.read_excel(BIKE_FILE, sheet_name="Datainput")

bike_trips.columns = [str(c).strip() for c in bike_trips.columns]
bike_decay.columns = [str(c).strip() for c in bike_decay.columns]

required_bike_cols = [
    "Trip purpose",
    "Bike type (main mode)",
    "AfstV",
    "Total Trips",
    "Sample Trips"
]

missing = [c for c in required_bike_cols if c not in bike_trips.columns]

if missing:
    raise ValueError(f"Missing required columns in Bike_Trip purpose.xlsx: {missing}")

bike_trips["AfstV"] = clean_numeric(bike_trips["AfstV"])
bike_trips["Total Trips"] = clean_numeric(bike_trips["Total Trips"])
bike_trips["Sample Trips"] = clean_numeric(bike_trips["Sample Trips"])

essential_keywords = [
    "work",
    "education",
    "school",
    "shopping",
    "groceries",
    "service",
    "services",
    "medical",
    "doctor",
    "care"
]


def is_essential_purpose(x):
    x = str(x).lower()
    return any(k in x for k in essential_keywords)


bike_trips["is_essential"] = bike_trips["Trip purpose"].apply(is_essential_purpose)

# 10-minute cycling radius:
# 18 km/h means around 3 km in 10 minutes.
bike_trips["within_3km"] = bike_trips["AfstV"] <= 3


# ------------------------------------------------------------
# Figure A: cycling trips to essential amenities within 3 km
# ------------------------------------------------------------

essential_3km = (
    bike_trips[bike_trips["is_essential"] & bike_trips["within_3km"]]
    .groupby(["Trip purpose", "Bike type (main mode)"], as_index=False)["Total Trips"]
    .sum()
)

pivot_essential_3km = essential_3km.pivot(
    index="Trip purpose",
    columns="Bike type (main mode)",
    values="Total Trips"
).fillna(0)

if not pivot_essential_3km.empty:
    pivot_essential_3km["Total"] = pivot_essential_3km.sum(axis=1)
    pivot_essential_3km = pivot_essential_3km.sort_values("Total", ascending=True)
    pivot_essential_3km = pivot_essential_3km.drop(columns="Total")

    plt.figure(figsize=(10, 6))
    pivot_essential_3km.plot(kind="barh", ax=plt.gca())
    plt.title("Cycling trips to essential amenities within 3 km")
    plt.xlabel("Total trips")
    plt.ylabel("Trip purpose")
    plt.legend(title="Bike type")
    save_fig("RQ1_cycling_to_essential_amenities_within_3km.png")
else:
    warnings.warn(
        "No essential trips within 3 km found. "
        "Check purpose labels and distance column."
    )


# ------------------------------------------------------------
# Figure B: share of essential cycling trips within 3 km
# ------------------------------------------------------------

essential_share = (
    bike_trips[bike_trips["is_essential"]]
    .groupby("Bike type (main mode)")
    .apply(lambda g: pd.Series({
        "Trips within 3 km": g.loc[g["within_3km"], "Total Trips"].sum(),
        "All essential trips": g["Total Trips"].sum()
    }))
    .reset_index()
)

essential_share["Share within 3 km"] = (
    essential_share["Trips within 3 km"] / essential_share["All essential trips"]
)

essential_share = essential_share.replace([np.inf, -np.inf], np.nan).dropna(
    subset=["Share within 3 km"]
)

if not essential_share.empty:
    plt.figure(figsize=(7, 5))
    plt.bar(
        essential_share["Bike type (main mode)"],
        essential_share["Share within 3 km"] * 100
    )
    plt.title("Share of essential cycling trips within 3 km")
    plt.ylabel("Share of essential trips within 3 km (%)")
    plt.xlabel("Bike type")

    upper = max(10, essential_share["Share within 3 km"].max() * 120)
    plt.ylim(0, min(100, upper))

    save_fig("RQ1_share_essential_cycling_trips_within_3km.png")


# ------------------------------------------------------------
# Figure C: bike/e-bike distance decay for essential purposes
# ------------------------------------------------------------

if "Dist" in bike_decay.columns:
    bike_decay["Dist"] = clean_numeric(bike_decay["Dist"])

    decay_cols = [
        "Bike_Work",
        "EBike_Work",
        "Bike_Edu",
        "EBike_Edu",
        "Bike_Shop",
        "EBike_Shop",
        "Bike_Shop_Gro",
        "EBike_Shop_Gro"
    ]

    available_decay_cols = [c for c in decay_cols if c in bike_decay.columns]

    for c in available_decay_cols:
        bike_decay[c] = clean_numeric(bike_decay[c])

    if available_decay_cols:
        plt.figure(figsize=(10, 6))

        for c in available_decay_cols:
            plt.plot(
                bike_decay["Dist"],
                bike_decay[c],
                marker="o",
                linewidth=1.5,
                label=c
            )

        plt.axvline(3, linestyle="--", linewidth=1)
        plt.text(3.05, 0.95, "3 km / 10-min bike-shed", va="top")
        plt.title("Bike and e-bike distance decay for essential trip purposes")
        plt.xlabel("Distance")
        plt.ylabel("Relative usage / willingness")
        plt.legend()
        save_fig("RQ1_bike_ebike_distance_decay_essential_purposes.png")


# ============================================================
# 5. KWB: build essential amenity access score
# ============================================================

print("\nInspecting potentially relevant CBS KWB columns...")
show_columns_like(kwb, ["Wijken", "Buurt", "Regio", "Soort", "Codering", "Naam"])
show_columns_like(kwb, ["inkomen", "laag", "hoog", "sociaal"])
show_columns_like(kwb, ["huisarts", "supermarkt", "school", "kinderdag", "station", "voorzien"])

region_code_col = find_col(
    kwb,
    [r"WijkenEnBuurten", r"Codering", r"RegioCode", r"RegioS", r"Key"]
)
region_name_col = find_col(
    kwb,
    [r"Title", r"Naam", r"RegioNaam", r"Gemeentenaam"]
)
region_type_col = find_col(
    kwb,
    [r"SoortRegio", r"RegioSoort", r"Soort"]
)

print("\nDetected region columns:")
print("  region_code_col:", region_code_col)
print("  region_name_col:", region_name_col)
print("  region_type_col:", region_type_col)

# Since we downloaded only BU rows, all rows should already be neighborhoods.
if region_type_col is not None:
    buurt = kwb[
        kwb[region_type_col].astype(str).str.contains("Buurt", case=False, na=False)
    ].copy()

    if buurt.empty:
        print("Region type filtering returned empty; using all downloaded rows instead.")
        buurt = kwb.copy()

elif region_code_col is not None:
    possible_buurt = kwb[
        kwb[region_code_col].astype(str).str.startswith("BU", na=False)
    ].copy()

    buurt = possible_buurt if not possible_buurt.empty else kwb.copy()

else:
    buurt = kwb.copy()

print("Buurt-level rows used:", buurt.shape)


amenity_candidates = {
    "GP distance": [
        r"huisarts",
        r"huisartsenpraktijk"
    ],
    "Supermarket distance": [
        r"supermarkt",
        r"grote.*supermarkt"
    ],
    "Childcare distance": [
        r"kinderdagverblijf",
        r"kinderopvang"
    ],
    "School distance": [
        r"afstand.*school",
        r"basisschool"
    ],
    "Schools within 3 km": [
        r"scholen.*3",
        r"3\s*km.*school"
    ],
    "Train station distance": [
        r"treinstation",
        r"station"
    ]
}

selected_amenity_cols = {}

for label, patterns in amenity_candidates.items():
    col = find_col(buurt, patterns)
    if col is not None:
        selected_amenity_cols[label] = col

print("\nSelected amenity columns:")
for label, col in selected_amenity_cols.items():
    print(f"  {label}: {col}")

if not selected_amenity_cols:
    raise ValueError(
        "No amenity columns found. Run the script once and inspect printed columns. "
        "Then update amenity_candidates patterns."
    )

for label, col in selected_amenity_cols.items():
    buurt[col] = clean_numeric(buurt[col])

access_indicator_cols = []

for label, col in selected_amenity_cols.items():
    new_col = "access_" + re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_")

    if "within" in label.lower() or "count" in label.lower() or "number" in label.lower():
        buurt[new_col] = (buurt[col] > 0).astype(float)
    else:
        buurt[new_col] = (buurt[col] <= 3).astype(float)

    buurt.loc[buurt[col].isna(), new_col] = np.nan
    access_indicator_cols.append(new_col)

buurt["essential_access_score"] = buurt[access_indicator_cols].mean(axis=1)

processed_buurt_path = CACHE_DIR / "processed_buurt_essential_access_scores.csv"
buurt.to_csv(processed_buurt_path, index=False)
print(f"\nSaved processed buurt access scores to: {processed_buurt_path}")


# ------------------------------------------------------------
# Figure D: distribution of essential amenity access score
# ------------------------------------------------------------

plt.figure(figsize=(8, 5))
plt.hist(buurt["essential_access_score"].dropna(), bins=20)
plt.title("Distribution of essential amenity access score by neighborhood")
plt.xlabel("Essential amenity access score, 0-1")
plt.ylabel("Number of neighborhoods")
save_fig("RQ1_distribution_essential_amenity_access_score.png")


# ============================================================
# 6. KWB: socioeconomic variable x essential accessibility
# ============================================================

socio_patterns = [
    r"gemiddeld.*inkomen",
    r"inkomen.*inwoner",
    r"inkomen.*huishouden",
    r"laag.*inkomen",
    r"sociaal.*minimum",
    r"armoede"
]

socio_col = find_col(buurt, socio_patterns)

print("\nSelected socioeconomic column:", socio_col)

if socio_col is not None:
    buurt[socio_col] = clean_numeric(buurt[socio_col])

    buurt_soc = buurt.dropna(subset=[socio_col, "essential_access_score"]).copy()

    if len(buurt_soc) > 20:
        buurt_soc["socioeconomic_decile"] = pd.qcut(
            buurt_soc[socio_col],
            q=10,
            labels=[f"D{i}" for i in range(1, 11)],
            duplicates="drop"
        )

        deciles = list(buurt_soc["socioeconomic_decile"].dropna().unique())
        deciles = sorted(deciles, key=lambda x: int(str(x).replace("D", "")))

        box_data = [
            buurt_soc.loc[
                buurt_soc["socioeconomic_decile"] == d,
                "essential_access_score"
            ].dropna()
            for d in deciles
        ]

        plt.figure(figsize=(10, 6))
        plt.boxplot(box_data, labels=deciles)
        plt.title("Essential amenity access score by socioeconomic decile")
        plt.xlabel(f"Decile based on: {socio_col}")
        plt.ylabel("Essential amenity access score, 0-1")
        save_fig("RQ2_socioeconomic_decile_vs_essential_access_score.png")

        plt.figure(figsize=(8, 6))
        plt.scatter(
            buurt_soc[socio_col],
            buurt_soc["essential_access_score"],
            alpha=0.35,
            s=12
        )
        plt.title("Socioeconomic status vs essential amenity access")
        plt.xlabel(socio_col)
        plt.ylabel("Essential amenity access score, 0-1")
        save_fig("RQ2_socioeconomic_status_vs_amenity_access_scatter.png")

    else:
        warnings.warn("Not enough rows with socioeconomic + access data for decile plots.")
else:
    warnings.warn(
        "No socioeconomic/income column was automatically found. "
        "Check the printed KWB income columns and manually set socio_col."
    )


# ============================================================
# 7. Municipality-level policy score
# ============================================================

if region_code_col is not None and region_code_col in buurt.columns:
    buurt["_region_code_clean"] = buurt[region_code_col].astype(str)

    buurt["gemeente_code_4digit"] = (
        buurt["_region_code_clean"]
        .str.replace("BU", "", regex=False)
        .str.replace("WK", "", regex=False)
        .str.replace("GM", "", regex=False)
        .str.extract(r"(\d{4})")[0]
    )
else:
    if "WijkenEnBuurten" in buurt.columns:
        buurt["_region_code_clean"] = buurt["WijkenEnBuurten"].astype(str)
        buurt["gemeente_code_4digit"] = (
            buurt["_region_code_clean"]
            .str.replace("BU", "", regex=False)
            .str.extract(r"(\d{4})")[0]
        )
    elif "RegioS" in buurt.columns:
        buurt["_region_code_clean"] = buurt["RegioS"].astype(str)
        buurt["gemeente_code_4digit"] = (
            buurt["_region_code_clean"]
            .str.replace("BU", "", regex=False)
            .str.extract(r"(\d{4})")[0]
        )
    else:
        buurt["gemeente_code_4digit"] = np.nan

municipality_name_col = None

if GEM_FILE.exists():
    gem = pd.read_csv(GEM_FILE, sep=";", dtype=str)

    gem_code_col = find_col(gem, [r"Gemeente2025", r"Gemeente", r"GM"])
    gem_name_col = find_col(gem, [r"Gemeentenaam2025", r"Gemeentenaam", r"naam"])

    if gem_code_col is not None and gem_name_col is not None:
        gem[gem_code_col] = (
            gem[gem_code_col]
            .astype(str)
            .str.replace("GM", "", regex=False)
            .str.extract(r"(\d{4})")[0]
        )

        buurt = buurt.merge(
            gem[[gem_code_col, gem_name_col]],
            left_on="gemeente_code_4digit",
            right_on=gem_code_col,
            how="left"
        )

        municipality_name_col = gem_name_col
    else:
        warnings.warn("Could not detect code/name columns in gem_2025.csv.")
else:
    warnings.warn(f"Municipality lookup file not found: {GEM_FILE}")

if municipality_name_col is None:
    municipality_name_col = region_name_col

if municipality_name_col is not None and municipality_name_col in buurt.columns:
    municipal_access = (
        buurt
        .dropna(subset=["essential_access_score"])
        .groupby(municipality_name_col, as_index=False)["essential_access_score"]
        .mean()
        .sort_values("essential_access_score", ascending=False)
    )

    municipality_scores_path = CACHE_DIR / "municipality_essential_access_scores.csv"
    municipal_access.to_csv(municipality_scores_path, index=False)
    print(f"\nSaved municipality scores to: {municipality_scores_path}")

    top10 = municipal_access.head(10)
    bottom10 = municipal_access.tail(10)

    policy_rank = pd.concat([bottom10, top10], axis=0)

    plt.figure(figsize=(10, 8))
    plt.barh(
        policy_rank[municipality_name_col],
        policy_rank["essential_access_score"]
    )
    plt.title("Top and bottom municipalities by essential amenity access score")
    plt.xlabel("Mean essential amenity access score, 0-1")
    plt.ylabel("Municipality")
    save_fig("Policy_top_bottom_municipalities_essential_access_score.png")

else:
    warnings.warn("Could not identify municipality names for policy ranking.")


print("\nDone. Figures saved in:")
print(OUT_DIR)

print("\nCached/processed data saved in:")
print(CACHE_DIR)