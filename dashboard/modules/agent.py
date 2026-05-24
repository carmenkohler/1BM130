from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

from .data_loader import AMENITY_COLUMNS, AMENITY_LABELS, DASHBOARD_DIR, load_model, load_neighborhood_data


SYSTEM_PROMPT_PATH = DASHBOARD_DIR / "prompts" / "system_prompt.txt"
ENV_PATHS = [
    DASHBOARD_DIR.parent / ".env",
    DASHBOARD_DIR / ".env",
]
PLACEHOLDER_KEY = "paste_your_gemini_key_here"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
LAST_GEMINI_ERROR: str | None = None


def _system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _load_env_file() -> None:
    for env_path in ENV_PATHS:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ[key] = value


def _get_gemini_api_key() -> str | None:
    _load_env_file()
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and api_key != PLACEHOLDER_KEY:
        return api_key

    if hasattr(st, "secrets"):
        try:
            api_key = st.secrets.get("GEMINI_API_KEY", None)
        except Exception:
            api_key = None
    if api_key and api_key != PLACEHOLDER_KEY:
        return api_key
    return None


def gemini_key_configured() -> bool:
    return _get_gemini_api_key() is not None


def get_neighborhood_profile(buurtcode: str) -> dict[str, Any]:
    df = load_neighborhood_data()
    row = df.loc[df["buurtcode"].astype(str) == str(buurtcode)]
    if row.empty:
        return {"error": f"No neighborhood found for buurtcode {buurtcode}."}
    r = row.iloc[0]
    return {
        "buurtcode": r["buurtcode"],
        "buurtnaam": r["buurtnaam"],
        "gemeentenaam": r["gemeentenaam"],
        "access_score": round(float(r["bike10_weighted_score"]), 1),
        "cycling_share_pct": round(float(r["pct_bike"]), 1),
        "access_usage_gap_pp": round(float(r["access_usage_gap"]), 1),
        "income_decile": None if pd.isna(r["HHGestInkG"]) else int(r["HHGestInkG"]),
        "urbanisation_class": None if pd.isna(r["Sted"]) else int(r["Sted"]),
        "pattern_label": r["pattern_label"],
    }


def get_worst_neighborhoods(metric: str, n: int = 10) -> list[dict[str, Any]]:
    allowed = {"bike10_weighted_score", "pct_bike", "access_usage_gap"}
    if metric not in allowed:
        return [{"error": f"Metric must be one of {sorted(allowed)}."}]
    df = load_neighborhood_data()
    cols = ["buurtcode", "buurtnaam", "gemeentenaam", metric, "pattern_label"]
    return df.sort_values(metric)[cols].head(n).to_dict(orient="records")


def get_municipality_summary(gemeentenaam: str) -> dict[str, Any]:
    df = load_neighborhood_data()
    mun = df[df["gemeentenaam"].str.lower() == gemeentenaam.lower()]
    if mun.empty:
        return {"error": f"No municipality found for {gemeentenaam}."}
    return {
        "gemeentenaam": gemeentenaam,
        "neighborhoods": int(len(mun)),
        "mean_access_score": round(float(mun["bike10_weighted_score"].mean()), 1),
        "mean_cycling_share_pct": round(float(mun["pct_bike"].mean()), 1),
        "mean_gap_pp": round(float(mun["access_usage_gap"].mean()), 1),
        "pattern_counts": mun["pattern_label"].value_counts().to_dict(),
        "income_decile_counts": mun["HHGestInkG"].value_counts(dropna=True).sort_index().to_dict(),
    }


def get_amenity_gap(amenity: str) -> dict[str, Any]:
    if amenity not in AMENITY_COLUMNS:
        reverse = {v.lower(): k for k, v in AMENITY_LABELS.items()}
        amenity = reverse.get(amenity.lower(), amenity)
    if amenity not in AMENITY_COLUMNS:
        return {"error": f"Unknown amenity. Use one of: {list(AMENITY_LABELS.values())}."}

    df = load_neighborhood_data().copy()
    df["lacks_amenity"] = ~df[amenity].fillna(0).gt(0)
    return {
        "amenity": AMENITY_LABELS.get(amenity, amenity),
        "overall_lacking_pct": round(float(df["lacks_amenity"].mean() * 100), 1),
        "lacking_by_urbanisation_pct": (
            df.groupby("Sted")["lacks_amenity"].mean().mul(100).round(1).to_dict()
        ),
        "lacking_by_income_decile_pct": (
            df.groupby("HHGestInkG")["lacks_amenity"].mean().mul(100).round(1).to_dict()
        ),
    }


