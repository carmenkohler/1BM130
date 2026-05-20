# ============================================================
# Topic 3 - Minimum Product Urban Policy Dashboard
#
# Streamlit + Gemini AI assistant

#
# Required main CSV:
# - area name column:
#   municipality / Gemeentenaam / gm_naam / region / buurt / WijkenEnBuurten
#
# - access score column:
#   essential_access_score / bike10_weighted_score / access_score / bike10_score
#
# Optional but useful:
# - usage column:
#   usage_score / pct_within_3km / local_cycling_usage / cycling_usage
#
# - amenity/audit columns:
#   columns starting with access_
#   or columns containing school, supermarket, huisarts, gp, pharmacy, station, distance, afstand
#
# Optional Topic 2 mode-choice CSV:
# - region / RegioS_title
# - mode / mode_class
# - mode_share / share
#
# Run:
# streamlit run topic3_dashboard.py
# ============================================================

from pathlib import Path
import re
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

try:
    from google import genai
except Exception:
    genai = None


# ============================================================
# 0. App setup
# ============================================================

st.set_page_config(
    page_title="10-Minute Cycling City Policy Dashboard",
    layout="wide"
)

WORKSPACE = Path(__file__).resolve().parent


# ============================================================
# 1. Gemini API key
# ============================================================

# Paste your Gemini API key here.
# Example:
# GEMINI_API_KEY = "AIzaSy..."
GEMINI_API_KEY = "PASTE_YOUR_GEMINI_API_KEY_HERE"


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


def find_col(df, patterns):
    for pat in patterns:
        matches = [c for c in df.columns if re.search(pat, str(c), re.IGNORECASE)]
        if matches:
            return matches[0]
    return None


def normalize_name(x):
    if pd.isna(x):
        return ""
    x = str(x).lower().strip()
    x = re.sub(r"\s+", " ", x)
    return x


def make_basic_usage_proxy(access_score):
    """
    Tiny fallback scenario model.

    This is NOT the predictive model.
    It only creates a dashboard demonstration value when no observed usage
    variable exists in the selected CSV.
    """
    if pd.isna(access_score):
        return np.nan
    return max(0, min(100, 35 + 0.35 * access_score))


def classify_policy_case(access_score, usage_score):
    if pd.isna(access_score) or pd.isna(usage_score):
        return "insufficient data"

    if access_score >= 70 and usage_score >= 60:
        return "high access / high usage"

    if access_score >= 70 and usage_score < 60:
        return "high access / low usage"

    if access_score < 70 and usage_score >= 60:
        return "low access / high usage"

    return "low access / low usage"


def recommendation_from_case(case):
    if case == "high access / high usage":
        return (
            "Maintain current cycling conditions and protect existing accessibility. "
            "This area already performs well as a 10-minute cycling environment."
        )

    if case == "high access / low usage":
        return (
            "Focus on cycling conditions and behaviour rather than only adding amenities. "
            "Possible actions include safer routes, better crossings, bicycle parking, lighting, and more direct cycling links."
        )

    if case == "low access / high usage":
        return (
            "There is cycling demand despite weaker access. "
            "Adding amenities or improving direct connections could create strong benefits."
        )

    if case == "low access / low usage":
        return (
            "This area needs both spatial and mobility interventions. "
            "Improve access to essential services and make cycling safer and more convenient."
        )

    return "More data is needed before making a targeted recommendation."


def ask_gemini(prompt):
    api_key = GEMINI_API_KEY.strip()

    if not api_key or api_key == "PASTE_YOUR_GEMINI_API_KEY_HERE" or genai is None:
        return None

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    return response.text


def fallback_policy_answer(context_text, user_question):
    return f"""
Based on the selected dashboard context, the main policy interpretation is:

{context_text}

For your question: "{user_question}"

A practical recommendation is to first identify whether the area is mainly an access problem or a usage problem.

If access is low, focus on improving connections to essential amenities or adding missing daily services.
If access is high but usage is low, focus on cycling attractiveness: safety, direct routes, crossings, lighting, and parking.
"""


