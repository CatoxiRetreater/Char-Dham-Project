"""
Simulator - What-If Scenario Planning
========================================
Scenario sliders, ESI comparison, sensitivity analysis.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

from core.data_loader import load_and_merge_data, SHRINE_COORDS, get_shrine_data
from core.feature_engine import compute_esi, compute_ndvi_features, compute_tourism_pressure_index, get_esi_status

st.set_page_config(page_title="Simulator | Char Dham", page_icon="M", layout="wide")
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

# --- Sidebar ---
with st.sidebar:
    st.markdown("### Simulator Controls")
    selected_shrine = st.selectbox("Select Shrine", list(SHRINE_COORDS.keys()), key="sim_shrine")
    st.markdown("---")

    st.markdown("##### Scenario Parameters")
    shrine_df = get_shrine_data(df, selected_shrine)
    latest = shrine_df.iloc[-1]

    sim_pilgrims = st.slider("Pilgrim Count",
        min_value=0, max_value=int(latest["Carrying_Capacity"] * 3),
        value=int(latest["Pilgrim_Count"]), step=100, key="sim_pil")

    sim_temp = st.slider("Temperature (C)",
        min_value=-15.0, max_value=35.0,
        value=float(latest["Avg_Temperature_C"]), step=0.5, key="sim_temp")

    sim_rainfall = st.slider("Rainfall (mm)",
        min_value=0.0, max_value=500.0,
        value=float(latest["Rainfall_mm"]), step=5.0, key="sim_rain")

    sim_ndvi = st.slider("NDVI",
        min_value=0.05, max_value=0.85,
        value=float(latest.get("NDVI", 0.4)), step=0.01, key="sim_ndvi")

    st.markdown("---")
    st.markdown("##### Guide")
    st.caption("1. Adjust sliders to simulate scenarios")
    st.caption("2. Compare current vs simulated ESI")
    st.caption("3. Review impact analysis below")

# --- Header ---
st.markdown(f"# What-If Simulator: {selected_shrine}")
st.caption("Explore how changes in tourism volume, climate, and vegetation affect ecosystem stress")
st.markdown("---")

# --- Compute Simulated ESI ---
capacity = int(latest["Carrying_Capacity"])

# Build simulated row
sim_row = latest.copy()
sim_row["Pilgrim_Count"] = sim_pilgrims
sim_row["Avg_Temperature_C"] = sim_temp
sim_row["Rainfall_mm"] = sim_rainfall
if "NDVI" in sim_row.index:
    sim_row["NDVI"] = sim_ndvi

sim_df = pd.DataFrame([sim_row])

# Recompute anomalies for sim
mean_temp = shrine_df["Avg_Temperature_C"].mean()
mean_rain = shrine_df["Rainfall_mm"].mean()
sim_df["Temp_Anomaly"] = sim_temp - mean_temp
sim_df["Rain_Anomaly"] = sim_rainfall - mean_rain
sim_df["Capacity_Utilization"] = sim_pilgrims / max(capacity, 1)
sim_df["Carrying_Capacity"] = capacity

sim_esi = float(compute_esi(sim_df).iloc[0])
current_esi = float(latest["ESI"])

current_status, current_color, current_desc = get_esi_status(current_esi)
sim_status, sim_color, sim_desc = get_esi_status(sim_esi)
esi_delta = sim_esi - current_esi

# --- Comparison ---
st.markdown("### Current vs Simulated Comparison")

col_current, col_gauge, col_sim = st.columns([1, 1, 1])

with col_current:
    st.markdown("#### Current State")
    st.metric("ESI", f"{current_esi:.1f}/100", current_status)
    st.metric("Pilgrims", f"{int(latest['Pilgrim_Count']):,}")
    st.metric("Temperature", f"{latest['Avg_Temperature_C']:.1f}C")
    st.metric("Rainfall", f"{latest['Rainfall_mm']:.0f} mm")
    st.metric("NDVI", f"{latest.get('NDVI', 0):.3f}")
    st.metric("Utilization", f"{latest['Pilgrim_Count']/max(capacity,1)*100:.0f}%")

with col_gauge:
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=sim_esi,
        delta={"reference": current_esi, "valueformat": ".1f"},
        number={"suffix": "/100", "font": {"size": 40, "color": sim_color}},
        title={"text": "Simulated ESI", "font": {"color": "#e2e8f0", "size": 14}},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": sim_color, "thickness": 0.3},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 1, "bordercolor": "#334155",
            "steps": [
                {"range": [0, 40], "color": "rgba(34,197,94,0.12)"},
                {"range": [40, 70], "color": "rgba(245,158,11,0.12)"},
                {"range": [70, 100], "color": "rgba(239,68,68,0.12)"},
            ],
        },
    ))
    fig_gauge.update_layout(
        height=300, margin=dict(l=20, r=20, t=50, b=10),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"),
    )
    st.plotly_chart(fig_gauge, width='stretch')

    direction = "increase" if esi_delta > 0 else "decrease"
    st.metric("ESI Change", f"{esi_delta:+.1f}", f"{direction} in stress")

with col_sim:
    st.markdown("#### Simulated State")
    st.metric("ESI", f"{sim_esi:.1f}/100", sim_status)
    st.metric("Pilgrims", f"{sim_pilgrims:,}")
    st.metric("Temperature", f"{sim_temp:.1f}C")
    st.metric("Rainfall", f"{sim_rainfall:.0f} mm")
    st.metric("NDVI", f"{sim_ndvi:.3f}")
    st.metric("Utilization", f"{sim_pilgrims/max(capacity,1)*100:.0f}%")

st.markdown("---")

# --- Simulated Alert Triggers ---
st.markdown("### Simulated Alert Triggers")

sim_util = sim_pilgrims / max(capacity, 1)
trigger_data = {
    "Tourist Overload": ("CRITICAL" if sim_util >= 1.0 else "HIGH" if sim_util >= 0.85 else "MODERATE" if sim_util >= 0.6 else "LOW"),
    "Climate Stress": ("HIGH" if abs(sim_temp - mean_temp) >= 6 else "MODERATE" if abs(sim_temp - mean_temp) >= 3 else "LOW"),
    "NDVI Degradation": ("HIGH" if sim_ndvi < 0.2 else "MODERATE" if sim_ndvi < 0.35 else "LOW"),
    "ESI Level": ("CRITICAL" if sim_esi >= 70 else "MODERATE" if sim_esi >= 40 else "LOW"),
}

t_cols = st.columns(len(trigger_data))
for i, (name, level) in enumerate(trigger_data.items()):
    with t_cols[i]:
        if level == "CRITICAL":
            st.error(f"**{name}**")
        elif level == "HIGH":
            st.warning(f"**{name}**")
        elif level == "MODERATE":
            st.warning(f"**{name}**")
        else:
            st.success(f"**{name}**")
        st.caption(level)

st.markdown("---")

# --- Sensitivity Analysis ---
st.markdown("### Sensitivity Analysis")
st.caption("How each parameter independently affects ESI while others remain at current values")

param_ranges = {
    "Pilgrim Count": np.linspace(0, capacity * 2, 50),
    "Temperature (C)": np.linspace(-10, 30, 50),
    "Rainfall (mm)": np.linspace(0, 400, 50),
    "NDVI": np.linspace(0.05, 0.85, 50),
}

fig_sens = go.Figure()
colors = {
    "Pilgrim Count": "#3b82f6",
    "Temperature (C)": "#f59e0b",
    "Rainfall (mm)": "#22c55e",
    "NDVI": "#ec4899",
}

for param_name, param_values in param_ranges.items():
    esi_values = []
    for val in param_values:
        test_row = latest.copy()
        test_df = pd.DataFrame([test_row])
        test_df["Carrying_Capacity"] = capacity

        # Apply the parameter being swept
        if param_name == "Pilgrim Count":
            test_df["Pilgrim_Count"] = val
        elif param_name == "Temperature (C)":
            test_df["Avg_Temperature_C"] = val
        elif param_name == "Rainfall (mm)":
            test_df["Rainfall_mm"] = val
        elif param_name == "NDVI":
            test_df["NDVI"] = val

        # Always recompute ALL derived fields for accuracy
        test_df["Capacity_Utilization"] = test_df["Pilgrim_Count"] / max(capacity, 1)
        test_df["Temp_Anomaly"] = test_df["Avg_Temperature_C"] - mean_temp
        test_df["Rain_Anomaly"] = test_df["Rainfall_mm"] - mean_rain

        esi_values.append(float(compute_esi(test_df).iloc[0]))

    fig_sens.add_trace(go.Scatter(
        x=param_values, y=esi_values, mode="lines",
        name=param_name, line=dict(color=colors[param_name], width=2),
    ))

fig_sens.add_hline(y=40, line_dash="dot", line_color="#f59e0b", annotation_text="Moderate", annotation_position="right")
fig_sens.add_hline(y=70, line_dash="dot", line_color="#ef4444", annotation_text="Critical", annotation_position="right")

fig_sens.update_layout(
    height=400, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e2e8f0"),
    xaxis=dict(showgrid=False, title="Parameter Value"),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", title="ESI (0-100)", range=[0, 100]),
    legend=dict(orientation="h", y=1.08), hovermode="x unified",
)
st.plotly_chart(fig_sens, width='stretch')

