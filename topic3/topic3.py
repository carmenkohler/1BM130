# ============================================================
# Topic 3 - Minimum Product Urban Policy Dashboard
# Low-income focused + simplified graph carousel UI
#
# Streamlit + Gemini AI assistant
#
# This version automatically detects the three key datasets inside datasets/:
# 1. kwb2025.xlsx                         -> CBS KWB access/context
# 2. ODiN2024_DANS_Databestand_ Updated.xlsx -> detailed ODiN low-income mode choice
# 3. Bike_Trip purpose.xlsx                -> ODiN-derived cycling-purpose context
#
# It avoids repeatedly parsing the large ODiN file by:
# - reading only required columns
# - caching summaries with st.cache_data
# - loading ODiN only when an ODiN graph is requested
#
# Run:
# streamlit run topic3_dashboard_low_income_simplified.py
# ============================================================

from pathlib import Path
import re
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

px.defaults.template = "plotly_white"

try:
    from google import genai
except Exception:
    genai = None

# ============================================================
# 0. App setup
# ============================================================

st.set_page_config(
    page_title="10-Minute Cycling City Dashboard - Low Income Focus",
    layout="wide"
)

WORKSPACE = Path(__file__).resolve().parent
DATASETS_DIR = WORKSPACE / "datasets"