def list_workspace_csvs():
    """
    Find CSV files inside the project workspace.
    Keeps paths relative so they look clean in the UI.
    """
    csv_files = sorted(WORKSPACE.glob("**/*.csv"))

    # Avoid hidden/system folders and very irrelevant cache internals if desired.
    cleaned = []
    for p in csv_files:
        parts = [part.lower() for part in p.parts]
        if ".git" in parts or "__pycache__" in parts:
            continue
        cleaned.append(p)

    return cleaned


def read_local_csv(path):
    path = Path(path)

    try:
        df = pd.read_csv(path, low_memory=False)
        if df.shape[1] == 1:
            df = pd.read_csv(path, sep=";", low_memory=False)
        return df

    except UnicodeDecodeError:
        try:
            return pd.read_csv(path, sep=";", encoding="latin1", low_memory=False)
        except Exception:
            return pd.read_csv(path, encoding="latin1", low_memory=False)

    except Exception as e:
        st.error(f"Could not read CSV file: {path}\n\nError: {e}")
        return pd.DataFrame()


def detect_topic3_main_columns(df):
    area_col = find_col(df, [
        r"municipality",
        r"Gemeentenaam",
        r"gm_naam",
        r"gemeente",
        r"region",
        r"RegioS_title",
        r"Regio",
        r"buurt",
        r"WijkenEnBuurten",
        r"wijk"
    ])

    access_col = find_col(df, [
        r"essential_access_score",
        r"bike10_weighted_score",
        r"bike10_access_score",
        r"access_score",
        r"bike10_score",
        r"access"
    ])

    usage_col = find_col(df, [
        r"usage_score",
        r"estimated_usage_score",
        r"pct_within_3km",
        r"local_cycling_usage",
        r"cycling_usage",
        r"usage",
        r"mode_share"
    ])

    income_col = find_col(df, [
        r"income",
        r"inkomen",
        r"p_ink_li",
        r"low_income",
        r"laagste",
        r"laag.*inkomen"
    ])

    urban_col = find_col(df, [
        r"urban",
        r"stedelijkheid",
        r"MateVanStedelijkheid",
        r"urbanisation",
        r"urbanization"
    ])

    audit_cols = [
        c for c in df.columns
        if str(c).startswith("access_")
        or re.search(
            r"dist_|distance|afstand|school|supermarket|supermarkt|huisarts|gp|doctor|pharmacy|apotheek|station|hospital|ziekenhuis",
            str(c),
            re.IGNORECASE
        )
    ]

    return {
        "area_col": area_col,
        "access_col": access_col,
        "usage_col": usage_col,
        "income_col": income_col,
        "urban_col": urban_col,
        "audit_cols": audit_cols
    }


def validate_topic3_main_file(df, detected):
    errors = []
    warnings = []

    if df.empty:
        errors.append("The selected CSV is empty or could not be read.")

    if detected["area_col"] is None:
        errors.append(
            "No area-name column found. Expected one of: municipality, Gemeentenaam, gm_naam, region, buurt, WijkenEnBuurten."
        )

    if detected["access_col"] is None:
        errors.append(
            "No access-score column found. Expected one of: essential_access_score, bike10_weighted_score, access_score, bike10_score."
        )

    if detected["usage_col"] is None:
        warnings.append(
            "No observed usage column found. The dashboard will create a simple estimated usage score from the access score."
        )

    if len(detected["audit_cols"]) == 0:
        warnings.append(
            "No amenity audit columns found. The Essential Function Audit will be limited."
        )

    return errors, warnings


