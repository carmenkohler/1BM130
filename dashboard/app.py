from __future__ import annotations

import streamlit as st

from modules import agent, audit_feature, map_feature, scenario_feature


st.set_page_config(layout="wide", page_title="10-Minute Cycling City Dashboard")

st.sidebar.title("10-Minute Cycling City")
page = st.sidebar.radio(
    "",
    [
        "Access-Usage Heatmap",
        "Essential Function Audit",
        "What-If Scenario Builder",
        "AI Policy Assistant",
    ],
)

if page == "Access-Usage Heatmap":
    map_feature.render()
elif page == "Essential Function Audit":
    audit_feature.render()
elif page == "What-If Scenario Builder":
    scenario_feature.render()
else:
    agent.render()

