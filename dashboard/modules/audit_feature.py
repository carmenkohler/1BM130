from __future__ import annotations

import plotly.express as px
import streamlit as st

from .data_loader import AMENITY_COLUMNS, AMENITY_LABELS, load_neighborhood_data


def render() -> None:
    df = load_neighborhood_data()
    st.subheader("Essential Function Audit")

    amenity = st.sidebar.selectbox(
        "Amenity",
        AMENITY_COLUMNS,
        format_func=lambda col: AMENITY_LABELS.get(col, col),
    )
    label = AMENITY_LABELS.get(amenity, amenity)
    audited = df.copy()
    audited["has_access"] = audited[amenity].fillna(0).gt(0)
    audited["Access"] = audited["has_access"].map({True: "Within 10-min bike access", False: "No 10-min bike access"})

    c1, c2, c3 = st.columns(3)
    c1.metric("Neighborhoods audited", f"{len(audited):,}")
    c2.metric("With access", f"{audited['has_access'].mean() * 100:.1f}%")
    c3.metric("Without access", f"{(1 - audited['has_access'].mean()) * 100:.1f}%")

    by_urban = (
        audited.dropna(subset=["Sted"])
        .groupby(["Sted", "has_access"], as_index=False)
        .size()
    )
    by_urban["share"] = by_urban.groupby("Sted")["size"].transform(lambda s: s / s.sum() * 100)
    by_urban["Access"] = by_urban["has_access"].map({True: "Within 10-min bike access", False: "No 10-min bike access"})

    has_income = audited["HHGestInkG"].notna().any()
    if has_income:
        by_income = (
            audited.dropna(subset=["HHGestInkG"])
            .groupby(["HHGestInkG", "has_access"], as_index=False)
            .size()
        )
        by_income["share"] = by_income.groupby("HHGestInkG")["size"].transform(lambda s: s / s.sum() * 100)
        by_income["Access"] = by_income["has_access"].map({True: "Within 10-min bike access", False: "No 10-min bike access"})

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            px.bar(
                by_urban,
                x="Sted",
                y="share",
                color="Access",
                barmode="group",
                labels={"Sted": "Urbanisation class", "share": "Neighborhood share (%)"},
                title=f"{label} access by urbanisation",
            ),
            use_container_width=True,
        )
    with col2:
        if has_income:
            st.plotly_chart(
                px.bar(
                    by_income,
                    x="HHGestInkG",
                    y="share",
                    color="Access",
                    barmode="group",
                    labels={"HHGestInkG": "Income decile", "share": "Neighborhood share (%)"},
                    title=f"{label} access by income decile",
                ),
                use_container_width=True,
            )
        else:
            st.info("Income deciles are unavailable in the current dashboard dataset.")

    worst = (
        audited.groupby("gemeentenaam", as_index=False)
        .agg(
            access_pct=(amenity, lambda s: s.fillna(0).gt(0).mean() * 100),
            no_access_pct=(amenity, lambda s: (~s.fillna(0).gt(0)).mean() * 100),
            neighborhoods=("buurtcode", "count"),
            mean_access_score=("bike10_weighted_score", "mean"),
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
            "mean_access_score": "Mean Bike-10 score",
            "mean_cycling_share": "Mean cycling share (%)",
        }
    )
    st.markdown(f"**10 worst-performing municipalities for {label.lower()} access**")
    st.dataframe(worst.round(1), use_container_width=True, hide_index=True)