def standardize_topic3_main_file(df, detected):
    out = df.copy()

    out = out.rename(columns={
        detected["area_col"]: "area_name",
        detected["access_col"]: "access_score"
    })

    out["area_name"] = out["area_name"].astype(str)
    out["access_score"] = clean_numeric(out["access_score"])

    if out["access_score"].max(skipna=True) <= 1.5:
        out["access_score"] = out["access_score"] * 100

    if detected["usage_col"] is not None:
        out = out.rename(columns={detected["usage_col"]: "usage_score"})
        out["usage_score"] = clean_numeric(out["usage_score"])

        if out["usage_score"].max(skipna=True) <= 1.5:
            out["usage_score"] = out["usage_score"] * 100
    else:
        out["usage_score"] = out["access_score"].apply(make_basic_usage_proxy)

    if detected["income_col"] is not None:
        out = out.rename(columns={detected["income_col"]: "income_context"})
    else:
        out["income_context"] = np.nan

    if detected["urban_col"] is not None:
        out = out.rename(columns={detected["urban_col"]: "urbanisation_context"})
    else:
        out["urbanisation_context"] = np.nan

    out["area_norm"] = out["area_name"].apply(normalize_name)

    out = out.dropna(subset=["area_name", "access_score"]).copy()

    return out


def detect_topic2_columns(df):
    region_col = find_col(df, [
        r"region",
        r"RegioS_title",
        r"Regio",
        r"gebied"
    ])

    mode_col = find_col(df, [
        r"mode_class",
        r"mode",
        r"vervoer",
        r"Vervoerwijzen"
    ])

    share_col = find_col(df, [
        r"mode_share",
        r"share",
        r"percentage",
        r"value"
    ])

    return {
        "region_col": region_col,
        "mode_col": mode_col,
        "share_col": share_col
    }


def validate_topic2_file(df, detected):
    errors = []
    warnings = []

    if df.empty:
        errors.append("The selected Topic 2 CSV is empty or could not be read.")

    if detected["region_col"] is None:
        errors.append("No region column found. Expected: region, RegioS_title, Regio.")

    if detected["mode_col"] is None:
        errors.append("No mode column found. Expected: mode, mode_class, Vervoerwijzen.")

    if detected["share_col"] is None:
        errors.append("No mode share column found. Expected: mode_share, share, percentage, value.")

    return errors, warnings


def standardize_topic2_file(df, detected):
    out = df.copy()

    out = out.rename(columns={
        detected["region_col"]: "region",
        detected["mode_col"]: "mode",
        detected["share_col"]: "mode_share"
    })

    out["region"] = out["region"].astype(str)
    out["mode"] = out["mode"].astype(str)
    out["mode_share"] = clean_numeric(out["mode_share"])

    if out["mode_share"].max(skipna=True) > 1.5:
        out["mode_share"] = out["mode_share"] / 100

    out = out.dropna(subset=["region", "mode", "mode_share"]).copy()

    return out


def show_detected_variables(title, df, detected):
    st.subheader(title)

    detected_table = []
    for k, v in detected.items():
        if isinstance(v, list):
            detected_table.append({
                "Expected relation": k,
                "Detected variable": ", ".join(v[:10]) + (" ..." if len(v) > 10 else "")
            })
        else:
            detected_table.append({
                "Expected relation": k,
                "Detected variable": v if v is not None else "NOT FOUND"
            })

    st.dataframe(pd.DataFrame(detected_table), use_container_width=True)

    with st.expander("Show all columns in selected file"):
        st.write(list(df.columns))

    with st.expander("Preview selected data"):
        st.dataframe(df.head(20), use_container_width=True)


# ============================================================
# 3. Header
# ============================================================

st.title("10-Minute Cycling City Policy Dashboard")
st.caption(
    "Minimum product interface for Topic 3: select local CSV data, inspect access and usage, run scenarios, and ask an AI policy assistant."
)

st.markdown(
    """
This dashboard translates the results from Topic 1 and Topic 2 into a practical decision-support tool.
Instead of uploading files, it scans your local project workspace and lets you select CSV files from a dropdown.
"""
)


# ============================================================
# 4. Local file selector
# ============================================================

st.header("0. Select local data files")