def get_scenario_result(buurtcode: str, intervention: str) -> dict[str, Any]:
    df = load_neighborhood_data()
    row = df.loc[df["buurtcode"].astype(str).eq(str(buurtcode))]
    if row.empty:
        return {"error": f"No neighborhood found for buurtcode {buurtcode}."}

    from .scenario_feature import INTERVENTIONS, run_model_scenario, run_proxy_scenario

    if intervention not in INTERVENTIONS:
        return {"error": f"Unknown intervention. Use one of: {list(INTERVENTIONS)}."}

    model, metadata = load_model()
    if model is None:
        return run_proxy_scenario(row.iloc[0], intervention)
    result, warning = run_model_scenario(row.iloc[0], intervention, model, metadata)
    if warning:
        result["warning"] = warning
    return result


def summarize_scenario(result: dict[str, Any]) -> str:
    return (
        f"For {result['buurtnaam']} in {result['gemeentenaam']}, the {result['intervention'].lower()} scenario "
        f"changes the access score from {result['baseline_access_score']:.1f} to "
        f"{result['scenario_access_score']:.1f}. The estimated cycling-share change is "
        f"{result['delta_bike_share_pp']:+.1f} percentage points using a {result['method']}. "
        f"{result.get('intervention_note', '')} "
        "Treat this as a screening estimate because it depends on representative ODiN trips and model features. "
        "Recommendation: validate the intervention against observed trip-purpose demand before prioritising investment."
    )


def _dispatch(user_message: str, selected_buurt: str | None) -> dict[str, Any]:
    message = user_message.lower()
    df = load_neighborhood_data()

    code_match = re.search(r"\b[0-9A-Z]{8}\b", user_message)
    buurt_context = code_match.group(0) if code_match else selected_buurt

    if "scenario" in message or "what if" in message or "intervention" in message:
        if "gp" in message or "doctor" in message or "huisarts" in message:
            intervention = "Add GP/doctor"
        elif "school" in message:
            intervention = "Add primary school"
        elif "car" in message:
            intervention = "Reduce car dependency"
        elif "infrastructure" in message or "cycling" in message:
            intervention = "Improve cycling infrastructure"
        else:
            intervention = "Add supermarket"
        if buurt_context:
            return {"tool": "get_scenario_result", "context": get_scenario_result(buurt_context, intervention)}
        return {"tool": "get_scenario_result", "context": {"error": "No selected neighborhood context is available."}}

    if "worst" in message or "lowest" in message:
        if "cycling" in message or "bike share" in message:
            return {"tool": "get_worst_neighborhoods", "context": get_worst_neighborhoods("pct_bike")}
        if "gap" in message:
            return {"tool": "get_worst_neighborhoods", "context": get_worst_neighborhoods("access_usage_gap")}
        return {"tool": "get_worst_neighborhoods", "context": get_worst_neighborhoods("bike10_weighted_score")}

    if "amenity" in message or "supermarket" in message or "school" in message or "gp" in message:
        if "supermarket" in message:
            amenity = "bike10_klasse_supermarkt"
        elif "school" in message:
            amenity = "bike10_klasse_basisschool"
        elif "gp" in message or "doctor" in message or "huisarts" in message:
            amenity = "bike10_klasse_huisarts"
        else:
            amenity = "bike10_klasse_supermarkt"
        return {"tool": "get_amenity_gap", "context": get_amenity_gap(amenity)}

    for name in df["gemeentenaam"].dropna().unique():
        if str(name).lower() in message:
            return {"tool": "get_municipality_summary", "context": get_municipality_summary(str(name))}

    if buurt_context:
        return {"tool": "get_neighborhood_profile", "context": get_neighborhood_profile(buurt_context)}
    return {"tool": "none", "context": {"error": "No selected neighborhood context is available."}}


