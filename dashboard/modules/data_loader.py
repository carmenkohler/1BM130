from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

try:
    import streamlit as st
except ModuleNotFoundError:  # Allows data preparation tests before Streamlit is installed.
    class _CacheShim:
        @staticmethod
        def cache_data(*args, **kwargs):
            return lambda func: func

        @staticmethod
        def cache_resource(*args, **kwargs):
            return lambda func: func

    st = _CacheShim()


DASHBOARD_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = DASHBOARD_DIR.parent
WORKSPACE_DIR = REPO_DIR.parents[1]

RAW_DATA_DIR = WORKSPACE_DIR / "data"
OUTPUTS_DIR = REPO_DIR / "outputs"
LOCAL_DATA_DIR = DASHBOARD_DIR / "data"

NEIGHBORHOOD_CSV = LOCAL_DATA_DIR / "neighborhood_data.csv"
SCENARIO_TRIPS_CSV = LOCAL_DATA_DIR / "scenario_trips.csv"
GEOPACKAGE_PATH = RAW_DATA_DIR / "wijkenbuurten_2024_v2.gpkg"
KWB2024_PATH = RAW_DATA_DIR / "kwb2024.xlsx"
ODIN2024_PATH = RAW_DATA_DIR / "ODiN2024 Updated with Header" / "ODiN2024_DANS_Databestand_ Updated.xlsx"
PC4_DOMINANT_BUURT_PATH = OUTPUTS_DIR / "pc4_dominant_buurt.csv"
MODEL_PATHS = [
    LOCAL_DATA_DIR / "xgb_model.pkl",
    LOCAL_DATA_DIR / "xgb_mode_choice_pipeline.pkl",
]
METADATA_PATH = LOCAL_DATA_DIR / "mode_choice_metadata.json"

AMENITY_COLUMNS = [
    "bike10_klasse_supermarkt",
    "bike10_klasse_huisarts",
    "bike10_klasse_basisschool",
    "bike10_klasse_ziekenhuis",
    "bike10_klasse_apotheek",
    "bike10_klasse_bushalte",
    "bike10_klasse_treinstation",
    "bike10_klasse_voortgezet_onderwijs",
    "bike10_klasse_kinderopvang",
    "bike10_klasse_horeca",
    "bike10_klasse_restaurant",
    "bike10_klasse_sportterrein",
    "bike10_klasse_fastfood",
    "bike10_klasse_kledingwinkel",
]

CORE_ACCESS_COLUMNS = [
    "bike10_klasse_supermarkt",
    "bike10_klasse_huisarts",
    "bike10_klasse_basisschool",
    "bike10_klasse_voortgezet_onderwijs",
    "bike10_klasse_ziekenhuis",
]

AMENITY_LABELS = {
    "bike10_klasse_supermarkt": "Supermarket",
    "bike10_klasse_huisarts": "GP / doctor",
    "bike10_klasse_basisschool": "Primary school",
    "bike10_klasse_ziekenhuis": "Hospital",
    "bike10_klasse_apotheek": "Pharmacy",
    "bike10_klasse_bushalte": "Bus stop",
    "bike10_klasse_treinstation": "Train station",
    "bike10_klasse_voortgezet_onderwijs": "Secondary school",
    "bike10_klasse_kinderopvang": "Childcare",
    "bike10_klasse_horeca": "Cafes and bars",
    "bike10_klasse_restaurant": "Restaurant",
    "bike10_klasse_sportterrein": "Sports facility",
    "bike10_klasse_fastfood": "Fast food",
    "bike10_klasse_kledingwinkel": "Clothing shop",
}

ACCESS_METHOD_NOTE = (
    "Access follows the Topic 1 weighted bike-access score: neighborhoods score higher when more useful "
    "destinations are reachable by bike, with higher weight for daily essentials such as supermarkets, GP "
    "practices and schools. MBO and HBO/WO are not available in the current destination file, so "
    "higher-education access is a data gap."
)

USAGE_METHOD_NOTE = (
    "Cycling share comes from the national travel survey and is available at municipality level. "
    "Use the gap as a first signal for discussion, not as a final ranking."
)