st.markdown(
    """
### What this dashboard needs

The main CSV should contain the relationships needed for Topic 3:

| Topic 3 component | Required relationship | Example variable names |
|---|---|---|
| Selected area | Municipality / neighborhood / region name | `municipality`, `Gemeentenaam`, `gm_naam`, `region`, `WijkenEnBuurten` |
| Access score | 10-minute cycling access to essential amenities | `essential_access_score`, `bike10_weighted_score`, `access_score`, `bike10_score` |
| Usage score | Local cycling usage or percentage within the bike-shed | `pct_within_3km`, `usage_score`, `local_cycling_usage` |
| Essential Function Audit | Amenity-specific access or distance variables | `access_supermarket`, `access_school`, `dist_gp`, `AfstandTotSchool` |
| Context | Income or urbanisation variables | `income`, `p_ink_li`, `stedelijkheid`, `urbanisation` |

If no usage score is found, the dashboard will still run using a simple estimated usage proxy.
"""
)

csv_files = list_workspace_csvs()

if not csv_files:
    st.error(
        f"No CSV files were found inside the workspace:\n\n{WORKSPACE}\n\n"
        "Put your CSV files in this folder or a subfolder, then refresh the Streamlit page."
    )
    st.stop()

csv_options = ["-- select a CSV file --"] + [str(p.relative_to(WORKSPACE)) for p in csv_files]

selected_main_rel = st.selectbox(
    "Select main Topic 3 access/access-usage CSV from local workspace",
    csv_options,
    index=0
)

selected_topic2_rel = st.selectbox(
    "Optional: select Topic 2 mode-choice CSV from local workspace",
    ["-- none --"] + [str(p.relative_to(WORKSPACE)) for p in csv_files],
    index=0
)

if selected_main_rel == "-- select a CSV file --":
    st.info("Select a main CSV file to start the dashboard.")
    st.stop()

main_path = WORKSPACE / selected_main_rel
st.write("Selected main CSV path:")
st.code(str(main_path))

main_df_raw = read_local_csv(main_path)

topic2_df_raw = pd.DataFrame()
if selected_topic2_rel != "-- none --":
    topic2_path = WORKSPACE / selected_topic2_rel
    st.write("Selected Topic 2 CSV path:")
    st.code(str(topic2_path))
    topic2_df_raw = read_local_csv(topic2_path)


# ============================================================
# 5. Validate selected files
# ============================================================

detected_main = detect_topic3_main_columns(main_df_raw)
errors_main, warnings_main = validate_topic3_main_file(main_df_raw, detected_main)

show_detected_variables("Main CSV variable detection", main_df_raw, detected_main)

if warnings_main:
    for w in warnings_main:
        st.warning(w)

if errors_main:
    st.error("This CSV does not match the minimum requirements for Topic 3.")
    for e in errors_main:
        st.error(e)
    st.info("Select another file from the dropdown above.")
    st.stop()

access_data = standardize_topic3_main_file(main_df_raw, detected_main)
st.success("Main CSV accepted. Dashboard can run with this file.")

topic2_ready = False
topic2_data = pd.DataFrame()

if selected_topic2_rel != "-- none --":
    detected_topic2 = detect_topic2_columns(topic2_df_raw)
    errors_topic2, warnings_topic2 = validate_topic2_file(topic2_df_raw, detected_topic2)

    show_detected_variables("Topic 2 CSV variable detection", topic2_df_raw, detected_topic2)

    if errors_topic2:
        st.error("The selected Topic 2 CSV does not match the expected format.")
        for e in errors_topic2:
            st.error(e)
        st.warning("The dashboard will continue without Topic 2 mode-choice data.")
    else:
        topic2_data = standardize_topic2_file(topic2_df_raw, detected_topic2)
        topic2_ready = True
        st.success("Topic 2 mode-choice CSV accepted.")


# ============================================================
# 6. Sidebar controls
# ============================================================

st.sidebar.title("Policy Dashboard Controls")

areas = sorted(access_data["area_name"].dropna().astype(str).unique())

selected_area = st.sidebar.selectbox(
    "Select municipality / neighborhood / region",
    areas
)

scenario_type = st.sidebar.selectbox(
    "What-if scenario",
    [
        "No scenario",
        "Add grocery / supermarket",
        "Add GP / healthcare",
        "Add school",
        "Improve cycling accessibility by 10%",
        "Improve cycling accessibility by 20%"
    ]
)

st.sidebar.markdown("---")
st.sidebar.write("LLM assistant status:")

