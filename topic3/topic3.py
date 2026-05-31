# ============================================================
# Topic 3 - Urban Policy Dashboard
# Low-income focused + combined neighbourhood dataset version
#
# Main changes in this version:
# 1. Uses combined_neighbourhood_dataset.csv as the main Topic 3 dataset.
#    This file is expected in datasets/.
#
# 2. Low-income information is pulled directly from the combined
#    neighbourhood dataset using p_ink_li.
#
# 3. Original graphs and scenario-updated graphs are kept separate.
#    The normal graph explorer shows the original data.
#    The What-if Scenario section shows updated graph views below
#    the updated Bike-10 access score.
#
# 4. Amenity scoring is consistent:
#    bike10_klasse_* variables are scored as:
#    0 = 0, 1 = 70, 2+ = 100.
#    This avoids treating school-count variables differently from
#    other amenity-class indicators.
#
# 5. Feature 1 is integrated:
#    - Access-Usage Heatmap
#    - 3 km bike-shed map for selected neighbourhood
#
# 6. Municipality and neighbourhood boundaries are downloaded automatically from
#    PDOK/CBS WFS if folium + streamlit-folium are installed.
#
# 7. Neighbourhood bike-shed matching is improved:
#    - first tries buurt code matching
#    - then municipality + neighbourhood name matching
#    - then cautious name-only matching
#    - otherwise falls back to municipality centre with a warning
#
# Required local datasets inside datasets/:
# - combined_neighbourhood_dataset.csv
#
# Optional:
# - Bike_Trip purpose.xlsx
#
# Install:
# python3 -m pip install streamlit plotly pandas numpy openpyxl requests folium streamlit-folium google-genai
#
# Run:
# streamlit run topic3_dashboard_final.py
# ============================================================

from pathlib import Path
import re
import json
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import requests
import streamlit as st
import plotly.express as px

px.defaults.template = "plotly_white"

try:
    from google import genai
except Exception:
    genai = None

try:
    import folium
    from streamlit_folium import st_folium
except Exception:
    folium = None
    st_folium = None


# ============================================================
# 0. App setup
# ============================================================

st.set_page_config(
    page_title="10-Minute Cycling City Dashboard - Low Income Focus",
    layout="wide"
)

WORKSPACE = Path(__file__).resolve().parent
DATASETS_DIR = WORKSPACE / "datasets"
CACHE_DIR = WORKSPACE / "data_cache" / "topic3"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Paste your Gemini API key here.
GEMINI_API_KEY = ""

PDOK_CBS_2025_WFS = "https://service.pdok.nl/cbs/gebiedsindelingen/2025/wfs/v1_0"


