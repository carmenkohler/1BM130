from __future__ import annotations

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from branca.colormap import LinearColormap
from streamlit_folium import st_folium

from .data_loader import ACCESS_METHOD_NOTE, USAGE_METHOD_NOTE, load_buurt_centroids, load_buurt_geometries, load_neighborhood_data


INCOME_FILTERS = {
    "All income groups": None,
    "Lowest income areas": (1, 2),
    "Lower-middle income areas": (3, 4),
    "Middle income areas": (5, 6),
    "Higher-middle income areas": (7, 8),
    "Highest income areas": (9, 10),
}

INCOME_LABELS = {
    1: "Lowest income areas",
    2: "Lowest income areas",
    3: "Lower-middle income areas",
    4: "Lower-middle income areas",
    5: "Middle income areas",
    6: "Middle income areas",
    7: "Higher-middle income areas",
    8: "Higher-middle income areas",
    9: "Highest income areas",
    10: "Highest income areas",
}

PATTERN_COLORS = {
    "Strong access and cycling": "#2e7d32",
    "Good access, low cycling": "#f57c00",
    "Low access, high cycling": "#1976d2",
    "Low access and cycling": "#c62828",
    "Unknown": "#777777",
}

METRIC_LABELS = {
    "bike10_weighted_score": "Topic 1 bike-access score",
    "pct_bike": "Municipal cycling share",
    "access_usage_gap": "Discussion gap",
    "pattern_label": "Policy pattern",
}


def _metric_color(metric: str, values: pd.Series):
    if metric == "pattern_label":
        return None
    values = pd.to_numeric(values, errors="coerce")
    vmin = float(values.quantile(0.05)) if values.notna().any() else 0.0
    vmax = float(values.quantile(0.95)) if values.notna().any() else 100.0
    if vmin == vmax:
        vmax = vmin + 1
    if metric == "access_usage_gap":
        limit = max(abs(vmin), abs(vmax), 1)
        return LinearColormap(["#2166ac", "#f7f7f7", "#b2182b"], vmin=-limit, vmax=limit)
    return LinearColormap(["#f7fbff", "#6baed6", "#08306b"], vmin=vmin, vmax=vmax)


def _draw_spatial_map(filtered: pd.DataFrame, metric: str, municipality: str) -> None:
    if filtered.empty:
        st.info("No neighborhoods match the current filters.")
        return

    colormap = _metric_color(metric, filtered[metric] if metric != "pattern_label" else pd.Series(dtype=float))

    if municipality != "All municipalities":
        gdf = load_buurt_geometries(municipality)
        gdf = gdf.merge(filtered, on="buurtcode", how="inner")
        if gdf.empty:
            st.info("No map shapes found for the selected municipality.")
            return

        minx, miny, maxx, maxy = gdf.total_bounds
        fmap = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=12, tiles="cartodbpositron")

        def style_function(feature):
            props = feature["properties"]
            value = props.get(metric)
            if metric == "pattern_label":
                fill = PATTERN_COLORS.get(value, "#777777")
            else:
                fill = colormap(float(value)) if pd.notna(value) else "#cccccc"
            return {
                "fillColor": fill,
                "color": "#555555",
                "weight": 0.5,
                "fillOpacity": 0.68,
            }

        tooltip_fields = [
            "buurtnaam",
            "bike10_weighted_score",
            "pct_bike",
            "access_usage_gap",
            "pattern_label",
        ]
        popup_fields = tooltip_fields + ["income_group_label"]
        folium.GeoJson(
            gdf,
            name="Neighborhoods",
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=tooltip_fields,
                aliases=["Neighborhood", "Topic 1 bike-access score", "Municipal cycling share", "Discussion gap", "Pattern"],
                localize=True,
                sticky=True,
            ),
            popup=folium.GeoJsonPopup(
                fields=popup_fields,
                aliases=[
                    "Neighborhood",
                    "Topic 1 bike-access score",
                    "Municipal cycling share (%)",
                    "Discussion gap (pp)",
                    "Pattern",
                    "Income group",
                ],
                localize=True,
                labels=True,
            ),
        ).add_to(fmap)
        if colormap is not None:
            colormap.caption = METRIC_LABELS.get(metric, metric)
            colormap.add_to(fmap)
        st_folium(fmap, use_container_width=True, height=560)
        return

    centroids = load_buurt_centroids()
    points = filtered.merge(centroids, on="buurtcode", how="inner").dropna(subset=["lat", "lon"])
    if len(points) > 3000:
        points = points.sample(3000, random_state=42)

    fmap = folium.Map(location=[52.15, 5.35], zoom_start=7, tiles="cartodbpositron")
    for row in points.itertuples(index=False):
        value = getattr(row, metric)
        if metric == "pattern_label":
            fill = PATTERN_COLORS.get(value, "#777777")
        else:
            fill = colormap(float(value)) if pd.notna(value) else "#777777"
        folium.CircleMarker(
            location=[row.lat, row.lon],
            radius=3,
            color=fill,
            fill=True,
            fill_color=fill,
            fill_opacity=0.75,
            weight=0,
            tooltip=(
                f"{row.buurtnaam}<br>{row.gemeentenaam}<br>"
                f"Topic 1 bike-access score: {row.bike10_weighted_score:.1f}<br>"
                f"Municipal cycling share: {row.pct_bike:.1f}%<br>"
                f"Discussion gap: {row.access_usage_gap:+.1f} pp<br>"
                f"{row.pattern_label}"
            ),
            popup=(
                f"<b>{row.buurtnaam}</b><br>"
                f"{row.gemeentenaam}<br>"
                f"Neighborhood code: {row.buurtcode}<br>"
                f"Topic 1 bike-access score: {row.bike10_weighted_score:.1f}<br>"
                f"Municipal cycling share: {row.pct_bike:.1f}%<br>"
                f"Discussion gap: {row.access_usage_gap:+.1f} pp<br>"
                f"Pattern: {row.pattern_label}"
            ),
        ).add_to(fmap)
    if colormap is not None:
        colormap.caption = METRIC_LABELS.get(metric, metric)
        colormap.add_to(fmap)
    st_folium(fmap, use_container_width=True, height=560)