if genai is not None and GEMINI_API_KEY.strip() != "PASTE_YOUR_GEMINI_API_KEY_HERE":
    st.sidebar.success("Gemini available")
elif genai is not None:
    st.sidebar.warning("Gemini package installed, but API key placeholder is not filled.")
else:
    st.sidebar.warning("Gemini package not installed. Using rule-based fallback.")


# ============================================================
# 7. Selected area summary
# ============================================================

st.header("1. Selected Area Summary")

selected_rows = access_data[access_data["area_name"] == selected_area]

if selected_rows.empty:
    st.error("Selected area not found in selected data.")
    st.stop()

selected_row = selected_rows.iloc[0]

access_score = float(selected_row["access_score"])
usage_score = float(selected_row["usage_score"]) if not pd.isna(selected_row["usage_score"]) else np.nan

policy_case = classify_policy_case(access_score, usage_score)
base_recommendation = recommendation_from_case(policy_case)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Bike-10 access score",
        f"{access_score:.1f}/100"
    )

with col2:
    st.metric(
        "Local usage score",
        f"{usage_score:.1f}/100" if not pd.isna(usage_score) else "No data"
    )

with col3:
    st.metric(
        "Policy case",
        policy_case
    )

st.info(base_recommendation)

with st.expander("Selected area raw row"):
    st.dataframe(selected_rows, use_container_width=True)


# ============================================================
# 8. Access-usage heatmap / scatter
# ============================================================

st.header("2. Access–Usage Heatmap")

plot_df = access_data.copy()

plot_df["policy_case"] = plot_df.apply(
    lambda r: classify_policy_case(r["access_score"], r["usage_score"]),
    axis=1
)

fig = px.scatter(
    plot_df,
    x="access_score",
    y="usage_score",
    color="policy_case",
    hover_name="area_name",
    title="Access–Usage relationship",
    labels={
        "access_score": "Bike-10 access score",
        "usage_score": "Local usage score",
        "policy_case": "Policy case"
    }
)

fig.add_vline(x=70, line_dash="dash")
fig.add_hline(y=60, line_dash="dash")

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "The dashed lines divide the dashboard into simple policy zones: high/low access and high/low usage. "
    "These are decision-support markers, not causal estimates."
)


# ============================================================
# 9. Essential Function Audit
# ============================================================

st.header("3. Essential Function Audit")

audit_cols = [
    c for c in main_df_raw.columns
    if str(c).startswith("access_")
    or re.search(
        r"dist_|distance|afstand|school|supermarket|supermarkt|huisarts|gp|doctor|pharmacy|apotheek|station|hospital|ziekenhuis",
        str(c),
        re.IGNORECASE
    )
]

if audit_cols:
    selected_audit_col = st.selectbox(
        "Choose amenity/access variable",
        audit_cols
    )

    audit_df = main_df_raw.copy()
    audit_df[selected_audit_col] = clean_numeric(audit_df[selected_audit_col])

    col_a, col_b = st.columns([1, 2])

    with col_a:
        st.write("Summary")
        st.write(audit_df[selected_audit_col].describe())

    with col_b:
        fig_audit = px.histogram(
            audit_df,
            x=selected_audit_col,
            nbins=30,
            title=f"Distribution of {selected_audit_col}"
        )
        st.plotly_chart(fig_audit, use_container_width=True)

else:
    st.warning(
        "No amenity audit variables were found in the selected CSV. "
        "Expected variables like access_supermarket, access_school, dist_gp, or AfstandTotSchool."
    )


# ============================================================
# 10. What-if scenario builder
# ============================================================

st.header("4. What-if Scenario Builder")

scenario_gain = 0

if scenario_type == "Add grocery / supermarket":
    scenario_gain = 8
elif scenario_type == "Add GP / healthcare":
    scenario_gain = 8
elif scenario_type == "Add school":
    scenario_gain = 8
elif scenario_type == "Improve cycling accessibility by 10%":
    scenario_gain = 10
elif scenario_type == "Improve cycling accessibility by 20%":
    scenario_gain = 20

