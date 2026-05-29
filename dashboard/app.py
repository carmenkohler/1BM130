from __future__ import annotations

import streamlit as st

from modules import agent, audit_feature, map_feature, scenario_feature


st.set_page_config(layout="wide", page_title="10-Minute Cycling City Dashboard")

st.sidebar.title("10-Minute Cycling City")
page = st.sidebar.radio(
    "",
    [
        "Access Map",
        "Equity Audit",
        "Scenario Builder",
        "Policy Assistant",
    ],
)

if page == "Access Map":
    map_feature.render()
elif page == "Equity Audit":
    audit_feature.render()
elif page == "Scenario Builder":
    scenario_feature.render()
else:
    agent.render()