def _call_gemini(prompt: str) -> str | None:
    global LAST_GEMINI_ERROR
    LAST_GEMINI_ERROR = None
    api_key = _get_gemini_api_key()
    if not api_key:
        LAST_GEMINI_ERROR = "No Gemini API key was found."
        return None

    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
    url = GEMINI_API_URL.format(model=model)
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 512,
        },
    }
    try:
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            json=payload,
            timeout=(5, 20),
        )
        if not response.ok:
            LAST_GEMINI_ERROR = f"Gemini API returned HTTP {response.status_code}: {response.text[:300]}"
            return None
        data = response.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            LAST_GEMINI_ERROR = "Gemini returned an empty response."
            return None
        return text
    except requests.Timeout:
        LAST_GEMINI_ERROR = "Gemini API request timed out."
        return None
    except Exception as exc:
        LAST_GEMINI_ERROR = f"Gemini API call failed: {type(exc).__name__}: {exc}"
        return None


def answer_question(user_message: str, selected_buurt: str | None = None) -> str:
    dispatched = _dispatch(user_message, selected_buurt)
    prompt = f"{_system_prompt()}\n\nData context:\n{dispatched}\n\nUser question: {user_message}"
    key_configured = gemini_key_configured()
    response = _call_gemini(prompt)
    if response:
        return response

    return _format_fallback_answer(dispatched, key_configured)


def _fallback_reason(key_configured: bool) -> str:
    if key_configured:
        detail = f" Detail: {LAST_GEMINI_ERROR}" if LAST_GEMINI_ERROR else ""
        return f"Gemini is configured, but the API call failed, so this is a deterministic fallback.{detail}"
    return "No Gemini API key is configured, so this is a deterministic fallback."


def _format_fallback_answer(dispatched: dict[str, Any], key_configured: bool = False) -> str:
    context = dispatched["context"]
    if isinstance(context, list) and context:
        rows = []
        for row in context[:5]:
            name = row.get("buurtnaam", "Unknown neighborhood")
            municipality = row.get("gemeentenaam", "unknown municipality")
            metric_items = [
                (key, value)
                for key, value in row.items()
                if key not in {"buurtcode", "buurtnaam", "gemeentenaam", "pattern_label"}
            ]
            metric_text = ", ".join(f"{key}: {value}" for key, value in metric_items)
            pattern = row.get("pattern_label", "Unknown")
            rows.append(f"- {name} ({municipality}): {metric_text}; pattern: {pattern}")
        findings = "\n".join(rows)
        return (
            f"Using `{dispatched['tool']}`, the strongest candidates are:\n\n"
            f"{findings}\n\n"
            f"{_fallback_reason(key_configured)} "
            "Use these neighborhoods as a shortlist for a concrete access intervention."
        )

    if isinstance(context, dict) and "error" not in context:
        if "delta_bike_share_pp" in context:
            return (
                f"Using `{dispatched['tool']}`, the {context['intervention'].lower()} scenario for "
                f"{context['buurtnaam']} ({context['gemeentenaam']}) changes predicted cycling share from "
                f"{context['baseline_bike_share']:.1f}% to {context['scenario_bike_share']:.1f}% "
                f"({context['delta_bike_share_pp']:+.1f} pp). "
                f"The estimate uses {context['method']} with {context.get('sample_scope', 'available')} trips. "
                "Recommendation: treat this as a shortlist signal and validate the intervention locally before implementation."
            )
        facts = "\n".join(f"- {key}: {value}" for key, value in context.items())
        return (
            f"Using `{dispatched['tool']}`, I found:\n\n{facts}\n\n"
            f"{_fallback_reason(key_configured)}"
        )

    return (
        "I could not find enough local context for that question. "
        "Try asking about a municipality, amenity gap, low access, low cycling share, or the selected neighborhood."
    )


def render() -> None:
    st.subheader("AI Policy Assistant")
    if gemini_key_configured():
        st.caption("Gemini API key detected from `.env` or Streamlit secrets.")
    else:
        st.caption("No Gemini API key detected. Add `GEMINI_API_KEY=...` to `.env`.")
    selected_buurt = st.session_state.get("selected_buurt")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    user_message = st.chat_input("Ask about a neighborhood, municipality, amenity gap, or policy opportunity")
    if user_message:
        st.session_state.messages.append({"role": "user", "content": user_message})
        with st.chat_message("user"):
            st.write(user_message)
        answer = answer_question(user_message, selected_buurt)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.write(answer)
