from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from .agent import summarize_scenario
from .data_loader import (
    AMENITY_LABELS,
    get_neighborhood_options,
    load_model,
    load_neighborhood_data,
    load_scenario_trips,
    parse_buurtcode,
)


INTERVENTIONS = {
    "Add supermarket": "bike10_klasse_supermarkt",
    "Add GP/doctor": "bike10_klasse_huisarts",
    "Add primary school": "bike10_klasse_basisschool",
    "Improve cycling infrastructure": "access_usage_gap",
    "Reduce car dependency": "HHAuto_DANS24",
}


MODE_ORDER = [
    "Car-driver",
    "Car-passenger",
    "Train",
    "Bus/tram/metro",
    "Bike",
    "Walking",
]


def run_proxy_scenario(row: pd.Series, intervention: str) -> dict:
    baseline_access = float(row["bike10_weighted_score"])
    baseline_bike = float(row["pct_bike"])
    scenario_access = baseline_access
    intervention_note = "No modeled access change."

    changed_feature = INTERVENTIONS[intervention]
    if changed_feature and changed_feature.startswith("bike10_klasse_"):
        current_class = float(row.get(changed_feature, 0) or 0)
        if current_class <= 0:
            scenario_access = min(100.0, baseline_access + 8.0)
            intervention_note = "The selected amenity is currently missing, so the proxy adds local access."
        elif current_class < 2:
            scenario_access = min(100.0, baseline_access + 4.0)
            intervention_note = "The amenity is present but weakly represented, so the proxy adds a smaller access gain."
        else:
            intervention_note = "The amenity is already strongly represented, so no access gain is applied."
    elif intervention == "Improve cycling infrastructure":
        scenario_access = min(100.0, baseline_access + 15.0)
        intervention_note = "The proxy increases the cycling accessibility score directly."
    elif intervention == "Reduce car dependency":
        intervention_note = "The proxy shifts a small share of non-bike trips towards cycling."

    if intervention == "Reduce car dependency":
        delta_bike = min(5.0, max(1.0, (100.0 - baseline_bike) * 0.04))
    elif scenario_access > baseline_access:
        gap_to_access = max(0.0, scenario_access - baseline_bike)
        delta_bike = min(6.0, gap_to_access * 0.12)
    else:
        delta_bike = 0.0

    scenario_bike = min(100.0, baseline_bike + delta_bike)
    baseline_other = max(0.0, 100.0 - baseline_bike)
    scenario_other = max(0.0, 100.0 - scenario_bike)

    return {
        "method": "transparent proxy estimate",
        "buurtcode": row["buurtcode"],
        "buurtnaam": row["buurtnaam"],
        "gemeentenaam": row["gemeentenaam"],
        "intervention": intervention,
        "changed_feature": changed_feature,
        "intervention_note": intervention_note,
        "baseline_access_score": round(baseline_access, 1),
        "scenario_access_score": round(scenario_access, 1),
        "baseline_bike_share": round(baseline_bike, 1),
        "scenario_bike_share": round(scenario_bike, 1),
        "delta_bike_share_pp": round(scenario_bike - baseline_bike, 1),
        "baseline_other_share": round(baseline_other, 1),
        "scenario_other_share": round(scenario_other, 1),
    }


def _weighted_mode_shares(probabilities: np.ndarray, weights: pd.Series, labels: list[str]) -> dict[str, float]:
    weights = pd.to_numeric(weights, errors="coerce").fillna(1.0).to_numpy()
    if weights.sum() <= 0:
        weights = np.ones_like(weights)
    shares = np.average(probabilities, axis=0, weights=weights) * 100
    return {label: round(float(share), 1) for label, share in zip(labels, shares)}