scenario_access = min(100, access_score + scenario_gain)

if not pd.isna(usage_score):
    scenario_usage = min(100, usage_score + scenario_gain * 0.35)
else:
    scenario_usage = make_basic_usage_proxy(scenario_access)

scenario_case = classify_policy_case(scenario_access, scenario_usage)
scenario_recommendation = recommendation_from_case(scenario_case)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Scenario access score",
        f"{scenario_access:.1f}/100",
        delta=f"+{scenario_gain}" if scenario_gain > 0 else "0"
    )

with col2:
    delta_usage = scenario_usage - usage_score if not pd.isna(usage_score) else np.nan
    st.metric(
        "Scenario usage score",
        f"{scenario_usage:.1f}/100",
        delta=f"{delta_usage:.1f}" if not pd.isna(delta_usage) else None
    )

with col3:
    st.metric(
        "Scenario policy case",
        scenario_case
    )

st.write("Scenario recommendation:")
st.success(scenario_recommendation)


# ============================================================
# 11. Topic 2 mode-choice outputs
# ============================================================

st.header("5. Lowest-Income Mode Choice Context")

if topic2_ready and not topic2_data.empty:
    fig_region = px.bar(
        topic2_data,
        x="mode_share",
        y="region",
        color="mode",
        orientation="h",
        title="Lowest-income mode share by region",
        labels={
            "mode_share": "Mode share",
            "region": "Region",
            "mode": "Mode"
        }
    )
    st.plotly_chart(fig_region, use_container_width=True)

    with st.expander("Topic 2 mode-choice data"):
        st.dataframe(topic2_data, use_container_width=True)

else:
    st.warning(
        "No valid Topic 2 mode-choice CSV was selected. "
        "This section is optional, but useful for connecting the dashboard to the predictive modelling phase."
    )


# ============================================================
# 12. AI Agent Policy Assistant
# ============================================================

st.header("6. AI-Agent Policy Assistant")

context_text = f"""
Selected area: {selected_area}
Current Bike-10 access score: {access_score:.1f} out of 100
Current local usage score: {usage_score:.1f} out of 100
Current policy case: {policy_case}
Current recommendation: {base_recommendation}

Scenario selected: {scenario_type}
Scenario access score: {scenario_access:.1f} out of 100
Scenario usage score: {scenario_usage:.1f} out of 100
Scenario policy case: {scenario_case}
Scenario recommendation: {scenario_recommendation}

Interpretation rules:
- High access and low usage means cycling conditions or behaviour may be the issue.
- Low access means amenity availability or direct cycling connections may be the issue.
- Urbanisation and car dependency can affect whether nearby amenities become actual cycling trips.
- The assistant should support policy interpretation and not claim causal proof.
"""

st.write("Ask a question such as:")
st.code("What intervention is most useful here?")
st.code("Explain the trade-off between adding amenities and improving cycling routes.")
st.code("Give me a short policy recommendation for this area.")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for role, message in st.session_state.chat_history:
    with st.chat_message(role):
        st.write(message)

user_question = st.chat_input("Ask the policy assistant...")

if user_question:
    st.session_state.chat_history.append(("user", user_question))

    with st.chat_message("user"):
        st.write(user_question)

    prompt = f"""
You are an urban mobility policy assistant for a 10-minute cycling city dashboard.

Use only the dashboard context below.
Do not invent exact numbers beyond the given values.
Do not claim causal proof.
Give concise, policy-oriented advice.

Dashboard context:
{context_text}

User question:
{user_question}

Answer in this structure:
1. Interpretation
2. Trade-off
3. Recommended policy action
"""

    ai_answer = ask_gemini(prompt)

    if ai_answer is None:
        ai_answer = fallback_policy_answer(context_text, user_question)

    st.session_state.chat_history.append(("assistant", ai_answer))

    with st.chat_message("assistant"):
        st.write(ai_answer)


# ============================================================
# 13. Footer
# ============================================================

st.markdown("---")
st.caption(
    "MVP dashboard. The AI assistant explains model outputs and scenario results; it does not replace the predictive models."
)