# Paste your Gemini API key here.
# Example: GEMINI_API_KEY = "AIzaSy..."
GEMINI_API_KEY = "AIzaSyCWoPw5ivr7K_JTgwkcXSSGVMpR97uIN4A"

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
        max-width: 1280px;
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
    }
    section[data-testid="stSidebar"] * { color: #e5e7eb !important; }
    section[data-testid="stSidebar"] div[data-baseweb="select"] * { color: #111827 !important; }
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
        min-height: 164px;
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
    .bubble-ok { border: 1px solid rgba(16,185,129,.38); }
    .bubble-warn { border: 1px solid rgba(245,158,11,.45); }
    .bubble h3 { margin: 0; color: #0f172a; font-size: 1.05rem; }
    .bubble p { margin: .35rem 0 0 0; color: #475569; font-size: .86rem; }
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
        background: rgba(255,255,255,.78);
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
    </style>
    """,
    unsafe_allow_html=True
)

# ============================================================
# 2. Helpers
# ============================================================

def clean_numeric(series):
    return (
        series.astype(str)
        .str.replace(",", ".", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace(" ", "", regex=False)
        .replace({".": np.nan, "nan": np.nan, "None": np.nan, "": np.nan, "x": np.nan, "X": np.nan, "-": np.nan})
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


def weighted_share(df, group_cols, value_col="weight"):
    grouped = df.groupby(group_cols, dropna=False)[value_col].sum().reset_index(name="weighted_trips")
    if not isinstance(group_cols, list):
        group_cols = [group_cols]
    denom_cols = group_cols[:-1]
    if denom_cols:
        denom = grouped.groupby(denom_cols)["weighted_trips"].transform("sum")
    else:
        denom = grouped["weighted_trips"].sum()
    grouped["share"] = grouped["weighted_trips"] / denom * 100
    return grouped


def classify_policy_case(access_score, low_income_share=None):
    # Higher access is good. Low-income share is context, not a problem by itself.
    if pd.isna(access_score):
        return "insufficient data"
    if access_score >= 75:
        return "strong access"
    if access_score >= 50:
        return "moderate access"
    return "low access"


def fmt_pct(value):
    if pd.isna(value):
        return "No data"
    return f"{float(value):.1f}%"


def fmt_num(value, suffix=""):
    if pd.isna(value):
        return "No data"
    return f"{float(value):.1f}{suffix}"


def has_enough_numeric(series, min_count=5):
    return pd.Series(series).dropna().shape[0] >= min_count


def recommendation_from_case(case):
    if case == "strong access":
        return "Access is relatively strong. Policy attention should focus on whether low-income residents actually use active modes and whether routes feel safe and direct."
    if case == "moderate access":
        return "Access is mixed. Target missing amenities and improve route directness toward the weakest essential functions."
    if case == "low access":
        return "Access is weak. Prioritise direct cycling links to essential services and consider adding missing daily amenities in underserved neighbourhoods."
    return "More data is needed before making a targeted recommendation."


def ask_gemini(prompt):
    api_key = GEMINI_API_KEY.strip()
    if not api_key or api_key == "PASTE_YOUR_GEMINI_API_KEY_HERE" or genai is None:
        return None
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return response.text


def fallback_policy_answer(context_text, user_question):
    return f"""
**Interpretation**
{context_text}

**Answer to your question**
For: "{user_question}", first decide whether the selected municipality has an access problem or a usage/infrastructure problem.

**Recommended policy action**
If access is weak, improve connections to supermarkets, GP/doctor services, schools, and childcare. If access is already strong, focus on cycling safety, route directness, parking, and barriers that may prevent low-income residents from choosing active mobility.
"""

# ============================================================
# 3. Dataset loaders
# ============================================================

KWB_REQUIRED = ["regio", "gm_naam", "a_inw", "bev_dich", "p_ink_li", "ste_mvs", "g_afs_hp", "g_afs_gs", "g_afs_kv", "g_afs_sc", "g_3km_sc"]
BIKE_REQUIRED = ["AfstV", "Bike type (main mode)", "Urbanization level", "Trip purpose", "Total Trips", "Sample Trips"]
ODIN_REQUIRED = ["HHGestInkG", "Hvm", "MotiefV", "Sted", "Prov", "Reisduur", "FactorV"]
ODIN_OPTIONAL = ["AfstV"]

@st.cache_data(show_spinner=False)
def load_kwb(path_str, sheet_name, mtime):
    path = Path(path_str)
    df = pd.read_excel(path, sheet_name=sheet_name)
    missing = [c for c in KWB_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"CBS KWB file is missing columns: {missing}")

    out = df.copy()
    for c in ["a_inw", "bev_dich", "p_ink_li", "ste_mvs", "g_afs_hp", "g_afs_gs", "g_afs_kv", "g_afs_sc", "g_3km_sc"]:
        out[c] = clean_numeric(out[c])

    # Continuous access score, less inflated than binary <=3 km scoring.
    # Distance score: 3km or more = 0, 0km = 100. This preserves low-access differences.
    out["score_gp"] = (1 - out["g_afs_hp"] / 3).clip(0, 1) * 100
    out["score_supermarket"] = (1 - out["g_afs_gs"] / 3).clip(0, 1) * 100
    out["score_childcare"] = (1 - out["g_afs_kv"] / 3).clip(0, 1) * 100
    out["score_school_distance"] = (1 - out["g_afs_sc"] / 3).clip(0, 1) * 100
    out["score_schools_within_3km"] = (out["g_3km_sc"].clip(0, 5) / 5) * 100

    access_cols = ["score_gp", "score_supermarket", "score_childcare", "score_school_distance", "score_schools_within_3km"]
    out["bike10_access_score"] = out[access_cols].mean(axis=1)
    out["low_access_flag"] = out["bike10_access_score"] < 50

    # Municipality aggregation, population weighted
    def wavg(g, col):
        vals = g[col]
        weights = g["a_inw"].fillna(1).replace(0, 1)
        if vals.notna().sum() == 0:
            return np.nan
        return np.average(vals.fillna(vals.mean()), weights=weights)

    muni = (
        out.dropna(subset=["gm_naam", "bike10_access_score"])
        .groupby("gm_naam", as_index=False)
        .apply(lambda g: pd.Series({
            "access_score": wavg(g, "bike10_access_score"),
            "low_income_share": wavg(g, "p_ink_li"),
            "density": wavg(g, "bev_dich"),
            "urbanisation_code": wavg(g, "ste_mvs"),
            "population": g["a_inw"].sum(),
            "low_access_neighbourhood_share": g["low_access_flag"].mean() * 100,
            "n_neighbourhoods": len(g)
        }))
        .reset_index(drop=True)
        .rename(columns={"gm_naam": "municipality"})
    )
    muni["policy_case"] = muni["access_score"].apply(classify_policy_case)

    coverage = pd.DataFrame({
        "Amenity": ["GP / doctor", "Large supermarket", "Childcare", "School distance", "Schools within 3 km"],
        "Mean access score": [out[c].mean() for c in access_cols],
        "Low-access neighbourhoods (%)": [(out[c] < 50).mean() * 100 for c in access_cols]
    })

    return out, muni, coverage


def essential_purpose(x):
    x = str(x).lower()
    keys = ["work", "education", "school", "shopping", "groceries", "grocery", "service", "doctor", "medical", "care"]
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

    by_bike = essential.groupby("Bike type (main mode)").apply(lambda g: pd.Series({
        "total": g["Total Trips"].sum(),
        "within_3km": g.loc[g["within_3km"], "Total Trips"].sum()
    })).reset_index()
    by_bike["share_within_3km"] = by_bike["within_3km"] / by_bike["total"] * 100

    by_urban = essential.groupby("Urbanization level").apply(lambda g: pd.Series({
        "total": g["Total Trips"].sum(),
        "within_3km": g.loc[g["within_3km"], "Total Trips"].sum()
    })).reset_index()
    by_urban["share_within_3km"] = by_urban["within_3km"] / by_urban["total"] * 100

    by_purpose = df.groupby(["Trip purpose", "Bike type (main mode)"], as_index=False)["Total Trips"].sum()

    return {"raw": df, "by_bike": by_bike, "by_urban": by_urban, "by_purpose": by_purpose}

@st.cache_data(show_spinner=False)
def load_codebook_mappings(datasets_dir_str):
    datasets_dir = Path(datasets_dir_str)
    codebook = find_dataset_file([r"Codeboek.*ODiN", r"ODiN.*Codeboek"])
    mappings = {}
    if codebook is None:
        return mappings
    try:
        cb = pd.read_excel(codebook, sheet_name="Codeboek DANS ODiN 2024")
        required = ["Variabele_naam_DANS_ODiN_2024", "Code_DANS_ODiN_2024", "Code_label_DANS_ODiN_2024"]
        if all(c in cb.columns for c in required):
            for var in ["Hvm", "MotiefV", "Sted", "Prov"]:
                sub = cb[cb["Variabele_naam_DANS_ODiN_2024"].astype(str).str.strip() == var]
                maps = {}
                for _, r in sub.iterrows():
                    maps[str(r["Code_DANS_ODiN_2024"]).strip()] = str(r["Code_label_DANS_ODiN_2024"]).strip()
                    try:
                        maps[str(int(float(r["Code_DANS_ODiN_2024"]))).strip()] = str(r["Code_label_DANS_ODiN_2024"]).strip()
                    except Exception:
                        pass
                mappings[var] = maps
    except Exception:
        return {}
    return mappings


def map_with_codebook(series, mapping):
    if not mapping:
        return series.astype(str)
    return series.astype(str).str.strip().map(mapping).fillna(series.astype(str))


def classify_mode_from_label(label, raw_value=None):
    text = str(label).lower()
    raw = str(raw_value).strip()
    if any(k in text for k in ["fiets", "bike", "bicycle", "e-bike", "elektrische fiets"]):
        return "bike"
    if any(k in text for k in ["auto", "car", "personenauto"]):
        return "car"
    if any(k in text for k in ["trein", "train", "bus", "tram", "metro", "openbaar", "public"]):
        return "public transport"
    # Fallback only if codebook labels are not available. These codes may need adjustment.
    numeric_map = {
        "1": "public transport", "2": "public transport",
        "3": "car", "4": "car",
        "5": "bike", "6": "bike", "7": "bike"
    }
    return numeric_map.get(raw, "other")

@st.cache_data(show_spinner=False)
def load_odin_low_income_summaries(path_str, sheet_name, mtime, datasets_dir_str):
    """
    Reads only required ODiN columns. This is still the slowest step the first time,
    but Streamlit caches the resulting summaries so it should not re-parse every rerun.
    """
    path = Path(path_str)

    header = pd.read_excel(path, sheet_name=sheet_name, nrows=0)
    needed = [c for c in ODIN_REQUIRED + ODIN_OPTIONAL if c in header.columns]
    missing = [c for c in ODIN_REQUIRED if c not in header.columns]
    if missing:
        raise ValueError(f"Detailed ODiN file is missing columns: {missing}")

    df = pd.read_excel(path, sheet_name=sheet_name, usecols=needed)
    maps = load_codebook_mappings(datasets_dir_str)

    df["HHGestInkG"] = clean_numeric(df["HHGestInkG"])
    df["Reisduur"] = clean_numeric(df["Reisduur"])
    df["weight"] = clean_numeric(df["FactorV"]).fillna(1)
    if "AfstV" in df.columns:
        df["AfstV"] = clean_numeric(df["AfstV"])

    valid_income = df["HHGestInkG"].dropna()
    valid_income = valid_income[valid_income > 0]
    lowest_income_value = valid_income.min() if not valid_income.empty else df["HHGestInkG"].min()
    low = df[df["HHGestInkG"] == lowest_income_value].copy()

    low["Hvm_label"] = map_with_codebook(low["Hvm"], maps.get("Hvm", {}))
    low["MotiefV_label"] = map_with_codebook(low["MotiefV"], maps.get("MotiefV", {}))
    low["Sted_label"] = map_with_codebook(low["Sted"], maps.get("Sted", {}))
    low["Prov_label"] = map_with_codebook(low["Prov"], maps.get("Prov", {}))
    low["mode_class"] = [classify_mode_from_label(lbl, raw) for lbl, raw in zip(low["Hvm_label"], low["Hvm"])]
    low["within_10min"] = low["Reisduur"] <= 10

    # Keep only the major classes for the dashboard focus.
    low_main = low[low["mode_class"].isin(["bike", "car", "public transport"])].copy()

    national_mode = weighted_share(low_main, "mode_class")
    purpose_mode = weighted_share(low_main, ["MotiefV_label", "mode_class"])
    within10_mode = weighted_share(low_main[low_main["within_10min"]], "mode_class")
    urban_mode = weighted_share(low_main, ["Sted_label", "mode_class"])
    province_mode = weighted_share(low_main, ["Prov_label", "mode_class"])

    top_purposes = (
        low_main.groupby("MotiefV_label")["weight"].sum().sort_values(ascending=False).head(10).index.tolist()
    )
    purpose_mode = purpose_mode[purpose_mode["MotiefV_label"].isin(top_purposes)].copy()

    # limit province rows to readable provinces/labels
    top_provs = low_main.groupby("Prov_label")["weight"].sum().sort_values(ascending=False).head(14).index.tolist()
    province_mode = province_mode[province_mode["Prov_label"].isin(top_provs)].copy()

    return {
        "lowest_income_value": lowest_income_value,
        "n_rows": len(low),
        "national_mode": national_mode,
        "purpose_mode": purpose_mode,
        "within10_mode": within10_mode,
        "urban_mode": urban_mode,
        "province_mode": province_mode
    }

# ============================================================
# 4. Auto-detect datasets
# ============================================================

kwb_path = find_dataset_file([r"^kwb2025\.(xlsx|xls)$", r"kerncijfers.*wijken.*buurten.*2025"])
bike_path = find_dataset_file([r"Bike_Trip purpose\.(xlsx|xls)$", r"Bike.*Trip.*purpose"])
odin_path = find_dataset_file([r"ODiN2024_DANS_Databestand.*\.(xlsx|xls)$", r"ODiN2024.*Databestand"])

kwb_sheet = pick_sheet(kwb_path, "KWB2025") if kwb_path else None
bike_sheet = pick_sheet(bike_path, "Bike_Trip purpse") if bike_path else None
odin_sheet = pick_sheet(odin_path, "ODiN2024_DANS_Databestand_v2.0") if odin_path else None

# ============================================================
# 5. Hero + dataset bubbles
# ============================================================

st.markdown(
    """
    <div class="hero">
        <h1>10-Minute Cycling City Dashboard</h1>
        <p>Low-income focused MVP for Topic 3. The dashboard automatically selects the three project datasets, cycles through policy graphs, and lets Gemini explain what-if scenarios.</p>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("### Automatically selected datasets")
col1, col2, col3 = st.columns(3)


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


dataset_bubble(col1, "CBS KWB 2025", kwb_path, kwb_sheet, "kwb2025.xlsx")
dataset_bubble(col2, "Detailed ODiN 2024", odin_path, odin_sheet, "ODiN2024_DANS_Databestand_ Updated.xlsx")
dataset_bubble(col3, "Bike Trip Purpose", bike_path, bike_sheet, "Bike_Trip purpose.xlsx")

if kwb_path is None:
    st.markdown("<div class='bad'>Missing CBS KWB file. Put <b>kwb2025.xlsx</b> inside the <code>datasets/</code> folder.</div>", unsafe_allow_html=True)
    st.stop()
if odin_path is None:
    st.markdown("<div class='bad'>Missing detailed ODiN file. Put <b>ODiN2024_DANS_Databestand_ Updated.xlsx</b> inside the <code>datasets/</code> folder.</div>", unsafe_allow_html=True)
if bike_path is None:
    st.markdown("<div class='hint'>Bike Trip purpose file was not found. The dashboard will still run, but cycling-purpose context graphs will be skipped.</div>", unsafe_allow_html=True)

# ============================================================
# 6. Load KWB and optional bike context immediately; ODiN lazily
# ============================================================

try:
    kwb_neigh, kwb_muni, kwb_coverage = load_kwb(str(kwb_path), kwb_sheet, file_mtime(kwb_path))
except Exception as e:
    st.error(f"Could not load CBS KWB dataset: {e}")
    st.stop()

bike_context = None
if bike_path is not None:
    try:
        bike_context = load_bike_trip(str(bike_path), bike_sheet, file_mtime(bike_path))
    except Exception as e:
        st.warning(f"Bike Trip purpose file found but could not be used: {e}")
        bike_context = None

# ============================================================
# 7. Sidebar controls
# ============================================================

st.sidebar.title("Dashboard controls")
municipalities = sorted(kwb_muni["municipality"].dropna().astype(str).unique())
selected_muni = st.sidebar.selectbox("Municipality", municipalities)
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
if genai is not None and GEMINI_API_KEY.strip() != "PASTE_YOUR_GEMINI_API_KEY_HERE":
    st.sidebar.success("Gemini available")
elif genai is not None:
    st.sidebar.warning("Gemini package installed, but API key placeholder is not filled")
else:
    st.sidebar.warning("Gemini package not installed; using fallback assistant")

# ============================================================
# 8. Selected municipality summary
# ============================================================

row = kwb_muni[kwb_muni["municipality"] == selected_muni].iloc[0]
selected_neigh = kwb_neigh[kwb_neigh["gm_naam"] == selected_muni].copy()
access_score = float(row["access_score"])
low_income_share = float(row["low_income_share"]) if not pd.isna(row["low_income_share"]) else np.nan
low_access_share = float(row["low_access_neighbourhood_share"]) if not pd.isna(row["low_access_neighbourhood_share"]) else np.nan
policy_case = classify_policy_case(access_score, low_income_share)
recommendation = recommendation_from_case(policy_case)

st.markdown("### Selected municipality")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Municipality", selected_muni)
m2.metric("Access score", f"{access_score:.1f}/100")
m3.metric("Low-income share", fmt_pct(low_income_share))
m4.metric("Low-access neighbourhoods", f"{low_access_share:.1f}%")
st.info(recommendation)

if pd.isna(low_income_share):
    st.warning(
        "CBS KWB does not contain a usable low-income-share value for the selected municipality. "
        "The dashboard will still show access and low-access-neighbourhood patterns, but income-specific charts for this municipality are limited."
    )

# ============================================================
# 9. Graph carousel
# ============================================================

GRAPH_TITLES = [
    "Selected municipality in national access-income context",
    "Selected municipality essential function audit",
    "Low-access neighbourhoods in selected municipality",
    "Neighbourhood access vs low-income share in selected municipality",
    "Low-income national mode choice",
    "Low-income first-10-minute mode choice",
    "Low-income mode choice by trip purpose",
    "Low-income mode choice by urbanisation",
    "Cycling-purpose context from Bike Trip file"
]

if "graph_index" not in st.session_state:
    st.session_state.graph_index = 0

st.markdown("### Graph explorer")
nav1, nav2, nav3 = st.columns([1, 2, 1])
if nav1.button("← Previous graph", use_container_width=True):
    st.session_state.graph_index = (st.session_state.graph_index - 1) % len(GRAPH_TITLES)
if nav3.button("Next graph →", use_container_width=True):
    st.session_state.graph_index = (st.session_state.graph_index + 1) % len(GRAPH_TITLES)
nav2.markdown(f"<div class='section-card'><b>Current graph:</b> {GRAPH_TITLES[st.session_state.graph_index]}</div>", unsafe_allow_html=True)


def render_graph(index):
    title = GRAPH_TITLES[index]

    # These selected-municipality tables are recomputed on every rerun,
    # so changing the sidebar municipality updates the visible graph.
    selected_muni_row = kwb_muni[kwb_muni["municipality"] == selected_muni].copy()
    selected_neigh_local = kwb_neigh[kwb_neigh["gm_naam"] == selected_muni].copy()

    if index == 0:
        # National context, with selected municipality highlighted.
        # If low-income share is missing or too sparse, fall back to a policy-relevant
        # access vulnerability axis so the plot does not become empty.
        base = kwb_muni.copy()
        base["is_selected"] = np.where(
            base["municipality"] == selected_muni,
            f"Selected: {selected_muni}",
            "Other municipalities"
        )

        use_income_axis = (
            has_enough_numeric(base["low_income_share"], min_count=10)
            and not selected_muni_row["low_income_share"].isna().all()
        )

        if use_income_axis:
            x_col = "low_income_share"
            x_label = "Low-income share (%)"
            title_text = f"Where {selected_muni} sits in the national access-income pattern"
            caption_text = (
                "The blue marker shows the selected municipality against all municipalities. "
                "It helps check whether the selected municipality combines weaker access with a higher low-income share."
            )
        else:
            x_col = "low_access_neighbourhood_share"
            x_label = "Share of low-access neighbourhoods (%)"
            title_text = f"Where {selected_muni} sits in the national access-vulnerability pattern"
            caption_text = (
                "Low-income share is missing for the selected municipality or too sparse in the selected KWB file, "
                "so this graph uses the share of low-access neighbourhoods instead. "
                "This still supports policy targeting because it shows whether the municipality contains many neighbourhoods with weak Bike-10 access."
            )
            st.warning(
                "Low-income share is not available for this selected municipality in the KWB file. "
                "Showing access score versus low-access-neighbourhood share instead."
            )

        fig = px.scatter(
            base,
            x=x_col,
            y="access_score",
            size="population",
            color="is_selected",
            hover_name="municipality",
            title=title_text,
            labels={
                x_col: x_label,
                "access_score": "Continuous Bike-10 access score (0-100)",
                "is_selected": "Municipality"
            },
            color_discrete_map={
                "Other municipalities": "#CBD5E1",
                f"Selected: {selected_muni}": "#2563EB"
            }
        )
        fig.add_hline(y=50, line_dash="dash")

        selected_for_text = selected_muni_row.dropna(subset=[x_col, "access_score"]).copy()
        if not selected_for_text.empty:
            fig.add_trace(
                px.scatter(
                    selected_for_text,
                    x=x_col,
                    y="access_score",
                    text="municipality"
                ).data[0]
            )
            fig.update_traces(textposition="top center", selector={"mode": "markers+text"})

        fig.update_layout(legend_title_text="Municipality")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(caption_text)

    elif index == 1:
        # Selected municipality function audit compared with the national mean.
        selected_scores = pd.DataFrame({
            "Amenity": ["GP / doctor", "Large supermarket", "Childcare", "School distance", "Schools within 3 km"],
            "Selected municipality": [
                selected_neigh_local["score_gp"].mean(),
                selected_neigh_local["score_supermarket"].mean(),
                selected_neigh_local["score_childcare"].mean(),
                selected_neigh_local["score_school_distance"].mean(),
                selected_neigh_local["score_schools_within_3km"].mean(),
            ],
            "National average": [
                kwb_neigh["score_gp"].mean(),
                kwb_neigh["score_supermarket"].mean(),
                kwb_neigh["score_childcare"].mean(),
                kwb_neigh["score_school_distance"].mean(),
                kwb_neigh["score_schools_within_3km"].mean(),
            ]
        })
        long_scores = selected_scores.melt(
            id_vars="Amenity",
            value_vars=["Selected municipality", "National average"],
            var_name="Comparison",
            value_name="Access score"
        )
        fig = px.bar(
            long_scores,
            x="Access score",
            y="Amenity",
            color="Comparison",
            barmode="group",
            orientation="h",
            title=f"Essential function audit for {selected_muni}",
            labels={"Access score": "Mean continuous access score (0-100)"},
            color_discrete_map={"Selected municipality": "#2563EB", "National average": "#94A3B8"}
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "This graph changes with the selected municipality and shows which essential functions are weaker locally compared with the national average."
        )

    elif index == 2:
        top = selected_neigh_local.sort_values("bike10_access_score").head(20)
        fig = px.bar(
            top,
            x="bike10_access_score",
            y="regio",
            orientation="h",
            color="p_ink_li",
            title=f"Lowest-access neighbourhoods in {selected_muni}",
            labels={"bike10_access_score": "Access score", "regio": "Neighbourhood", "p_ink_li": "Low-income share (%)"}
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("This graph changes with the selected municipality and gives the most direct local targeting list for interventions.")

    elif index == 3:
        if selected_neigh_local.empty:
            st.warning("No neighbourhood rows found for the selected municipality.")
            return

        if has_enough_numeric(selected_neigh_local["p_ink_li"], min_count=3):
            fig = px.scatter(
                selected_neigh_local,
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
                "This graph changes with the selected municipality and checks whether lower-access neighbourhoods also have higher low-income shares."
            )
        else:
            st.warning(
                "Neighbourhood-level low-income share is missing or too sparse for this municipality. "
                "Showing neighbourhood access ranking instead."
            )
            ranked = selected_neigh_local.sort_values("bike10_access_score").head(25)
            fig = px.bar(
                ranked,
                x="bike10_access_score",
                y="regio",
                orientation="h",
                color="ste_mvs",
                title=f"Neighbourhood access ranking in {selected_muni}",
                labels={
                    "bike10_access_score": "Bike-10 access score (0-100)",
                    "regio": "Neighbourhood",
                    "ste_mvs": "Urbanisation code"
                }
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "Because income values are missing here, the graph focuses on where access itself is weakest within the municipality."
            )

    elif index in [4, 5, 6, 7]:
        st.markdown(
            "<div class='hint'>The next graph uses detailed ODiN low-income summaries. "
            "ODiN is not municipality-specific in this MVP, so changing municipality will not change this graph. "
            "Use it as low-income behavioural context for the selected municipality.</div>",
            unsafe_allow_html=True
        )
        if odin_path is None:
            st.warning("Detailed ODiN file is missing. Put ODiN2024_DANS_Databestand_ Updated.xlsx in datasets/.")
            return
        with st.spinner("Loading low-income ODiN summaries. First run can take time, but it is cached after that..."):
            odin = load_odin_low_income_summaries(str(odin_path), odin_sheet, file_mtime(odin_path), str(DATASETS_DIR))
        st.caption(f"ODiN filter: lowest HHGestInkG group = {odin['lowest_income_value']}; filtered rows = {odin['n_rows']:,}.")

        if index == 4:
            fig = px.bar(
                odin["national_mode"].sort_values("share"),
                x="share",
                y="mode_class",
                orientation="h",
                title="Lowest-income group: national mode choice",
                labels={"share": "Weighted mode share (%)", "mode_class": "Mode"}
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption("This graph focuses only on the lowest income group and shows whether car, bike, or public transport dominates overall.")

        elif index == 5:
            fig = px.bar(
                odin["within10_mode"].sort_values("share"),
                x="share",
                y="mode_class",
                orientation="h",
                title="Lowest-income group: mode choice for trips within first 10 minutes",
                labels={"share": "Weighted mode share within <=10 min trips (%)", "mode_class": "Mode"}
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption("This uses Reisduur <= 10 so the comparison is equal across transport modes, not based only on 3 km cycling distance.")

        elif index == 6:
            fig = px.bar(
                odin["purpose_mode"],
                x="share",
                y="MotiefV_label",
                color="mode_class",
                orientation="h",
                title="Lowest-income group: mode choice by trip purpose",
                labels={"share": "Weighted mode share within purpose (%)", "MotiefV_label": "Trip purpose", "mode_class": "Mode"}
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption("This shows for which purposes low-income travellers rely more on car, bike, or public transport.")

        elif index == 7:
            fig = px.bar(
                odin["urban_mode"],
                x="share",
                y="Sted_label",
                color="mode_class",
                orientation="h",
                title="Lowest-income group: mode choice by urbanisation",
                labels={"share": "Weighted mode share within urbanisation class (%)", "Sted_label": "Urbanisation", "mode_class": "Mode"}
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption("This links low-income mode choice to spatial context, which is important because access and car dependency vary strongly by urbanisation.")

    elif index == 8:
        st.markdown(
            "<div class='hint'>The Bike Trip purpose file is an aggregated cycling-context dataset, not municipality-specific. "
            "Changing municipality will not change this graph.</div>",
            unsafe_allow_html=True
        )
        if bike_context is None:
            st.warning("Bike_Trip purpose.xlsx was not found or could not be read.")
            return
        tab_a, tab_b = st.tabs(["Essential cycling within 3 km", "Purpose by bike type"])
        with tab_a:
            fig = px.bar(
                bike_context["by_bike"],
                x="Bike type (main mode)",
                y="share_within_3km",
                title="Share of essential cycling trips within 3 km by bike type",
                labels={"share_within_3km": "% essential cycling trips within 3 km"}
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
        st.caption("This is the lighter ODiN-derived context file used to interpret cycling behaviour by trip purpose.")

render_graph(st.session_state.graph_index)

# ============================================================
# 10. Scenario + Gemini assistant
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
    • Give me a short policy recommendation for a presentation slide.
    </div>
    """,
    unsafe_allow_html=True
)

scenario_gain = 0
if scenario_type == "Add grocery / supermarket":
    scenario_gain = 8
elif scenario_type == "Add GP / healthcare":
    scenario_gain = 8
elif scenario_type == "Add school / childcare access":
    scenario_gain = 8
elif scenario_type == "Improve cycling accessibility by 10%":
    scenario_gain = 10
elif scenario_type == "Improve cycling accessibility by 20%":
    scenario_gain = 20

scenario_access = min(100, access_score + scenario_gain)
scenario_case = classify_policy_case(scenario_access, low_income_share)

s1, s2, s3 = st.columns(3)
s1.metric("Selected scenario", scenario_type)
s2.metric("Scenario access score", f"{scenario_access:.1f}/100", delta=f"+{scenario_gain}" if scenario_gain else "0")
s3.metric("Scenario case", scenario_case)

income_context_text = fmt_pct(low_income_share)
context_text = f"""
Selected municipality: {selected_muni}
Current continuous Bike-10 access score: {access_score:.1f}/100
Current policy case: {policy_case}
Low-income resident share from CBS KWB: {income_context_text}
Share of low-access neighbourhoods in municipality: {low_access_share:.1f}%
Number of neighbourhoods: {int(row['n_neighbourhoods'])}
Scenario: {scenario_type}
Scenario access score: {scenario_access:.1f}/100
Scenario policy case: {scenario_case}
Dashboard interpretation:
- This dashboard focuses on low-income residents.
- CBS KWB gives amenity access and low-income context.
- Detailed ODiN gives low-income mode choice patterns nationally/by purpose/by urbanisation.
- Bike Trip purpose gives cycling-purpose context.
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
st.caption("MVP dashboard. KWB is used for accessibility and low-income context; detailed ODiN is loaded lazily and cached for low-income mode-choice summaries; Gemini explains scenario trade-offs.")