def run_model_scenario(row: pd.Series, intervention: str, model, metadata: dict) -> tuple[dict, str | None]:
    feature_columns = metadata.get("feature_columns", [])
    if not feature_columns:
        return run_proxy_scenario(row, intervention), "Model metadata does not contain feature columns."

    trips = load_scenario_trips(feature_columns)
    if trips.empty:
        return run_proxy_scenario(row, intervention), "Representative ODiN trip data could not be built."

    buurtcode = str(row["buurtcode"])
    gm_code = str(row["gm_code"])
    sample = trips[trips["buurtcode"].astype(str).eq(buurtcode)].copy()
    sample_scope = "neighborhood"
    if len(sample) < 30:
        sample = trips[trips["gm_code"].astype(str).eq(gm_code)].copy()
        sample_scope = "municipality fallback"
    if len(sample) < 30:
        return run_proxy_scenario(row, intervention), "Fewer than 30 representative ODiN trips were available."
    if len(sample) > 3000:
        sample = sample.sample(3000, random_state=42)

    changed_feature = INTERVENTIONS[intervention]
    if changed_feature not in feature_columns:
        warning = (
            f"`{changed_feature}` is not in the exported Topic 2 feature set, so this intervention cannot "
            "be passed through the XGBoost model. The baseline prediction is shown unchanged."
        )
    else:
        warning = None

    baseline_x = sample[feature_columns].copy()
    scenario_x = baseline_x.copy()
    baseline_access = float(row["bike10_weighted_score"])
    scenario_access = baseline_access
    intervention_note = "The intervention was applied to the exported XGBoost feature matrix."

    if warning is None:
        if changed_feature.startswith("bike10_klasse_"):
            before = pd.to_numeric(scenario_x[changed_feature], errors="coerce").fillna(0)
            scenario_x[changed_feature] = np.maximum(before, 1)
            if before.max() >= 1 and before.min() >= 1:
                intervention_note = "The selected amenity was already present in the representative trips."
            else:
                scenario_access = min(100.0, baseline_access + 8.0)
        elif intervention == "Improve cycling infrastructure":
            scenario_x[changed_feature] = pd.to_numeric(scenario_x[changed_feature], errors="coerce").fillna(0) + 15
            scenario_access = min(100.0, baseline_access + 15.0)
        elif intervention == "Reduce car dependency":
            cars = pd.to_numeric(scenario_x[changed_feature], errors="coerce").fillna(0)
            scenario_x[changed_feature] = np.maximum(cars - 1, 0)

    baseline_prob = model.predict_proba(baseline_x)
    scenario_prob = model.predict_proba(scenario_x)
    labels = [metadata.get("target_classes", {}).get(str(i), MODE_ORDER[i]) for i in range(baseline_prob.shape[1])]
    baseline_shares = _weighted_mode_shares(baseline_prob, sample["FactorV"], labels)
    scenario_shares = _weighted_mode_shares(scenario_prob, sample["FactorV"], labels)
    bike_label = "Bike" if "Bike" in baseline_shares else labels[min(4, len(labels) - 1)]

    return {
        "method": "Topic 2 XGBoost mode-choice model",
        "sample_scope": sample_scope,
        "sample_size": int(len(sample)),
        "buurtcode": row["buurtcode"],
        "buurtnaam": row["buurtnaam"],
        "gemeentenaam": row["gemeentenaam"],
        "intervention": intervention,
        "changed_feature": changed_feature,
        "intervention_note": intervention_note,
        "baseline_access_score": round(baseline_access, 1),
        "scenario_access_score": round(scenario_access, 1),
        "baseline_bike_share": baseline_shares.get(bike_label, 0.0),
        "scenario_bike_share": scenario_shares.get(bike_label, 0.0),
        "delta_bike_share_pp": round(scenario_shares.get(bike_label, 0.0) - baseline_shares.get(bike_label, 0.0), 1),
        "baseline_mode_shares": baseline_shares,
        "scenario_mode_shares": scenario_shares,
    }, warning


def render() -> None:
    df = load_neighborhood_data()
    model, metadata = load_model()
    st.subheader("What-If Scenario Builder")

    options = get_neighborhood_options(df)
    selected_label = st.sidebar.selectbox("Neighborhood", options)
    buurtcode = parse_buurtcode(selected_label)
    intervention = st.sidebar.selectbox("Intervention", list(INTERVENTIONS))
    st.session_state["selected_buurt"] = buurtcode

    row = df.loc[df["buurtcode"] == buurtcode].iloc[0]
    if model is None:
        st.warning(
            "No exported Topic 2 model artifact was found in `dashboard/data`. "
            "The scenario below uses a transparent proxy estimate, not an XGBoost prediction."
        )
    else:
        st.info(
            "Topic 2 model artifact loaded. Scenarios use representative ODiN origin trips and fall back "
            "to the municipality level when a neighborhood has fewer than 30 linked trips."
        )

    if st.sidebar.button("Run Scenario", type="primary"):
        if model is None:
            result = run_proxy_scenario(row, intervention)
            warning = None
        else:
            with st.spinner("Running Topic 2 model scenario..."):
                result, warning = run_model_scenario(row, intervention, model, metadata)
        if warning:
            st.warning(warning)

        c1, c2, c3 = st.columns(3)
        c1.metric("Baseline cycling share", f"{result['baseline_bike_share']:.1f}%")
        c2.metric("Scenario cycling share", f"{result['scenario_bike_share']:.1f}%")
        c3.metric("Predicted change", f"{result['delta_bike_share_pp']:+.1f} pp")

        if "baseline_mode_shares" in result:
            shares = pd.DataFrame(
                [
                    {"Scenario": "Baseline", "Mode": mode, "Share": share}
                    for mode, share in result["baseline_mode_shares"].items()
                ]
                + [
                    {"Scenario": "Scenario", "Mode": mode, "Share": share}
                    for mode, share in result["scenario_mode_shares"].items()
                ]
            )
        else:
            shares = pd.DataFrame(
                {
                    "Scenario": ["Baseline", "Baseline", "Scenario", "Scenario"],
                    "Mode": ["Bike", "Other modes", "Bike", "Other modes"],
                    "Share": [
                        result["baseline_bike_share"],
                        result["baseline_other_share"],
                        result["scenario_bike_share"],
                        result["scenario_other_share"],
                    ],
                }
            )
        st.plotly_chart(
            px.bar(shares, x="Mode", y="Share", color="Scenario", barmode="group", range_y=[0, 100]),
            use_container_width=True,
        )

        st.write(summarize_scenario(result))
        st.json(result)
