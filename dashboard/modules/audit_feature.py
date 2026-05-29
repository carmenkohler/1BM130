from __future__ import annotations

import plotly.express as px
import streamlit as st

from .data_loader import ACCESS_METHOD_NOTE, AMENITY_COLUMNS, AMENITY_LABELS, CORE_ACCESS_COLUMNS, load_neighborhood_data


URBANISATION_LABELS = {
    1: "Very urban",
    2: "Urban",
    3: "Moderately urban",
    4: "Low urban",
    5: "Rural",
}

INCOME_GROUP_LABELS = {
    "1-2": "Lowest income areas",
    "3-4": "Lower-middle income areas",
    "5-6": "Middle income areas",
    "7-8": "Higher-middle income areas",
    "9-10": "Highest income areas",
}

ACCESS_COLORS = {
    "Within 10-min bike access": "#2e7d32",
    "No 10-min bike access": "#c62828",
}


def _income_group(decile):
    if decile <= 2:
        return "1-2"
    if decile <= 4:
        return "3-4"
    if decile <= 6:
        return "5-6"
    if decile <= 8:
        return "7-8"
    return "9-10"


def render() -> None:
    df = load_neighborhood_data()
    st.subheader("Equity Audit")
    st.caption(
        f"{ACCESS_METHOD_NOTE} The audit can also inspect broader mobility-support amenities such as transit stops "
        "and pharmacies, consistent with the Topic 1 access setup."
    )
    st.warning(
        "Data coverage note: the provided destination data has supermarkets, GP practices, primary schools, "
        "secondary schools and hospitals, but no separate MBO or HBO/WO destinations. Those education "
        "destinations should be added from another source before making final higher-education access claims."
    )

    amenity = st.sidebar.selectbox(
        "Destination to audit",
        AMENITY_COLUMNS,
        format_func=lambda col: AMENITY_LABELS.get(col, col),
    )
    label = AMENITY_LABELS.get(amenity, amenity)
    if amenity in CORE_ACCESS_COLUMNS:
        st.info(f"{label} is part of the Topic 1 weighted access score.")
    else:
        st.info(f"{label} is included in the broader Topic 1 access setup, with a lower policy weight.")
    audited = df.copy()
    audited["has_access"] = audited[amenity].fillna(0).gt(0)
    audited["Access"] = audited["has_access"].map({True: "Within 10-min bike access", False: "No 10-min bike access"})
    audited["Urbanisation"] = audited["Sted"].map(URBANISATION_LABELS)
    audited["Income group"] = audited["HHGestInkG"].dropna().astype(int).map(_income_group).map(INCOME_GROUP_LABELS)

    c1, c2, c3 = st.columns(3)
    c1.metric("Neighborhoods checked", f"{len(audited):,}")
    c2.metric(f"Can reach a {label.lower()}", f"{audited['has_access'].mean() * 100:.1f}%")
    c3.metric(f"Cannot reach a {label.lower()}", f"{(1 - audited['has_access'].mean()) * 100:.1f}%")
    st.caption(
        "Green means at least one destination is reachable by bike. Red means no such destination is available "
        "for that neighborhood in the current data."
    )

    by_urban = (
        audited.dropna(subset=["Urbanisation"])
        .groupby(["Urbanisation", "has_access"], as_index=False)
        .size()
    )
    by_urban["share"] = by_urban.groupby("Urbanisation")["size"].transform(lambda s: s / s.sum() * 100)
    by_urban["Access"] = by_urban["has_access"].map({True: "Within 10-min bike access", False: "No 10-min bike access"})
    by_urban["Urbanisation"] = by_urban["Urbanisation"].astype(
        "category"
    ).cat.set_categories(list(URBANISATION_LABELS.values()), ordered=True)
    by_urban["Label"] = by_urban["share"].round(0).astype(int).astype(str) + "%"

    has_income = audited["HHGestInkG"].notna().any()
    if has_income:
        by_income = (
            audited.dropna(subset=["Income group"])
            .groupby(["Income group", "has_access"], as_index=False)
            .size()
        )
        by_income["share"] = by_income.groupby("Income group")["size"].transform(lambda s: s / s.sum() * 100)
        by_income["Access"] = by_income["has_access"].map({True: "Within 10-min bike access", False: "No 10-min bike access"})
        by_income["Income group"] = by_income["Income group"].astype(
            "category"
        ).cat.set_categories(list(INCOME_GROUP_LABELS.values()), ordered=True)
        by_income["Label"] = by_income["share"].round(0).astype(int).astype(str) + "%"

    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(
            by_urban.sort_values("Urbanisation"),
            x="Urbanisation",
            y="share",
            color="Access",
            barmode="group",
            text="Label",
            color_discrete_map=ACCESS_COLORS,
            labels={"Urbanisation": "Type of area", "share": "Share of neighborhoods (%)"},
            title=f"Where {label.lower()} access is missing",
        )
        fig.update_layout(legend_title_text="", yaxis_range=[0, 100], xaxis_tickangle=-20)
        fig.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Area type is based on address density: very urban areas are dense city areas; rural areas are low-density.")
    with col2:
        if has_income:
            fig = px.bar(
                by_income.sort_values("Income group"),
                x="Income group",
                y="share",
                color="Access",
                barmode="group",
                text="Label",
                color_discrete_map=ACCESS_COLORS,
                labels={"Income group": "Income level of area", "share": "Share of neighborhoods (%)"},
                title=f"Whether poorer and richer areas differ",
            )
            fig.update_layout(legend_title_text="", yaxis_range=[0, 100], xaxis_tickangle=-20)
            fig.update_traces(textposition="outside", cliponaxis=False)
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Income groups are based on neighborhood income ranks: lowest means the bottom 20% of neighborhoods, highest means the top 20%.")
        else:
            st.info("Income information is unavailable in the current dashboard dataset.")

    worst = (
        audited.groupby("gemeentenaam", as_index=False)
        .agg(
            access_pct=(amenity, lambda s: s.fillna(0).gt(0).mean() * 100),
            no_access_pct=(amenity, lambda s: (~s.fillna(0).gt(0)).mean() * 100),
            neighborhoods=("buurtcode", "count"),
            mean_access_score=("bike10_weighted_score", "mean"),
            mean_policy_score=("bike10_policy_score", "mean"),
            mean_cycling_share=("pct_bike", "mean"),
        )
        .query("neighborhoods >= 5")
        .sort_values(["access_pct", "mean_access_score"])
        .head(10)
    )
    worst = worst.rename(
        columns={
            "gemeentenaam": "Municipality",
            "access_pct": f"{label} access (%)",
            "no_access_pct": f"No {label} access (%)",
            "neighborhoods": "Neighborhoods",
            "mean_access_score": "Mean Topic 1 access score",
            "mean_policy_score": "Mean simple destination coverage",
            "mean_cycling_share": "Municipal cycling share (%)",
        }
    )
    st.markdown(f"**Municipalities where {label.lower()} access is weakest**")
    st.caption("Only municipalities with at least five neighborhoods in the dashboard are shown.")
    st.dataframe(worst.round(1), use_container_width=True, hide_index=True)
