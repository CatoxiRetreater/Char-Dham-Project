"""
Alerts - Multi-Factor Risk Assessment
========================================
Alert generation, display, and threshold configuration.
Uses ONLY native Streamlit components - no raw HTML layouts.
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

from core.data_loader import load_and_merge_data, SHRINE_COORDS, get_shrine_data
from core.feature_engine import compute_esi, compute_ndvi_features, compute_tourism_pressure_index
from core.alerts import (
    generate_all_alerts, get_overall_risk_level, count_alerts_by_level,
    DEFAULT_THRESHOLDS, ALERT_LEVELS, Alert
)
from core.report_generator import CharDhamReport

st.set_page_config(page_title="Alerts | Char Dham", page_icon="M", layout="wide")
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# --- Data ---
if "df" not in st.session_state:
    df = load_and_merge_data()
    df["ESI"] = compute_esi(df)
    df = compute_ndvi_features(df)
    df["TPI"] = compute_tourism_pressure_index(df)
    st.session_state["df"] = df
else:
    df = st.session_state["df"]

if df.empty:
    st.error("No data available.")
    st.stop()

# --- Sidebar: Threshold Configuration ---
with st.sidebar:
    st.markdown("### Alert Configuration")
    selected_shrine = st.selectbox("Select Shrine", list(SHRINE_COORDS.keys()), key="alert_shrine")
    st.markdown("---")

    st.markdown("##### Threshold Settings")
    with st.expander("Capacity Thresholds"):
        t_cap_med = st.slider("Medium Threshold", 0.4, 1.0, DEFAULT_THRESHOLDS["capacity_util_medium"], 0.05, key="t_cap_med")
        t_cap_high = st.slider("Critical Threshold", 0.6, 1.5, DEFAULT_THRESHOLDS["capacity_util_high"], 0.05, key="t_cap_high")

    with st.expander("Temperature Thresholds"):
        t_temp_mod = st.slider("Moderate Anomaly (C)", 1.0, 8.0, DEFAULT_THRESHOLDS["temp_anomaly_moderate"], 0.5, key="t_temp_mod")
        t_temp_high = st.slider("High Anomaly (C)", 3.0, 12.0, DEFAULT_THRESHOLDS["temp_anomaly_high"], 0.5, key="t_temp_high")

    with st.expander("ESI Thresholds"):
        t_esi_mod = st.slider("Moderate ESI", 20, 60, int(DEFAULT_THRESHOLDS["esi_moderate"]), 5, key="t_esi_mod")
        t_esi_crit = st.slider("Critical ESI", 50, 90, int(DEFAULT_THRESHOLDS["esi_critical"]), 5, key="t_esi_crit")

custom_thresholds = {
    **DEFAULT_THRESHOLDS,
    "capacity_util_medium": t_cap_med,
    "capacity_util_high": t_cap_high,
    "temp_anomaly_moderate": t_temp_mod,
    "temp_anomaly_high": t_temp_high,
    "esi_moderate": t_esi_mod,
    "esi_critical": t_esi_crit,
}

# --- Header ---
st.markdown("# Alert Center")
st.caption("Multi-factor risk assessment with configurable thresholds and AI-driven recommendations")
st.markdown("---")

# --- Generate Alerts for Selected Shrine ---
alerts = generate_all_alerts(df, selected_shrine, custom_thresholds)
overall_risk = get_overall_risk_level(alerts)
counts = count_alerts_by_level(alerts)

# --- Risk Summary ---
st.markdown(f"### Risk Overview: {selected_shrine}")

r1, r2, r3, r4, r5 = st.columns(5)

r1.metric("Overall Risk", overall_risk.name)
r2.metric("Low", str(counts["LOW"]))
r3.metric("Moderate", str(counts["MODERATE"]))
r4.metric("High", str(counts["HIGH"]))
r5.metric("Critical", str(counts["CRITICAL"]))

st.markdown("---")

# --- Individual Alert Cards ---
st.markdown("### Alert Details")

for alert in sorted(alerts, key=lambda a: a.level.priority, reverse=True):
    severity = alert.level.name

    if severity == "CRITICAL":
        st.error(f"**{alert.category.replace('_', ' ').title()}** | {alert.title}")
    elif severity == "HIGH":
        st.warning(f"**{alert.category.replace('_', ' ').title()}** | {alert.title}")
    elif severity == "MODERATE":
        st.warning(f"**{alert.category.replace('_', ' ').title()}** | {alert.title}")
    else:
        st.success(f"**{alert.category.replace('_', ' ').title()}** | {alert.title}")

    with st.expander(f"Details: {alert.category.replace('_', ' ').title()}", expanded=severity in ("CRITICAL", "HIGH")):
        st.markdown(f"**Assessment:** {alert.message}")
        st.markdown(f"**Recommendation:** {alert.recommendation}")
        m1, m2 = st.columns(2)
        m1.metric("Current Value", f"{alert.value:.2f}")
        m2.metric("Threshold", f"{alert.threshold:.2f}")

st.markdown("---")

# --- Cross-Shrine Summary ---
st.markdown("### All Shrines Summary")

all_shrine_data = []
for shrine in SHRINE_COORDS:
    s_alerts = generate_all_alerts(df, shrine, custom_thresholds)
    s_risk = get_overall_risk_level(s_alerts)
    s_counts = count_alerts_by_level(s_alerts)

    shrine_df_temp = df[df["Shrine"] == shrine]
    latest_esi = shrine_df_temp["ESI"].iloc[-1] if not shrine_df_temp.empty else 0

    all_shrine_data.append({
        "Shrine": shrine,
        "Overall Risk": s_risk.name,
        "ESI": f"{latest_esi:.1f}",
        "Critical": s_counts["CRITICAL"],
        "High": s_counts["HIGH"],
        "Moderate": s_counts["MODERATE"],
        "Low": s_counts["LOW"],
        "Total Alerts": len(s_alerts),
    })

st.dataframe(pd.DataFrame(all_shrine_data), width='stretch', hide_index=True)

# --- Download Report ---
st.markdown("---")
st.markdown("### Export Report")

col_pdf, col_csv = st.columns(2)

with col_pdf:
    try:
        report = CharDhamReport()
        report.add_section_title(f"Alert Report - {selected_shrine}")
        report.add_body_text(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        for alert in alerts:
            report.add_alert_entry(alert.level.name, alert.category, f"{alert.message} Recommendation: {alert.recommendation}")
        pdf_bytes = bytes(report.output())
        st.download_button("Download PDF Report", pdf_bytes, f"alerts_{selected_shrine}.pdf", "application/pdf")
    except Exception as e:
        st.caption(f"PDF generation unavailable: {e}")

with col_csv:
    csv_data = pd.DataFrame([{
        "Shrine": a.shrine, "Category": a.category, "Severity": a.level.name,
        "Title": a.title, "Message": a.message, "Recommendation": a.recommendation,
    } for a in alerts])
    st.download_button("Download CSV Report", csv_data.to_csv(index=False), f"alerts_{selected_shrine}.csv", "text/csv")