def _style_row(row: pd.Series) -> str:
    color = PATTERN_COLORS.get(row.get("pattern_label", row.get("Policy pattern")), "#777777")
    return [f"background-color: {color}; color: white"] * len(row)


def render() -> None:
    df = load_neighborhood_data()
    st.subheader("Access Map")
    st.caption(f"{ACCESS_METHOD_NOTE} {USAGE_METHOD_NOTE}")

    metric = st.sidebar.selectbox(
        "Metric",
        ["bike10_weighted_score", "pct_bike", "access_usage_gap", "pattern_label"],
        format_func=lambda x: {
            **METRIC_LABELS,
        }[x],
    )
    municipalities = ["All municipalities"] + sorted(df["gemeentenaam"].dropna().unique().tolist())
    municipality = st.sidebar.selectbox("Municipality", municipalities)
    has_income = df["HHGestInkG"].notna().any()
    income_group = st.sidebar.selectbox("Income level of area", list(INCOME_FILTERS), disabled=not has_income)
    if not has_income:
        st.sidebar.caption("Income information is unavailable in the current dashboard dataset.")
    else:
        st.sidebar.caption("Income groups compare neighborhoods by average income: lowest is the bottom 20%, highest is the top 20%.")

    filtered = df.copy()
    income = INCOME_FILTERS[income_group]
    if has_income and income is not None:
        filtered = filtered[filtered["HHGestInkG"].between(income[0], income[1], inclusive="both")]
    if municipality != "All municipalities":
        filtered = filtered[filtered["gemeentenaam"] == municipality]
    filtered = filtered.copy()
    filtered["income_group_label"] = filtered["HHGestInkG"].round().astype("Int64").map(INCOME_LABELS).fillna("Unknown")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Neighborhoods shown", f"{len(filtered):,}")
    c2.metric("Average access score", f"{filtered['bike10_weighted_score'].mean():.1f}")
    c3.metric("Municipal cycling share", f"{filtered['pct_bike'].mean():.1f}%")
    c4.metric("Discussion gap", f"{filtered['access_usage_gap'].mean():+.1f} pp")

    st.caption(
        "This is the same weighted bike-access score used in Topic 1. "
        "The table also shows simple key-destination coverage as a supporting explanation. "
        "Select a municipality to zoom in on neighborhood map areas."
    )

    _draw_spatial_map(filtered, metric, municipality)

    color = "pattern_label" if metric == "pattern_label" else metric
    st.plotly_chart(
        px.scatter(
            filtered,
            x="bike10_weighted_score",
            y="pct_bike",
            color=color,
            hover_name="buurtnaam",
            hover_data=["gemeentenaam", "income_group_label", "access_usage_gap", "pattern_label"],
            color_discrete_map=PATTERN_COLORS,
            labels={
                "bike10_weighted_score": "Topic 1 bike-access score",
                "pct_bike": "Municipal cycling share (%)",
                "access_usage_gap": "Discussion gap",
            },
            title="Access to key destinations compared with cycling use",
        ),
        use_container_width=True,
    )

    display_cols = [
        "buurtnaam",
        "gemeentenaam",
        "bike10_weighted_score",
        "bike10_coverage_score",
        "bike10_policy_score",
        "pct_bike",
        "access_usage_gap",
        "income_group_label",
        "pattern_label",
    ]
    table = filtered.sort_values(metric if metric != "pattern_label" else "access_usage_gap", ascending=True)
    table_display = table[display_cols].rename(
        columns={
            "buurtnaam": "Neighborhood",
            "gemeentenaam": "Municipality",
            "bike10_weighted_score": "Topic 1 bike-access score",
            "bike10_coverage_score": "Key destination coverage",
            "bike10_policy_score": "All listed destinations coverage",
            "pct_bike": "Municipal cycling share (%)",
            "access_usage_gap": "Discussion gap (pp)",
            "income_group_label": "Income group",
            "pattern_label": "Policy pattern",
        }
    )
    st.dataframe(
        table_display.head(500).style.apply(_style_row, axis=1),
        use_container_width=True,
        height=560,
    )