def _clean_code(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text.upper().startswith("BU"):
        text = text[2:]
    return text.zfill(8)


def _amenity_to_numeric(value: Any) -> float:
    if pd.isna(value):
        return np.nan
    text = str(value).strip()
    if text.endswith("+"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return np.nan


def _income_decile(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    out = pd.Series(np.nan, index=series.index)
    valid = numeric.dropna()
    if valid.empty:
        return out
    try:
        out.loc[valid.index] = pd.qcut(valid, 10, labels=False, duplicates="drop") + 1
    except ValueError:
        out.loc[valid.index] = pd.qcut(valid.rank(method="first"), 10, labels=False, duplicates="drop") + 1
    return out


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", ".", regex=False), errors="coerce")


def _pattern_labels(df: pd.DataFrame) -> pd.Series:
    access_median = df["bike10_weighted_score"].median()
    usage_median = df["pct_bike"].median()
    high_access = df["bike10_weighted_score"] >= access_median
    high_usage = df["pct_bike"] >= usage_median

    labels = np.select(
        [
            high_access & high_usage,
            high_access & ~high_usage,
            ~high_access & high_usage,
            ~high_access & ~high_usage,
        ],
        [
            "Strong access and cycling",
            "Good access, low cycling",
            "Low access, high cycling",
            "Low access and cycling",
        ],
        default="Unknown",
    )
    return pd.Series(labels, index=df.index)


def _class_access_score(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    values = df[columns].fillna(0).clip(lower=0, upper=2) / 2
    return (values.mean(axis=1) * 100).round(1)


def _coverage_access_score(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    return (df[columns].fillna(0).gt(0).mean(axis=1) * 100).round(1)


def _topic1_weighted_access_score(df: pd.DataFrame) -> pd.Series:
    weights = {
        "bike10_klasse_supermarkt": 0.18,
        "bike10_klasse_huisarts": 0.14,
        "bike10_klasse_basisschool": 0.13,
        "bike10_klasse_ziekenhuis": 0.10,
        "bike10_klasse_apotheek": 0.07,
        "bike10_klasse_voortgezet_onderwijs": 0.07,
        "bike10_klasse_bushalte": 0.06,
        "bike10_klasse_treinstation": 0.05,
        "bike10_klasse_kinderopvang": 0.03,
        "bike10_klasse_horeca": 0.05,
        "bike10_klasse_restaurant": 0.04,
        "bike10_klasse_sportterrein": 0.04,
        "bike10_klasse_fastfood": 0.02,
        "bike10_klasse_kledingwinkel": 0.02,
    }
    score = pd.Series(0.0, index=df.index)
    active = []
    for col, weight in weights.items():
        if col not in df.columns:
            continue
        values = pd.to_numeric(df[col], errors="coerce").fillna(0)
        if values.nunique(dropna=True) <= 1:
            continue
        active.append((values, weight))

    total_weight = sum(weight for _, weight in active)
    if total_weight == 0:
        return score

    for values, weight in active:
        score += values.rank(pct=True) * 100 * (weight / total_weight)
    return score.round(1)


def _build_neighborhood_data() -> pd.DataFrame:
    buurt = pd.read_csv(OUTPUTS_DIR / "buurt_master.csv")
    gemeente = pd.read_csv(OUTPUTS_DIR / "gemeente_odin_2024.csv")
    amenities = pd.read_csv(RAW_DATA_DIR / "voorzieningen_per_buurt_klasse.csv")

    amenities = amenities.rename(columns={amenities.columns[0]: "buurtcode"})
    amenities["buurtcode_clean"] = amenities["buurtcode"].map(_clean_code)

    rename_map = {
        col: f"bike10_{col}"
        for col in amenities.columns
        if col.startswith("klasse_")
    }
    amenities = amenities.rename(columns=rename_map)
    for col in AMENITY_COLUMNS:
        if col in amenities.columns:
            amenities[col] = amenities[col].map(_amenity_to_numeric)

    df = buurt.merge(
        amenities[["buurtcode_clean"] + [c for c in AMENITY_COLUMNS if c in amenities.columns]],
        left_on="gwb_code_8",
        right_on="buurtcode_clean",
        how="left",
    )

    df = df.merge(
        gemeente[["gm_code", "bike_share_pct", "local_trip_share_pct", "weighted_trips"]],
        on="gm_code",
        how="left",
    )

    for col in AMENITY_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan

    df["bike10_weighted_score"] = _topic1_weighted_access_score(df)
    df["bike10_core_score"] = df["bike10_weighted_score"]
    df["bike10_policy_score"] = _coverage_access_score(df, AMENITY_COLUMNS)
    df["bike10_intensity_score"] = _class_access_score(df, CORE_ACCESS_COLUMNS)
    df["bike10_coverage_score"] = _coverage_access_score(df, CORE_ACCESS_COLUMNS)
    df["bike10_score"] = df["bike10_policy_score"]

    df["buurtcode"] = df["Buurt2025"].map(_clean_code)
    df["buurtnaam"] = df["buurtnaam2025"]
    df["gemeentenaam"] = df["Gemeentenaam2025"].fillna(df["gm_naam"])
    df["Sted"] = pd.to_numeric(df["ste_mvs"], errors="coerce")
    df["HHGestInkG"] = _income_decile(df["g_ink_pi"])
    df["pct_bike"] = pd.to_numeric(df["bike_share_pct"], errors="coerce")
    df["pct_within_3km"] = pd.to_numeric(df["local_trip_share_pct"], errors="coerce")
    df["access_usage_gap"] = (df["bike10_weighted_score"] - df["pct_bike"]).round(1)
    df["access_scale"] = "Topic 1 weighted neighborhood bike-access score"
    df["bike_share_scale"] = "municipality travel-survey cycling share"
    df["gap_scale"] = "neighborhood access / municipality cycling usage"

    keep = [
        "buurtcode",
        "buurtnaam",
        "gemeentenaam",
        "gm_code",
        "Sted",
        "HHGestInkG",
        "a_inw",
        "bev_dich",
        "g_ink_pi",
        "bike10_core_score",
        "bike10_policy_score",
        "bike10_intensity_score",
        "bike10_coverage_score",
        "bike10_weighted_score",
        "bike10_score",
        "pct_bike",
        "pct_within_3km",
        "access_usage_gap",
        "access_scale",
        "bike_share_scale",
        "gap_scale",
        "weighted_trips",
    ] + AMENITY_COLUMNS
    df = df[keep].copy()
    df = df[df["a_inw"].fillna(0) >= 200].reset_index(drop=True)
    df["pattern_label"] = _pattern_labels(df)

    df = _enrich_income_from_kwb2024(df)
    LOCAL_DATA_DIR.mkdir(exist_ok=True)
    df.to_csv(NEIGHBORHOOD_CSV, index=False)
    return df


def _enrich_income_from_kwb2024(df: pd.DataFrame) -> pd.DataFrame:
    if not KWB2024_PATH.exists():
        return df

    income = pd.read_excel(
        KWB2024_PATH,
        sheet_name="KWB2024",
        usecols=["gwb_code_8", "g_ink_pi"],
    )
    income["buurtcode"] = income["gwb_code_8"].map(_clean_code)
    income["g_ink_pi_2024"] = _to_numeric(income["g_ink_pi"])
    income = income[["buurtcode", "g_ink_pi_2024"]].drop_duplicates("buurtcode")

    enriched = df.merge(income, on="buurtcode", how="left")
    enriched["g_ink_pi"] = pd.to_numeric(enriched.get("g_ink_pi"), errors="coerce")
    enriched["g_ink_pi"] = enriched["g_ink_pi"].fillna(enriched["g_ink_pi_2024"])
    enriched["HHGestInkG"] = _income_decile(enriched["g_ink_pi"])
    return enriched.drop(columns=["g_ink_pi_2024"])


def load_neighborhood_data() -> pd.DataFrame:
    if NEIGHBORHOOD_CSV.exists():
        df = pd.read_csv(NEIGHBORHOOD_CSV)
        required = {
            "bike10_core_score",
            "bike10_policy_score",
            "bike10_intensity_score",
            "bike10_coverage_score",
            "access_scale",
            "bike_share_scale",
            "gap_scale",
        }
        if not required.issubset(df.columns):
            return _build_neighborhood_data()
        if "HHGestInkG" in df.columns and not df["HHGestInkG"].notna().any():
            df = _enrich_income_from_kwb2024(df)
            df.to_csv(NEIGHBORHOOD_CSV, index=False)
        return df
    return _build_neighborhood_data()


@st.cache_resource(show_spinner=False)
def load_model() -> tuple[Any | None, dict[str, Any]]:
    metadata: dict[str, Any] = {}
    if METADATA_PATH.exists():
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

    for path in MODEL_PATHS:
        if path.exists():
            return joblib.load(path), metadata
    return None, metadata


def get_neighborhood_options(df: pd.DataFrame) -> list[str]:
    options = df[["buurtcode", "buurtnaam", "gemeentenaam"]].dropna(subset=["buurtcode"])
    labels = options.apply(
        lambda r: f"{r['buurtnaam']} ({r['gemeentenaam']}) - {r['buurtcode']}",
        axis=1,
    )
    return labels.tolist()


def parse_buurtcode(label: str) -> str:
    return label.rsplit("-", 1)[-1].strip()


def _clean_pc4(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    text = "".join(ch for ch in text if ch.isdigit())
    return text.zfill(4) if text else None


def _build_scenario_trips(feature_columns: list[str]) -> pd.DataFrame:
    if not ODIN2024_PATH.exists() or not PC4_DOMINANT_BUURT_PATH.exists():
        return pd.DataFrame()

    needed = set(feature_columns) | {
        "AfstV",
        "VertPC_PRAM",
        "VertGem_DANS24",
        "KHvm",
        "FactorV",
    }
    derived = {
        "dist_km",
        "log_dist_km",
        "bev_dich",
        "pattern_label",
        "bike10_klasse_treinstation",
        "access_usage_gap",
        "a_inw",
        "bike10_klasse_bushalte",
        "bike10_klasse_supermarkt",
    }
    read_cols = [col for col in needed if col not in derived]
    odin = pd.read_excel(ODIN2024_PATH, usecols=lambda col: col in read_cols)
    odin = odin[pd.to_numeric(odin["KHvm"], errors="coerce").between(1, 6, inclusive="both")].copy()
    odin["dist_km"] = pd.to_numeric(odin["AfstV"], errors="coerce") / 10
    odin["log_dist_km"] = np.log1p(odin["dist_km"].clip(lower=0))
    odin["pc4"] = odin["VertPC_PRAM"].map(_clean_pc4)
    odin["gm_code"] = "GM" + pd.to_numeric(odin["VertGem_DANS24"], errors="coerce").astype("Int64").astype(str).str.zfill(4)

    pc4 = pd.read_csv(PC4_DOMINANT_BUURT_PATH, dtype={"pc4": "string", "buurt_key": "string"})
    pc4["pc4"] = pc4["pc4"].map(_clean_pc4)
    pc4 = pc4.rename(columns={"buurt_key": "buurtcode"})
    odin = odin.merge(pc4[["pc4", "buurtcode"]], on="pc4", how="left")

    neighborhood_cols = [
        "buurtcode",
        "gemeentenaam",
        "bev_dich",
        "pattern_label",
        "bike10_klasse_treinstation",
        "access_usage_gap",
        "a_inw",
        "bike10_klasse_bushalte",
        "bike10_klasse_supermarkt",
    ]
    neighborhoods = load_neighborhood_data()[neighborhood_cols].drop_duplicates("buurtcode")
    odin = odin.merge(neighborhoods, on="buurtcode", how="left")

    keep = ["buurtcode", "gm_code", "gemeentenaam", "FactorV"] + feature_columns
    for col in keep:
        if col not in odin.columns:
            odin[col] = np.nan
    scenario_trips = odin[keep].dropna(subset=["dist_km"]).copy()
    LOCAL_DATA_DIR.mkdir(exist_ok=True)
    scenario_trips.to_csv(SCENARIO_TRIPS_CSV, index=False)
    return scenario_trips


@st.cache_data(show_spinner=False)
def load_scenario_trips(feature_columns: list[str]) -> pd.DataFrame:
    if SCENARIO_TRIPS_CSV.exists():
        return pd.read_csv(SCENARIO_TRIPS_CSV, dtype={"buurtcode": "string", "gm_code": "string"})
    return _build_scenario_trips(feature_columns)


@st.cache_data(show_spinner=False)
def load_buurt_centroids() -> pd.DataFrame:
    import geopandas as gpd

    gdf = gpd.read_file(
        GEOPACKAGE_PATH,
        layer="buurten",
        columns=["buurtcode", "buurtnaam", "gemeentenaam", "water", "geometry"],
    )
    if "water" in gdf.columns:
        gdf = gdf[gdf["water"].fillna("NEE").eq("NEE")]
    gdf["buurtcode_clean"] = gdf["buurtcode"].map(_clean_code)
    centroids = gdf.geometry.centroid.to_crs(4326)
    return pd.DataFrame(
        {
            "buurtcode": gdf["buurtcode_clean"].values,
            "lat": centroids.y.values,
            "lon": centroids.x.values,
        }
    )


@st.cache_data(show_spinner=False)
def load_buurt_geometries(gemeentenaam: str) -> Any:
    import geopandas as gpd

    gdf = gpd.read_file(
        GEOPACKAGE_PATH,
        layer="buurten",
        columns=["buurtcode", "buurtnaam", "gemeentenaam", "water", "geometry"],
    )
    if "water" in gdf.columns:
        gdf = gdf[gdf["water"].fillna("NEE").eq("NEE")]
    gdf = gdf[gdf["gemeentenaam"].eq(gemeentenaam)].copy()
    gdf["buurtcode"] = gdf["buurtcode"].map(_clean_code)
    return gdf[["buurtcode", "geometry"]].to_crs(4326)