# ============================================================
# 1. Styling
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --ink: #0f172a;
        --muted: #64748b;
        --blue: #2563eb;
        --cyan: #06b6d4;
        --green: #10b981;
        --amber: #f59e0b;
        --red: #ef4444;
        --soft: rgba(255,255,255,.78);
        --border: rgba(148, 163, 184, .28);
    }

    div[data-testid="stAppViewContainer"] {
        background:
          radial-gradient(circle at top left, rgba(37,99,235,.16), transparent 28%),
          radial-gradient(circle at top right, rgba(20,184,166,.15), transparent 28%),
          linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
    }

    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1320px;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
    }

    section[data-testid="stSidebar"] * {
        color: #e5e7eb !important;
    }

    section[data-testid="stSidebar"] div[data-baseweb="select"] * {
        color: #111827 !important;
    }

    .hero {
        padding: 1.55rem 1.75rem;
        border-radius: 28px;
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 55%, #14b8a6 100%);
        color: white;
        box-shadow: 0 22px 55px rgba(15, 23, 42, .18);
        margin-bottom: 1.2rem;
    }

    .hero h1 {
        margin: 0;
        font-size: 2.2rem;
        letter-spacing: -.04em;
        color: white;
    }

    .hero p {
        margin: .55rem 0 0 0;
        color: rgba(255,255,255,.88);
        max-width: 980px;
        font-size: 1rem;
    }

    .bubble {
        min-height: 154px;
        border-radius: 999px;
        padding: 1.1rem 1.35rem;
        background: rgba(255,255,255,.82);
        border: 1px solid rgba(148,163,184,.28);
        box-shadow: 0 16px 35px rgba(15,23,42,.08);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
    }

    .bubble-ok {
        border: 1px solid rgba(16,185,129,.38);
    }

    .bubble-warn {
        border: 1px solid rgba(245,158,11,.45);
    }

    .bubble h3 {
        margin: 0;
        color: #0f172a;
        font-size: 1.05rem;
    }

    .bubble p {
        margin: .35rem 0 0 0;
        color: #475569;
        font-size: .86rem;
    }

    .small-pill {
        display: inline-block;
        margin-bottom: .45rem;
        padding: .2rem .55rem;
        border-radius: 999px;
        font-size: .72rem;
        font-weight: 700;
        background: #dbeafe;
        color: #1e40af;
    }

    .section-card {
        border-radius: 24px;
        padding: 1.05rem 1.2rem;
        background: rgba(255,255,255,.82);
        border: 1px solid rgba(148,163,184,.28);
        box-shadow: 0 14px 30px rgba(15,23,42,.07);
        margin: .65rem 0 1rem 0;
    }

    div[data-testid="metric-container"] {
        background: rgba(255,255,255,.82);
        border: 1px solid rgba(148,163,184,.28);
        padding: 1rem;
        border-radius: 20px;
        box-shadow: 0 10px 26px rgba(15,23,42,.06);
    }

    .hint {
        padding: .85rem 1rem;
        border-radius: 18px;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1e3a8a;
        margin: .5rem 0;
    }

    .bad {
        padding: .85rem 1rem;
        border-radius: 18px;
        background: #fef2f2;
        border: 1px solid #fecaca;
        color: #991b1b;
        margin: .5rem 0;
    }

    .metric-note {
        font-size: .82rem;
        color: #64748b;
        margin-top: -.5rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# 2. Helper functions
# ============================================================

def clean_numeric(series):
    return (
        series.astype(str)
        .str.replace(",", ".", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace(" ", "", regex=False)
        .replace({
            ".": np.nan,
            "nan": np.nan,
            "None": np.nan,
            "": np.nan,
            "x": np.nan,
            "X": np.nan,
            "-": np.nan
        })
        .pipe(pd.to_numeric, errors="coerce")
    )


def file_mtime(path: Path):
    try:
        return path.stat().st_mtime
    except Exception:
        return 0


def find_dataset_file(patterns):
    if not DATASETS_DIR.exists():
        return None

    files = [p for p in DATASETS_DIR.rglob("*") if p.is_file()]

    for pattern in patterns:
        rx = re.compile(pattern, re.IGNORECASE)
        matches = [p for p in files if rx.search(p.name)]
        if matches:
            return sorted(matches, key=lambda p: len(str(p)))[0]

    return None


def list_excel_sheets(path: Path):
    try:
        return pd.ExcelFile(path).sheet_names
    except Exception:
        return []


def pick_sheet(path: Path, preferred):
    if path is None or path.suffix.lower() not in [".xlsx", ".xls"]:
        return None

    sheets = list_excel_sheets(path)

    if preferred in sheets:
        return preferred

    return sheets[0] if sheets else None


def fmt_pct(value):
    if pd.isna(value):
        return "No data"
    return f"{float(value):.1f}%"


def normalize_text(x):
    if pd.isna(x):
        return ""

    x = str(x).lower().strip()
    x = re.sub(r"\s+", " ", x)

    return x


def normalise_buurt_code(x):
    """
    Normalise Dutch buurt codes to BU######## when possible.
    This helps prevent false map matches when neighbourhood names repeat.
    """
    if pd.isna(x):
        return ""

    x = str(x).strip().upper()

    if x.startswith("BU"):
        nums = re.sub(r"\D", "", x)
        if nums:
            return "BU" + nums.zfill(8)
        return x

    nums = re.sub(r"\D", "", x)

    if len(nums) >= 8:
        return "BU" + nums[-8:]

    return x


def urbanisation_code_explanation():
    return (
        "Urbanisation code: 1 = very strongly urban, 2 = strongly urban, "
        "3 = moderately urban, 4 = slightly urban, 5 = not urban / rural."
    )


def classify_policy_case(access_score, usage_score=None):
    if pd.isna(access_score):
        return "insufficient data"

    if usage_score is not None and not pd.isna(usage_score):
        if access_score >= 70 and usage_score >= 60:
            return "environmental success"
        if access_score >= 70 and usage_score < 60:
            return "policy opportunity"
        if access_score < 70 and usage_score >= 60:
            return "cycling demand / access gap"
        return "low access / low usage"

    if access_score >= 75:
        return "strong access"
    if access_score >= 50:
        return "moderate access"

    return "low access"


def recommendation_from_case(case):
    if case == "environmental success":
        return "High access and high local usage. Maintain access quality and protect cycling conditions."

    if case == "policy opportunity":
        return "Good access but lower local usage. Focus on cycling safety, route directness, comfort, parking, and behaviour barriers."

    if case == "cycling demand / access gap":
        return "Cycling use exists despite weaker access. Adding amenities or improving direct routes may have strong benefit."

    if case == "low access / low usage":
        return "Both access and usage are weak. Combine spatial planning with cycling infrastructure improvements."

    if case == "strong access":
        return "Access is relatively strong. Policy attention should focus on whether low-income residents actually use active modes and whether routes feel safe and direct."

    if case == "moderate access":
        return "Access is mixed. Target missing amenities and improve route directness toward the weakest essential functions."

    if case == "low access":
        return "Access is weak. Prioritise direct cycling links to essential services and consider adding missing daily amenities in underserved neighbourhoods."

    return "More data is needed before making a targeted recommendation."


def ask_gemini(prompt):
    api_key = GEMINI_API_KEY.strip()

    if not api_key or genai is None:
        return None

    client = genai.Client(api_key=api_key)

    for model_name in [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-3.1-flash-lite"
    ]:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text
        except Exception:
            continue

    return None


def fallback_policy_answer(context_text, user_question):
    return f"""
**Interpretation**  
{context_text}

**Answer to your question**  
For: "{user_question}", first decide whether the selected area has an access problem, a usage/infrastructure problem, or both.

**Recommended policy action**  
If access is weak, improve connections to supermarkets, GP/doctor services, schools, healthcare, and childcare. If access is already strong, focus on cycling safety, route directness, parking, affordability, and barriers that may prevent low-income residents from choosing active mobility.
"""


def recursive_coords(geom):
    coords = []

    def walk(obj):
        if isinstance(obj, list):
            if (
                len(obj) >= 2
                and isinstance(obj[0], (int, float))
                and isinstance(obj[1], (int, float))
            ):
                coords.append((float(obj[0]), float(obj[1])))
            else:
                for item in obj:
                    walk(item)

    if geom and "coordinates" in geom:
        walk(geom["coordinates"])

    return coords


def centroid_from_geojson_geometry(geom):
    coords = recursive_coords(geom)

    if not coords:
        return None

    lon = float(np.mean([c[0] for c in coords]))
    lat = float(np.mean([c[1] for c in coords]))

    return lat, lon


# ============================================================
# 3. Automatic CBS boundary download
# ============================================================

def detect_wfs_layer(kind="gemeente"):
    try:
        params = {
            "service": "WFS",
            "request": "GetCapabilities"
        }

        r = requests.get(PDOK_CBS_2025_WFS, params=params, timeout=60)
        r.raise_for_status()

        root = ET.fromstring(r.content)

        names = []

        for elem in root.iter():
            tag = elem.tag.lower()

            if tag.endswith("name") and elem.text:
                txt = elem.text.strip()

                if ":" in txt or kind.lower() in txt.lower():
                    names.append(txt)

        kind = kind.lower()
        candidates = [n for n in names if kind in n.lower()]

        generalized = [n for n in candidates if "gegeneraliseerd" in n.lower()]

        if generalized:
            return generalized[0]

        if candidates:
            return candidates[0]

    except Exception:
        return None

    return None


@st.cache_data(show_spinner=False)
def download_cbs_boundary_geojson(kind, cache_key):
    cache_file = CACHE_DIR / f"cbs_gebiedsindelingen_2025_{kind}.geojson"

    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    layer_name = detect_wfs_layer(kind=kind)

    if layer_name is None:
        return None

    for version, type_param in [
        ("2.0.0", "typeNames"),
        ("1.1.0", "typeName")
    ]:
        try:
            params = {
                "service": "WFS",
                "version": version,
                "request": "GetFeature",
                type_param: layer_name,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326"
            }

            r = requests.get(PDOK_CBS_2025_WFS, params=params, timeout=180)
            r.raise_for_status()

            data = r.json()

            if "features" in data and len(data["features"]) > 0:
                cache_file.write_text(json.dumps(data), encoding="utf-8")
                return data

        except Exception:
            continue

    return None


def find_geojson_name_property(feature, target_type="municipality"):
    props = feature.get("properties", {})
    keys = list(props.keys())

    if target_type == "municipality":
        patterns = [
            r"gemeentenaam",
            r"gemeente_naam",
            r"gm_naam",
            r"statnaam",
            r"naam",
            r"name"
        ]
    else:
        patterns = [
            r"buurtnaam",
            r"buurt_naam",
            r"regio",
            r"statnaam",
            r"naam",
            r"name"
        ]

    for pat in patterns:
        rx = re.compile(pat, re.IGNORECASE)
        matches = [k for k in keys if rx.search(str(k))]

        if matches:
            return matches[0]

    return keys[0] if keys else None


def find_geojson_code_property(feature):
    props = feature.get("properties", {})
    keys = list(props.keys())

    patterns = [
        r"statcode",
        r"buurtcode",
        r"bu_code",
        r"code",
        r"regio",
        r"id"
    ]

    for pat in patterns:
        rx = re.compile(pat, re.IGNORECASE)
        matches = [k for k in keys if rx.search(str(k))]
        if matches:
            return matches[0]

    return None


def find_geojson_municipality_property(feature):
    props = feature.get("properties", {})
    keys = list(props.keys())

    patterns = [
        r"gemeentenaam",
        r"gemeente_naam",
        r"gm_naam",
        r"gemeente",
        r"municipality"
    ]

    for pat in patterns:
        rx = re.compile(pat, re.IGNORECASE)
        matches = [k for k in keys if rx.search(str(k))]
        if matches:
            return matches[0]

    return None


def prepare_municipality_geojson(raw_geojson, municipality_names):
    if raw_geojson is None:
        return None

    names_set = set(normalize_text(x) for x in municipality_names)

    out = json.loads(json.dumps(raw_geojson))

    for feat in out.get("features", []):
        prop_name = find_geojson_name_property(feat, "municipality")
        props = feat.setdefault("properties", {})

        raw_name = props.get(prop_name, "") if prop_name else ""
        norm = normalize_text(raw_name)

        dash_name = raw_name

        if norm not in names_set:
            for m in municipality_names:
                if normalize_text(m) == norm or normalize_text(m) in norm or norm in normalize_text(m):
                    dash_name = m
                    break

        props["_dash_name"] = str(dash_name)

    return out


def prepare_buurt_geojson(raw_geojson):
    if raw_geojson is None:
        return None

    out = json.loads(json.dumps(raw_geojson))

    for feat in out.get("features", []):
        prop_name = find_geojson_name_property(feat, "buurt")
        code_prop = find_geojson_code_property(feat)
        muni_prop = find_geojson_municipality_property(feat)

        props = feat.setdefault("properties", {})

        raw_name = props.get(prop_name, "") if prop_name else ""
        raw_code = props.get(code_prop, "") if code_prop else ""
        raw_muni = props.get(muni_prop, "") if muni_prop else ""

        props["_dash_buurt_name"] = str(raw_name)
        props["_dash_buurt_code"] = normalise_buurt_code(raw_code)
        props["_dash_muni_name"] = str(raw_muni)

    return out


def render_municipality_map(muni_geojson, selected_muni):
    if muni_geojson is None:
        st.sidebar.warning("Could not download municipality boundaries. Using dropdown fallback.")
        return None

    if folium is None or st_folium is None:
        st.sidebar.warning("Install folium and streamlit-folium for map selection. Using dropdown fallback.")
        st.sidebar.code("python3 -m pip install folium streamlit-folium")
        return None

    m = folium.Map(
        location=[52.15, 5.35],
        zoom_start=7,
        tiles="CartoDB positron"
    )

    def style_function(feature):
        name = feature.get("properties", {}).get("_dash_name", "")

        if name == selected_muni:
            return {
                "fillColor": "#2563eb",
                "color": "#1e3a8a",
                "weight": 2.2,
                "fillOpacity": 0.65
            }

        return {
            "fillColor": "#94a3b8",
            "color": "#475569",
            "weight": 0.6,
            "fillOpacity": 0.25
        }

    def highlight_function(feature):
        return {
            "fillColor": "#10b981",
            "color": "#065f46",
            "weight": 2.0,
            "fillOpacity": 0.65
        }

    folium.GeoJson(
        muni_geojson,
        name="Municipalities",
        style_function=style_function,
        highlight_function=highlight_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["_dash_name"],
            aliases=["Municipality:"],
            sticky=True
        ),
        popup=folium.GeoJsonPopup(
            fields=["_dash_name"],
            aliases=["Municipality:"]
        )
    ).add_to(m)

    result = st_folium(
        m,
        height=430,
        use_container_width=True,
        returned_objects=["last_active_drawing", "last_object_clicked"]
    )

    clicked_name = None

    if isinstance(result, dict):
        drawing = result.get("last_active_drawing")

        if drawing and isinstance(drawing, dict):
            props = drawing.get("properties", {})
            clicked_name = props.get("_dash_name")

    return clicked_name


# ============================================================
# 4. Main combined dataset loader
# ============================================================

COMBINED_REQUIRED = [
    "regio",
    "gm_naam",
    "a_inw",
    "bev_dich",
    "p_ink_li",
    "ste_mvs",
    "pct_within_10min"
]

CORE_AMENITIES = [
    "apotheek",
    "basisschool",
    "bushalte",
    "huisarts",
    "kinderopvang",
    "supermarkt",
    "treinstation",
    "voortgezet_onderwijs",
    "ziekenhuis"
]


def class_to_score(series):
    """
    Consistent class scoring for all bike10_klasse_* variables:
    0 = no reachable amenity
    1 = one reachable amenity
    2+ = two or more reachable amenities
    """
    s = clean_numeric(series)

    score = np.select(
        [
            s.isna(),
            s <= 0,
            s == 1,
            s >= 2
        ],
        [
            np.nan,
            0,
            70,
            100
        ],
        default=np.nan
    )

    return pd.Series(score, index=series.index, dtype="float")


@st.cache_data(show_spinner=False)
def load_combined_neighbourhood_dataset(path_str, mtime):
    path = Path(path_str)

    df = pd.read_csv(path, low_memory=False)

    missing = [c for c in COMBINED_REQUIRED if c not in df.columns]

    if missing:
        raise ValueError(f"combined_neighbourhood_dataset.csv is missing columns: {missing}")

    out = df.copy()

    for c in [
        "a_inw",
        "bev_dich",
        "p_ink_li",
        "ste_mvs",
        "pct_within_10min",
        "mean_dist_km",
        "mean_time_min",
        "n_trips_weighted",
        "bike_detour_rate",
        "ebike_detour_rate",
        "bike10_weighted_score",
        "bike10_score",
        "bike10_total_facilities"
    ]:
        if c in out.columns:
            out[c] = clean_numeric(out[c])

    # Build consistent amenity-class score.
    bike10_class_cols = [
        c for c in out.columns
        if c.startswith("bike10_klasse_")
    ]

    for c in bike10_class_cols:
        out[c] = clean_numeric(out[c])
        amenity_name = c.replace("bike10_klasse_", "")
        out[f"score_{amenity_name}"] = class_to_score(out[c])

    score_cols = [f"score_{a}" for a in CORE_AMENITIES if f"score_{a}" in out.columns]

    if score_cols:
        out["bike10_class_access_score"] = out[score_cols].mean(axis=1)
    else:
        out["bike10_class_access_score"] = np.nan

    # Prefer provided weighted score if it exists; otherwise use class score.
    if "bike10_weighted_score" in out.columns and out["bike10_weighted_score"].notna().sum() > 0:
        out["bike10_access_score"] = out["bike10_weighted_score"]

        if out["bike10_access_score"].max(skipna=True) <= 1.5:
            out["bike10_access_score"] = out["bike10_access_score"] * 100
    else:
        out["bike10_access_score"] = out["bike10_class_access_score"]

    # Usage from first 10 minutes.
    out["usage_score"] = out["pct_within_10min"]

    if out["usage_score"].max(skipna=True) <= 1.5:
        out["usage_score"] = out["usage_score"] * 100

    out["low_access_flag"] = out["bike10_access_score"] < 50

    def wavg(g, col):
        vals = g[col]
        weights = g["a_inw"].fillna(1).replace(0, 1)

        if vals.notna().sum() == 0:
            return np.nan

        return np.average(vals.fillna(vals.mean()), weights=weights)

    agg_dict = {
        "access_score": lambda g: wavg(g, "bike10_access_score"),
        "class_access_score": lambda g: wavg(g, "bike10_class_access_score"),
        "usage_score": lambda g: wavg(g, "usage_score"),
        "low_income_share": lambda g: wavg(g, "p_ink_li"),
        "density": lambda g: wavg(g, "bev_dich"),
        "urbanisation_code": lambda g: wavg(g, "ste_mvs"),
        "population": lambda g: g["a_inw"].sum(),
        "low_access_neighbourhood_share": lambda g: g["low_access_flag"].mean() * 100,
        "n_neighbourhoods": lambda g: len(g)
    }

    rows = []

    for name, g in out.dropna(subset=["gm_naam"]).groupby("gm_naam"):
        row = {
            "municipality": name
        }

        for k, fn in agg_dict.items():
            row[k] = fn(g)

        for col in score_cols:
            row[col] = wavg(g, col)

        rows.append(row)

    muni = pd.DataFrame(rows)

    muni["policy_case"] = muni.apply(
        lambda r: classify_policy_case(r["access_score"], r["usage_score"]),
        axis=1
    )

    coverage_rows = []

    for col in score_cols:
        amenity = col.replace("score_", "")
        coverage_rows.append({
            "Amenity": amenity.replace("_", " ").title(),
            "Mean access score": out[col].mean(),
            "Low-access neighbourhoods (%)": (out[col] < 50).mean() * 100,
            "Metric explanation": "Class score: 0 = 0, 1 = 70, 2+ = 100"
        })

    coverage = pd.DataFrame(coverage_rows)

    return out, muni, coverage, score_cols


# ============================================================
# 5. Optional Bike Trip Purpose loader
# ============================================================

BIKE_REQUIRED = [
    "AfstV",
    "Bike type (main mode)",
    "Urbanization level",
    "Trip purpose",
    "Total Trips",
    "Sample Trips"
]


def essential_purpose(x):
    x = str(x).lower()

    keys = [
        "work",
        "education",
        "school",
        "shopping",
        "groceries",
        "grocery",
        "service",
        "doctor",
        "medical",
        "care"
    ]

    return any(k in x for k in keys)


@st.cache_data(show_spinner=False)
def load_bike_trip(path_str, sheet_name, mtime):
    path = Path(path_str)
    df = pd.read_excel(path, sheet_name=sheet_name)

    missing = [c for c in BIKE_REQUIRED if c not in df.columns]

    if missing:
        raise ValueError(f"Bike_Trip purpose file is missing columns: {missing}")

    df = df.copy()

    df["AfstV"] = clean_numeric(df["AfstV"])
    df["Total Trips"] = clean_numeric(df["Total Trips"])
    df["Sample Trips"] = clean_numeric(df["Sample Trips"])
    df["is_essential"] = df["Trip purpose"].apply(essential_purpose)
    df["within_3km"] = df["AfstV"] <= 3

    essential = df[df["is_essential"]].copy()

    by_bike = (
        essential
        .groupby("Bike type (main mode)")
        .apply(lambda g: pd.Series({
            "total": g["Total Trips"].sum(),
            "within_3km": g.loc[g["within_3km"], "Total Trips"].sum()
        }))
        .reset_index()
    )

    by_bike["share_within_3km"] = by_bike["within_3km"] / by_bike["total"] * 100

    by_purpose = (
        df
        .groupby(["Trip purpose", "Bike type (main mode)"], as_index=False)["Total Trips"]
        .sum()
    )

    return {
        "raw": df,
        "by_bike": by_bike,
        "by_purpose": by_purpose
    }


# ============================================================
# 6. Scenario functions
# ============================================================

def apply_scenario_to_neighbourhoods(df, scenario_type, score_cols):
    after = df.copy()

    if scenario_type == "No scenario":
        return after

    if scenario_type == "Add grocery / supermarket":
        for c in score_cols:
            if "supermarkt" in c or "supermarket" in c:
                after[c] = np.maximum(after[c], 85)

    elif scenario_type == "Add GP / healthcare":
        for c in score_cols:
            if "huisarts" in c or "ziekenhuis" in c or "apotheek" in c:
                after[c] = np.maximum(after[c], 85)

    elif scenario_type == "Add school / childcare access":
        for c in score_cols:
            if "school" in c or "onderwijs" in c or "kinderopvang" in c:
                after[c] = np.maximum(after[c], 85)

    elif scenario_type == "Improve cycling accessibility by 10%":
        for c in score_cols:
            after[c] = (after[c] + 10).clip(0, 100)

    elif scenario_type == "Improve cycling accessibility by 20%":
        for c in score_cols:
            after[c] = (after[c] + 20).clip(0, 100)

    after["bike10_access_score"] = after[score_cols].mean(axis=1)
    after["low_access_flag"] = after["bike10_access_score"] < 50

    return after


def aggregate_selected_muni(neigh_df, municipality_name, score_cols):
    if neigh_df.empty:
        return pd.Series(dtype=float)

    def wavg(g, col):
        vals = g[col]
        weights = g["a_inw"].fillna(1).replace(0, 1)

        if vals.notna().sum() == 0:
            return np.nan

        return np.average(vals.fillna(vals.mean()), weights=weights)

    g = neigh_df.copy()

    row = {
        "municipality": municipality_name,
        "access_score": wavg(g, "bike10_access_score"),
        "usage_score": wavg(g, "usage_score"),
        "low_income_share": wavg(g, "p_ink_li"),
        "density": wavg(g, "bev_dich"),
        "urbanisation_code": wavg(g, "ste_mvs"),
        "population": g["a_inw"].sum(),
        "low_access_neighbourhood_share": g["low_access_flag"].mean() * 100,
        "n_neighbourhoods": len(g)
    }

    for col in score_cols:
        row[col] = wavg(g, col)

    return pd.Series(row)


# ============================================================
# 7. Auto-detect datasets
# ============================================================

combined_path = find_dataset_file([
    r"combined_neighbourhood_dataset\.csv$",
    r"combined.*neighbourhood.*\.csv$"
])

bike_path = find_dataset_file([
    r"Bike_Trip purpose\.(xlsx|xls)$",
    r"Bike.*Trip.*purpose"
])

bike_sheet = pick_sheet(bike_path, "Bike_Trip purpse") if bike_path else None


# ============================================================
# 8. Hero and dataset bubbles
# ============================================================

st.markdown(
    """
    <div class="hero">
        <h1>10-Minute Cycling City Dashboard</h1>
        <p>Low-income focused MVP for Topic 3. Select municipalities from a map, inspect access and 10-minute usage, run what-if scenarios, and ask Gemini for policy guidance.</p>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("### Automatically selected datasets")

col1, col2 = st.columns(2)


def dataset_bubble(col, title, path, sheet, expected):
    ok = path is not None
    klass = "bubble bubble-ok" if ok else "bubble bubble-warn"
    status = "FOUND" if ok else "MISSING"
    file_text = path.name if ok else expected
    sheet_text = f"Sheet: {sheet}" if sheet else ""

    col.markdown(
        f"""
        <div class="{klass}">
            <span class="small-pill">{status}</span>
            <h3>{title}</h3>
            <p><b>{file_text}</b></p>
            <p>{sheet_text}</p>
        </div>
        """,
        unsafe_allow_html=True
    )


dataset_bubble(col1, "Combined neighbourhood data", combined_path, None, "combined_neighbourhood_dataset.csv")
dataset_bubble(col2, "Bike Trip Purpose", bike_path, bike_sheet, "Bike_Trip purpose.xlsx")

if combined_path is None:
    st.markdown(
        "<div class='bad'>Missing main dataset. Put <b>combined_neighbourhood_dataset.csv</b> inside the <code>datasets/</code> folder.</div>",
        unsafe_allow_html=True
    )
    st.stop()


# ============================================================
# 9. Load data
# ============================================================

try:
    neighbourhoods, municipalities_df, coverage_df, score_cols = load_combined_neighbourhood_dataset(
        str(combined_path),
        file_mtime(combined_path)
    )
except Exception as e:
    st.error(f"Could not load combined_neighbourhood_dataset.csv: {e}")
    st.stop()

bike_context = None

if bike_path is not None:
    try:
        bike_context = load_bike_trip(
            str(bike_path),
            bike_sheet,
            file_mtime(bike_path)
        )
    except Exception as e:
        st.warning(f"Bike Trip purpose file found but could not be used: {e}")
        bike_context = None


# ============================================================
# 10. Municipality map selection
# ============================================================

municipality_names = sorted(municipalities_df["municipality"].dropna().astype(str).unique())

if "selected_muni" not in st.session_state:
    st.session_state.selected_muni = municipality_names[0] if municipality_names else None

st.sidebar.title("Dashboard controls")
st.sidebar.markdown("### Select municipality from map")

with st.sidebar.expander("Map source", expanded=False):
    st.write("Municipality boundaries are downloaded automatically from PDOK/CBS Gebiedsindelingen 2025 WFS and cached locally.")

muni_geojson_raw = None
muni_geojson = None

try:
    muni_geojson_raw = download_cbs_boundary_geojson("gemeente", "2025_gemeente_v1")
    muni_geojson = prepare_municipality_geojson(muni_geojson_raw, municipality_names)
except Exception as e:
    st.sidebar.warning(f"Could not download municipality map: {e}")

clicked_muni = render_municipality_map(muni_geojson, st.session_state.selected_muni)

if clicked_muni and clicked_muni in municipality_names:
    if clicked_muni != st.session_state.selected_muni:
        st.session_state.selected_muni = clicked_muni
        st.rerun()

fallback_index = (
    municipality_names.index(st.session_state.selected_muni)
    if st.session_state.selected_muni in municipality_names
    else 0
)

selected_from_dropdown = st.sidebar.selectbox(
    "Fallback / exact municipality selector",
    municipality_names,
    index=fallback_index
)

if selected_from_dropdown != st.session_state.selected_muni:
    st.session_state.selected_muni = selected_from_dropdown
    st.rerun()

selected_muni = st.session_state.selected_muni

scenario_type = st.sidebar.selectbox(
    "What-if scenario",
    [
        "No scenario",
        "Add grocery / supermarket",
        "Add GP / healthcare",
        "Add school / childcare access",
        "Improve cycling accessibility by 10%",
        "Improve cycling accessibility by 20%"
    ]
)

st.sidebar.markdown("---")

if genai is not None and GEMINI_API_KEY.strip() != "":
    st.sidebar.success("Gemini available")
elif genai is not None:
    st.sidebar.warning("Gemini package installed, but API key is empty")
else:
    st.sidebar.warning("Gemini package not installed; using fallback assistant")


# ============================================================
# 11. Selected municipality summary
# ============================================================

selected_neighbourhoods = neighbourhoods[neighbourhoods["gm_naam"] == selected_muni].copy()

if selected_neighbourhoods.empty:
    st.error("No neighbourhoods found for selected municipality.")
    st.stop()

before_row = aggregate_selected_muni(
    selected_neighbourhoods,
    selected_muni,
    score_cols
)

scenario_neighbourhoods = apply_scenario_to_neighbourhoods(
    selected_neighbourhoods,
    scenario_type,
    score_cols
)

after_row = aggregate_selected_muni(
    scenario_neighbourhoods,
    selected_muni,
    score_cols
)

access_score = float(before_row["access_score"])
usage_score = float(before_row["usage_score"]) if not pd.isna(before_row["usage_score"]) else np.nan
low_income_share = float(before_row["low_income_share"]) if not pd.isna(before_row["low_income_share"]) else np.nan
low_access_share = float(before_row["low_access_neighbourhood_share"]) if not pd.isna(before_row["low_access_neighbourhood_share"]) else np.nan

scenario_access_score = float(after_row["access_score"])
scenario_usage_score = float(after_row["usage_score"]) if not pd.isna(after_row["usage_score"]) else usage_score

policy_case = classify_policy_case(access_score, usage_score)
scenario_case = classify_policy_case(scenario_access_score, scenario_usage_score)

st.markdown("### Selected municipality")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Municipality", selected_muni)
m2.metric("Bike-10 access score", f"{access_score:.1f}/100")
m3.metric("Low-income share", fmt_pct(low_income_share))
m4.metric("Low-access neighbourhoods", f"{low_access_share:.1f}%")

st.info(recommendation_from_case(policy_case))

st.markdown(
    f"<div class='metric-note'>{urbanisation_code_explanation()}</div>",
    unsafe_allow_html=True
)


# ============================================================
# 12. Graph explorer: original views only
# ============================================================

GRAPH_TITLES = [
    "Feature 1: Access-Usage Heatmap",
    "3 km bike-shed for selected neighbourhood",
    "Selected municipality in national access-income context",
    "Selected municipality essential function audit",
    "Low-access neighbourhoods in selected municipality",
    "Neighbourhood access vs low-income share in selected municipality",
    "Cycling-purpose context from Bike Trip file"
]

if "graph_index" not in st.session_state:
    st.session_state.graph_index = 0

# Prevent old saved graph_index from pointing beyond new shortened list.
if st.session_state.graph_index >= len(GRAPH_TITLES):
    st.session_state.graph_index = 0

st.markdown("### Graph explorer: original dataset views")

nav1, nav2, nav3 = st.columns([1, 2, 1])

if nav1.button("← Previous graph", use_container_width=True):
    st.session_state.graph_index = (st.session_state.graph_index - 1) % len(GRAPH_TITLES)

if nav3.button("Next graph →", use_container_width=True):
    st.session_state.graph_index = (st.session_state.graph_index + 1) % len(GRAPH_TITLES)

nav2.markdown(
    f"<div class='section-card'><b>Current graph:</b> {GRAPH_TITLES[st.session_state.graph_index]}</div>",
    unsafe_allow_html=True
)


def render_bikeshed_map():
    if folium is None or st_folium is None:
        st.warning("Install folium and streamlit-folium to see the bike-shed map.")
        st.code("python3 -m pip install folium streamlit-folium")
        return

    local = selected_neighbourhoods.copy()

    if local.empty:
        st.warning("No neighbourhood rows found for the selected municipality.")
        return

    neighbourhood_list = sorted(local["regio"].dropna().astype(str).unique())

    selected_buurt = st.selectbox(
        "Select neighbourhood for the 3 km bike-shed",
        neighbourhood_list
    )

    selected_buurt_row = local[local["regio"] == selected_buurt].iloc[0]

    selected_buurt_name = str(selected_buurt_row["regio"])
    selected_buurt_code = normalise_buurt_code(selected_buurt_row["regio"])
    selected_muni_norm = normalize_text(selected_muni)
    selected_buurt_norm = normalize_text(selected_buurt_name)

    buurt_geojson = None

    try:
        raw_buurt = download_cbs_boundary_geojson("buurt", "2025_buurt_v1")
        buurt_geojson = prepare_buurt_geojson(raw_buurt)
    except Exception:
        buurt_geojson = None

    center = None
    matched_feature = None
    match_method = "No exact boundary match found"

    if buurt_geojson is not None:
        features = buurt_geojson.get("features", [])

        # ----------------------------------------------------
        # 1. Best match: buurt code
        # ----------------------------------------------------
        for feat in features:
            props = feat.get("properties", {})

            code_prop = find_geojson_code_property(feat)

            if code_prop is None:
                continue

            geo_code = normalise_buurt_code(props.get(code_prop, ""))

            if geo_code and geo_code == selected_buurt_code:
                matched_feature = feat
                center = centroid_from_geojson_geometry(feat.get("geometry"))
                match_method = f"Matched by neighbourhood code: {selected_buurt_code}"
                break

        # ----------------------------------------------------
        # 2. Second-best match: municipality + neighbourhood name
        # ----------------------------------------------------
        if matched_feature is None:
            for feat in features:
                props = feat.get("properties", {})

                name_prop = find_geojson_name_property(feat, "buurt")
                muni_prop = find_geojson_municipality_property(feat)

                geo_buurt_name = normalize_text(props.get(name_prop, "")) if name_prop else ""
                geo_muni_name = normalize_text(props.get(muni_prop, "")) if muni_prop else ""

                buurt_match = (
                    geo_buurt_name == selected_buurt_norm
                    or selected_buurt_norm in geo_buurt_name
                    or geo_buurt_name in selected_buurt_norm
                )

                muni_match = (
                    geo_muni_name == selected_muni_norm
                    or selected_muni_norm in geo_muni_name
                    or geo_muni_name in selected_muni_norm
                )

                if buurt_match and muni_match:
                    matched_feature = feat
                    center = centroid_from_geojson_geometry(feat.get("geometry"))
                    match_method = "Matched by municipality + neighbourhood name"
                    break

        # ----------------------------------------------------
        # 3. Last name-only fallback, but only if unique
        # ----------------------------------------------------
        if matched_feature is None:
            name_matches = []

            for feat in features:
                props = feat.get("properties", {})
                name_prop = find_geojson_name_property(feat, "buurt")
                geo_buurt_name = normalize_text(props.get(name_prop, "")) if name_prop else ""

                buurt_match = (
                    geo_buurt_name == selected_buurt_norm
                    or selected_buurt_norm in geo_buurt_name
                    or geo_buurt_name in selected_buurt_norm
                )

                if buurt_match:
                    name_matches.append(feat)

            if len(name_matches) == 1:
                matched_feature = name_matches[0]
                center = centroid_from_geojson_geometry(matched_feature.get("geometry"))
                match_method = "Matched by neighbourhood name only"
            elif len(name_matches) > 1:
                st.warning(
                    f"Multiple CBS boundary matches were found for neighbourhood name '{selected_buurt_name}'. "
                    "The map will use the municipality centre instead to avoid showing the wrong neighbourhood."
                )

    # ----------------------------------------------------
    # 4. Municipality fallback
    # ----------------------------------------------------
    if center is None and muni_geojson is not None:
        for feat in muni_geojson.get("features", []):
            if feat.get("properties", {}).get("_dash_name") == selected_muni:
                center = centroid_from_geojson_geometry(feat.get("geometry"))
                match_method = "Fallback: municipality centre"
                break

    if center is None:
        center = (52.15, 5.35)
        match_method = "Fallback: Netherlands centre"

    m = folium.Map(
        location=center,
        zoom_start=12 if matched_feature is not None else 10,
        tiles="CartoDB positron"
    )

    if matched_feature is not None:
        folium.GeoJson(
            matched_feature,
            name="Selected neighbourhood",
            tooltip=selected_buurt_name,
            style_function=lambda f: {
                "fillColor": "#2563eb",
                "color": "#1e3a8a",
                "weight": 2,
                "fillOpacity": 0.35
            }
        ).add_to(m)

    folium.Circle(
        location=center,
        radius=3000,
        color="#10b981",
        fill=True,
        fill_opacity=0.18,
        popup="3 km / approx. 10-minute bike-shed"
    ).add_to(m)

    folium.Marker(
        center,
        tooltip=f"{selected_buurt_name} — approximate bike-shed centre"
    ).add_to(m)

    st_folium(m, height=550, use_container_width=True)

    st.caption(
        f"{match_method}. The green circle represents the assignment’s 3 km approximation of a 10-minute cycling radius. "
        "The current analysis also uses pct_within_10min for usage, so the dashboard can compare access with first-10-minute mobility behaviour."
    )

    st.markdown(
        f"""
        <div class="section-card">
        <b>Selected neighbourhood:</b> {selected_buurt_name}<br>
        <b>Bike-10 access score:</b> {selected_buurt_row['bike10_access_score']:.1f}/100<br>
        <b>Usage within 10 minutes:</b> {fmt_pct(selected_buurt_row['usage_score'])}<br>
        <b>Low-income share:</b> {fmt_pct(selected_buurt_row['p_ink_li'])}<br>
        <b>Urbanisation code:</b> {selected_buurt_row['ste_mvs']}<br>
        <b>Boundary match:</b> {match_method}<br>
        <b>Metric explanation:</b> amenity class variables use 0 = 0, 1 = 70, 2+ = 100.
        </div>
        """,
        unsafe_allow_html=True
    )


def render_graph(index):
    if index == 0:
        plot_df = municipalities_df.copy()

        plot_df["State"] = np.where(
            plot_df["municipality"] == selected_muni,
            f"Selected: {selected_muni}",
            "Other municipalities"
        )

        plot_df["policy_zone"] = plot_df.apply(
            lambda r: classify_policy_case(r["access_score"], r["usage_score"]),
            axis=1
        )

        fig = px.scatter(
            plot_df,
            x="access_score",
            y="usage_score",
            size="population",
            color="State",
            symbol="policy_zone",
            hover_name="municipality",
            title="Access-Usage Heatmap: local living success vs policy opportunity",
            labels={
                "access_score": "Bike-10 access score (0-100)",
                "usage_score": "Share of trips within first 10 minutes (%)",
                "policy_zone": "Policy zone"
            },
            color_discrete_map={
                "Other municipalities": "#CBD5E1",
                f"Selected: {selected_muni}": "#2563EB"
            }
        )

        fig.add_vline(x=70, line_dash="dash", line_color="#64748b")
        fig.add_hline(y=60, line_dash="dash", line_color="#64748b")

        fig.add_annotation(
            x=86,
            y=88,
            text="Environmental success<br>high access + high usage",
            showarrow=False,
            bgcolor="rgba(16,185,129,.15)"
        )

        fig.add_annotation(
            x=86,
            y=35,
            text="Policy opportunity<br>good access + lower usage",
            showarrow=False,
            bgcolor="rgba(245,158,11,.15)"
        )

        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "This is the assignment’s Access-Usage Heatmap. "
            "Access comes from Bike-10 amenity accessibility; usage comes from pct_within_10min in the combined neighbourhood dataset."
        )

    elif index == 1:
        render_bikeshed_map()

    elif index == 2:
        base = municipalities_df.copy()

        base["State"] = np.where(
            base["municipality"] == selected_muni,
            f"Selected: {selected_muni}",
            "Other municipalities"
        )

        fig = px.scatter(
            base,
            x="low_income_share",
            y="access_score",
            size="population",
            color="State",
            hover_name="municipality",
            title=f"Where {selected_muni} sits in the national access-income pattern",
            labels={
                "low_income_share": "Low-income share (%)",
                "access_score": "Bike-10 access score (0-100)",
                "State": "Municipality"
            },
            color_discrete_map={
                "Other municipalities": "#CBD5E1",
                f"Selected: {selected_muni}": "#2563EB"
            }
        )

        fig.add_hline(y=50, line_dash="dash")

        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "This graph uses p_ink_li from the combined neighbourhood dataset. "
            "It shows whether the selected municipality combines weaker access with a higher share of low-income residents."
        )

    elif index == 3:
        selected_scores = []

        for col in score_cols:
            selected_scores.append({
                "Amenity": col.replace("score_", "").replace("_", " ").title(),
                "Access score": selected_neighbourhoods[col].mean(),
                "Comparison": "Selected municipality"
            })

            selected_scores.append({
                "Amenity": col.replace("score_", "").replace("_", " ").title(),
                "Access score": neighbourhoods[col].mean(),
                "Comparison": "National average"
            })

        plot_df = pd.DataFrame(selected_scores)

        fig = px.bar(
            plot_df,
            x="Access score",
            y="Amenity",
            color="Comparison",
            barmode="group",
            orientation="h",
            title=f"Essential function audit for {selected_muni}",
            labels={
                "Access score": "Mean amenity class score (0-100)"
            },
            color_discrete_map={
                "Selected municipality": "#2563EB",
                "National average": "#94A3B8"
            }
        )

        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "All amenity class variables are scored consistently: 0 = 0, 1 = 70, 2+ = 100. "
            "This fixes the earlier issue where school availability used a different metric."
        )

    elif index == 4:
        top = selected_neighbourhoods.sort_values("bike10_access_score").head(20)

        fig = px.bar(
            top,
            x="bike10_access_score",
            y="regio",
            orientation="h",
            color="p_ink_li",
            title=f"Lowest-access neighbourhoods in {selected_muni}",
            labels={
                "bike10_access_score": "Bike-10 access score (0-100)",
                "regio": "Neighbourhood",
                "p_ink_li": "Low-income share (%)"
            }
        )

        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "This graph lists the neighbourhoods with the weakest Bike-10 access in the selected municipality. "
            f"{urbanisation_code_explanation()}"
        )

    elif index == 5:
        fig = px.scatter(
            selected_neighbourhoods,
            x="p_ink_li",
            y="bike10_access_score",
            size="a_inw",
            color="ste_mvs",
            hover_name="regio",
            title=f"Neighbourhood access vs low-income share in {selected_muni}",
            labels={
                "p_ink_li": "Low-income share (%)",
                "bike10_access_score": "Bike-10 access score (0-100)",
                "a_inw": "Population",
                "ste_mvs": "Urbanisation code"
            }
        )

        fig.add_hline(y=50, line_dash="dash")

        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "The dashed line marks the low-access threshold. "
            f"{urbanisation_code_explanation()}"
        )

    elif index == 6:
        if bike_context is None:
            st.warning("Bike_Trip purpose.xlsx was not found or could not be read.")
            return

        st.markdown(
            "<div class='hint'>The Bike Trip Purpose file is an aggregated cycling-context dataset, not municipality-specific. "
            "Changing municipality will not change this graph.</div>",
            unsafe_allow_html=True
        )

        tab_a, tab_b = st.tabs(["Essential cycling within 3 km", "Purpose by bike type"])

        with tab_a:
            fig = px.bar(
                bike_context["by_bike"],
                x="Bike type (main mode)",
                y="share_within_3km",
                title="Share of essential cycling trips within 3 km by bike type",
                labels={
                    "share_within_3km": "% essential cycling trips within 3 km"
                }
            )

            st.plotly_chart(fig, use_container_width=True)

        with tab_b:
            fig = px.bar(
                bike_context["by_purpose"],
                x="Total Trips",
                y="Trip purpose",
                color="Bike type (main mode)",
                orientation="h",
                title="Cycling trips by purpose and bike type"
            )

            st.plotly_chart(fig, use_container_width=True)


render_graph(st.session_state.graph_index)


# ============================================================
# 13. What-if scenario section: updated views only
# ============================================================

st.markdown("---")
st.markdown("## What-if scenario view")

st.markdown(
    """
    <div class="section-card">
    The graphs above remain the original dataset views. This section shows the updated view after the selected what-if scenario.
    </div>
    """,
    unsafe_allow_html=True
)

s1, s2, s3 = st.columns(3)

s1.metric("Selected scenario", scenario_type)
s2.metric(
    "Updated Bike-10 access score",
    f"{scenario_access_score:.1f}/100",
    delta=f"{scenario_access_score - access_score:.1f}" if scenario_type != "No scenario" else "0"
)
s3.metric("Updated policy case", scenario_case)

if scenario_type == "No scenario":
    st.info("Choose a what-if scenario in the sidebar to generate updated graphs.")
else:
    st.markdown("### Updated Access-Usage Heatmap")

    updated_muni = municipalities_df.copy()

    updated_selected = after_row.copy()
    updated_selected["municipality"] = selected_muni
    updated_selected["policy_case"] = classify_policy_case(
        updated_selected["access_score"],
        updated_selected["usage_score"]
    )

    updated_muni = updated_muni[updated_muni["municipality"] != selected_muni].copy()
    updated_muni = pd.concat(
        [
            updated_muni,
            pd.DataFrame([updated_selected])
        ],
        ignore_index=True
    )

    updated_muni["State"] = np.where(
        updated_muni["municipality"] == selected_muni,
        f"Updated: {selected_muni}",
        "Other municipalities"
    )

    updated_muni["policy_zone"] = updated_muni.apply(
        lambda r: classify_policy_case(r["access_score"], r["usage_score"]),
        axis=1
    )

    fig_updated_heatmap = px.scatter(
        updated_muni,
        x="access_score",
        y="usage_score",
        size="population",
        color="State",
        symbol="policy_zone",
        hover_name="municipality",
        title="Updated Access-Usage Heatmap after scenario",
        labels={
            "access_score": "Updated Bike-10 access score (0-100)",
            "usage_score": "Share of trips within first 10 minutes (%)",
            "policy_zone": "Policy zone"
        },
        color_discrete_map={
            "Other municipalities": "#CBD5E1",
            f"Updated: {selected_muni}": "#10B981"
        }
    )

    fig_updated_heatmap.add_vline(x=70, line_dash="dash", line_color="#64748b")
    fig_updated_heatmap.add_hline(y=60, line_dash="dash", line_color="#64748b")

    st.plotly_chart(fig_updated_heatmap, use_container_width=True)

    st.markdown("### Updated Essential Function Audit")

    updated_scores = []

    for col in score_cols:
        updated_scores.append({
            "Amenity": col.replace("score_", "").replace("_", " ").title(),
            "Access score": scenario_neighbourhoods[col].mean()
        })

    updated_scores_df = pd.DataFrame(updated_scores)

    fig_updated_audit = px.bar(
        updated_scores_df,
        x="Access score",
        y="Amenity",
        orientation="h",
        title=f"Updated essential function audit for {selected_muni}",
        labels={
            "Access score": "Updated amenity class score (0-100)"
        }
    )

    st.plotly_chart(fig_updated_audit, use_container_width=True)

    st.markdown("### Updated Low-Access Neighbourhood Ranking")

    updated_top = scenario_neighbourhoods.sort_values("bike10_access_score").head(20)

    fig_updated_rank = px.bar(
        updated_top,
        x="bike10_access_score",
        y="regio",
        orientation="h",
        color="p_ink_li",
        title=f"Updated lowest-access neighbourhoods in {selected_muni}",
        labels={
            "bike10_access_score": "Updated Bike-10 access score (0-100)",
            "regio": "Neighbourhood",
            "p_ink_li": "Low-income share (%)"
        }
    )

    st.plotly_chart(fig_updated_rank, use_container_width=True)

    st.caption(
        "These updated graphs are separate from the original graph explorer. "
        "They show the scenario-adjusted dataset only."
    )


# ============================================================
# 14. Gemini assistant
# ============================================================

st.markdown("---")
st.markdown("## Ask Gemini about what-if scenarios")

st.markdown(
    """
    <div class="section-card">
    <b>Example questions:</b><br>
    • What if we add a supermarket to the lowest-access neighbourhoods?<br>
    • Should this municipality prioritise amenities or cycling infrastructure?<br>
    • How does the low-income focus change the recommendation?<br>
    • Give me a short policy recommendation for a presentation slide.<br>
    • What does the scenario-updated graph tell us?
    </div>
    """,
    unsafe_allow_html=True
)

context_text = f"""
Selected municipality: {selected_muni}
Original Bike-10 access score: {access_score:.1f}/100
Original first-10-minute usage score: {usage_score:.1f}%
Original policy case: {policy_case}
Low-income resident share from combined neighbourhood dataset: {fmt_pct(low_income_share)}
Share of low-access neighbourhoods: {low_access_share:.1f}%
Number of neighbourhoods: {int(before_row['n_neighbourhoods'])}

Scenario: {scenario_type}
Updated Bike-10 access score: {scenario_access_score:.1f}/100
Updated first-10-minute usage score: {scenario_usage_score:.1f}%
Updated policy case: {scenario_case}

Metric details:
- Low-income context comes from p_ink_li in combined_neighbourhood_dataset.csv.
- Usage comes from pct_within_10min in combined_neighbourhood_dataset.csv.
- Amenity classes use consistent scoring: 0 = 0, 1 = 70, 2+ = 100.
- Urbanisation code: 1 = very strongly urban, 2 = strongly urban, 3 = moderately urban, 4 = slightly urban, 5 = not urban/rural.
- Do not claim causality; give practical planning recommendations.
"""

if "chat_history_topic3_low_income" not in st.session_state:
    st.session_state.chat_history_topic3_low_income = []

for role, message in st.session_state.chat_history_topic3_low_income:
    with st.chat_message(role):
        st.write(message)

user_question = st.chat_input("Ask Gemini about this municipality or scenario...")

if user_question:
    st.session_state.chat_history_topic3_low_income.append(("user", user_question))

    with st.chat_message("user"):
        st.write(user_question)

    prompt = f"""
You are an urban mobility policy assistant for a 10-minute cycling city dashboard.
Focus specifically on the lowest-income group and equity.
Use only the dashboard context below.
Do not invent exact numbers beyond the provided values.
Do not claim causal proof.
Give concise, policy-oriented advice.

Dashboard context:
{context_text}

User question:
{user_question}

Answer using:
1. Interpretation
2. Low-income equity concern
3. Recommended action
"""

    answer = ask_gemini(prompt)

    if answer is None:
        answer = fallback_policy_answer(context_text, user_question)

    st.session_state.chat_history_topic3_low_income.append(("assistant", answer))

    with st.chat_message("assistant"):
        st.write(answer)


st.markdown("---")
st.caption(
    "MVP dashboard. The combined neighbourhood dataset is used for Bike-10 accessibility, low-income share, and first-10-minute usage. The optional Bike Trip Purpose file is used only as aggregated cycling-purpose context."
)