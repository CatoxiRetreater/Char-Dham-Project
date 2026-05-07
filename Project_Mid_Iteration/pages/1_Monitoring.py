"""
Monitoring - Real-Time Environmental Monitoring
==================================================
Live weather, forecast, ESI gauge, pilgrim tracking, and historical analysis.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

from core.data_loader import load_and_merge_data, SHRINE_COORDS, get_shrine_data
from core.feature_engine import compute_esi, compute_ndvi_features, compute_tourism_pressure_index, get_esi_status
from core.weather_api import fetch_current_weather, fetch_forecast

st.set_page_config(page_title="Monitoring | Char Dham", page_icon="M", layout="wide")
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
    st.markdown("### Monitoring Controls")
    selected_shrine = st.selectbox("Select Shrine", list(SHRINE_COORDS.keys()), key="monitor_shrine")
    st.markdown("---")
    show_forecast = st.checkbox("Show 5-Day Forecast", value=True)

shrine_df = get_shrine_data(df, selected_shrine)

# --- Header ---
st.markdown(f"# Real-Time Monitoring: {selected_shrine}")
st.caption("Live environmental parameters, weather feeds, and pilgrim activity tracking")
st.markdown("---")

# --- Weather Panel ---
weather = fetch_current_weather(selected_shrine)

st.markdown("### Current Weather Conditions")

w1, w2, w3, w4, w5, w6 = st.columns(6)
w1.metric("Temperature", f"{weather['temp']:.1f}C", f"Feels like {weather['feels_like']:.1f}C")
w2.metric("Humidity", f"{weather['humidity']}%")
w3.metric("Wind Speed", f"{weather['wind_speed']} m/s")
w4.metric("Cloud Cover", f"{weather['clouds']}%", weather['description'])

# Rain with visual indicator
rain_val = weather.get('rain_1h', 0)
rain_delta = "Heavy" if rain_val > 5 else "Moderate" if rain_val > 1 else "None" if rain_val == 0 else "Light"
w5.metric("Rain (1h)", f"{rain_val:.1f} mm", rain_delta)

# Visibility with visual indicator
vis_val = weather.get('visibility', 10000)
vis_km = vis_val / 1000
vis_delta = "Very Low" if vis_km < 1 else "Low" if vis_km < 3 else "Moderate" if vis_km < 6 else "Good"
w6.metric("Visibility", f"{vis_km:.1f} km", vis_delta)

st.caption(f"Source: {weather.get('source', 'Unknown')} | Updated: {weather.get('timestamp', 'N/A')}")
st.markdown("---")

# --- 5-Day Forecast ---
if show_forecast:
    st.markdown("### 5-Day Weather Forecast")
    forecast_data = fetch_forecast(selected_shrine)

    if forecast_data:
        fc_df = pd.DataFrame(forecast_data)
        fc_df["datetime"] = pd.to_datetime(fc_df["datetime"])

        fig_fc = go.Figure()
        fig_fc.add_trace(go.Scatter(
            x=fc_df["datetime"], y=fc_df["temp"], mode="lines+markers",
            name="Temperature", line=dict(color="#f59e0b", width=2), marker=dict(size=4), yaxis="y",
        ))
        fig_fc.add_trace(go.Bar(
            x=fc_df["datetime"], y=fc_df["rain_3h"], name="Rain (3h)",
            marker_color="rgba(59,130,246,0.5)", yaxis="y2",
        ))
        fig_fc.update_layout(
            height=280, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"), xaxis=dict(showgrid=False),
            yaxis=dict(title="Temp (C)", showgrid=True, gridcolor="rgba(255,255,255,0.04)"),
            yaxis2=dict(title="Rain (mm)", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", y=1.08), hovermode="x unified",
            margin=dict(l=50, r=50, t=10, b=30),
        )
        st.plotly_chart(fig_fc, width='stretch')
    st.markdown("---")

# --- ESI Gauge + Pilgrim Counter ---
st.markdown("### Ecosystem Status and Pilgrim Activity")

gauge_col, counter_col = st.columns(2)

with gauge_col:
    current_esi = shrine_df["ESI"].iloc[-1]
    status, color, desc = get_esi_status(current_esi)

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=current_esi,
        delta={"reference": shrine_df["ESI"].mean(), "valueformat": ".1f", "prefix": "vs avg "},
        number={"suffix": "/100", "font": {"size": 36, "color": color}},
        title={"text": "Ecosystem Stress Index", "font": {"color": "#e2e8f0", "size": 14}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#334155"},
            "bar": {"color": color, "thickness": 0.3},
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
        height=260, margin=dict(l=20, r=20, t=50, b=10),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
    )
    st.plotly_chart(fig_gauge, width='stretch')

with counter_col:
    latest = shrine_df.iloc[-1]
    pilgrims = int(latest["Pilgrim_Count"])
    capacity = int(latest["Carrying_Capacity"])
    util = pilgrims / max(capacity, 1)

    st.metric("Latest Monthly Pilgrims", f"{pilgrims:,}")
    st.metric("Carrying Capacity", f"{capacity:,}")
    st.metric("Capacity Utilization", f"{util*100:.1f}%",
              delta="SAFE" if util < 0.6 else "WARNING" if util < 1.0 else "EXCEEDED")
    st.progress(min(util, 1.0))

st.markdown("---")

# --- Historical Analysis ---
st.markdown("### Historical Analysis")

tab_trend, tab_climate, tab_season, tab_corr = st.tabs([
    "Footfall Trends", "Climate Analysis", "Seasonality", "Correlations"
])

with tab_trend:
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=shrine_df["Date"], y=shrine_df["Pilgrim_Count"],
        mode="lines+markers", line=dict(color="#3b82f6", width=2), marker=dict(size=3),
        name="Pilgrim Count", fill="tozeroy", fillcolor="rgba(59,130,246,0.05)",
    ))
    fig_trend.add_trace(go.Scatter(
        x=shrine_df["Date"], y=shrine_df["Carrying_Capacity"],
        mode="lines", line=dict(color="#ef4444", width=1, dash="dash"), name="Capacity Limit",
    ))
    fig_trend.update_layout(
        height=380, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"), xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", title="Pilgrims"),
        hovermode="x unified", legend=dict(orientation="h", y=1.05),
    )
    st.plotly_chart(fig_trend, width='stretch')

with tab_climate:
    c1, c2 = st.columns(2)
    with c1:
        fig_temp = px.scatter(
            shrine_df, x="Avg_Temperature_C", y="Pilgrim_Count",
            color="Month", size="Pilgrim_Count", hover_data=["Year"],
            title="Temperature vs Footfall", color_continuous_scale="Viridis",
        )
        fig_temp.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"), height=380)
        st.plotly_chart(fig_temp, width='stretch')
    with c2:
        fig_rain = px.scatter(
            shrine_df, x="Rainfall_mm", y="Pilgrim_Count",
            color="Month", size="Pilgrim_Count", hover_data=["Year"],
            title="Rainfall vs Footfall", color_continuous_scale="PuBuGn",
        )
        fig_rain.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"), height=380)
        st.plotly_chart(fig_rain, width='stretch')

with tab_season:
    season_piv = shrine_df.pivot_table(index="Year", columns="Month", values="Pilgrim_Count", aggfunc="sum")
    fig_season = px.imshow(
        season_piv, aspect="auto", color_continuous_scale="YlOrRd",
        title=f"Seasonality Heatmap - {selected_shrine}",
        labels={"x": "Month", "y": "Year", "color": "Pilgrims"},
    )
    fig_season.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"), height=420)
    st.plotly_chart(fig_season, width='stretch')

with tab_corr:
    corr_cols = ["Pilgrim_Count", "Avg_Temperature_C", "Rainfall_mm",
                 "Relative_Humidity_%", "Wind_Speed_mps", "Capacity_Utilization", "ESI"]
    available = [c for c in corr_cols if c in shrine_df.columns]
    corr_matrix = shrine_df[available].corr()

    fig_corr = px.imshow(
        corr_matrix, text_auto=".2f", aspect="auto", color_continuous_scale="RdBu_r",
        zmin=-1, zmax=1, title="Feature Correlation Matrix",
    )
    fig_corr.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"), height=450)
    st.plotly_chart(fig_corr, width='stretch')
