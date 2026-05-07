"""
Geospatial - Satellite-Based Geospatial Intelligence
======================================================
Interactive Folium maps, NDVI heatmaps, LULC classification, and NDVI trends.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from streamlit_folium import st_folium

from core.data_loader import load_and_merge_data, SHRINE_COORDS, get_shrine_data
from core.feature_engine import compute_esi, compute_ndvi_features, compute_tourism_pressure_index
from core.geospatial import (
    get_gee_status, get_ndvi_source, create_shrine_overview_map, create_ndvi_map,
    create_lulc_map, get_ndvi_timeseries, get_lulc_data, SHRINE_REGIONS, LULC_COLORS
)
from core.weather_api import get_all_shrine_weather

st.set_page_config(page_title="Geospatial | Char Dham", page_icon="M", layout="wide")
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
    st.markdown("### Map Controls")
    selected_shrine = st.selectbox("Select Shrine", list(SHRINE_COORDS.keys()), key="geo_shrine")
    st.markdown("---")

    ndvi_source = get_ndvi_source()
    st.info(f"NDVI Source: {ndvi_source}")

    gee_ok, gee_msg = get_gee_status()
    if gee_ok:
        st.success(f"GEE: {gee_msg}")
    else:
        st.caption("GEE: Offline — using alternative NDVI source")

# --- Header ---
st.markdown("# Geospatial Intelligence")
st.caption("Satellite-based NDVI analysis, land cover classification, and interactive shrine mapping")
st.markdown("---")

# --- Tabs ---
tab_overview, tab_ndvi, tab_lulc, tab_trends = st.tabs([
    "Shrine Overview Map", "NDVI Heatmap", "Land Cover", "NDVI Trends"
])

with tab_overview:
    st.markdown("### Char Dham Shrine Status Map")
    st.caption("Interactive map showing all 4 shrines with capacity utilization, pilgrim counts, and live weather data.")

    weather = st.session_state.get("weather_data") or get_all_shrine_weather()
    m = create_shrine_overview_map(df, weather)
    st_folium(m, width=None, height=500, returned_objects=[])

    # Comparison table
    st.markdown("#### Shrine Comparison")
    comp_rows = []
    for shrine in SHRINE_COORDS:
        sdf = df[df["Shrine"] == shrine]
        if sdf.empty:
            continue
        latest = sdf.iloc[-1]
        info = SHRINE_REGIONS[shrine]
        w = weather.get(shrine, {})
        comp_rows.append({
            "Shrine": shrine,
            "District": info["district"],
            "Altitude (m)": info["alt"],
            "Pilgrims": int(latest["Pilgrim_Count"]),
            "Capacity": int(latest["Carrying_Capacity"]),
            "Utilization": f"{latest['Pilgrim_Count']/max(latest['Carrying_Capacity'],1)*100:.0f}%",
            "ESI": f"{latest['ESI']:.1f}",
            "NDVI": f"{latest.get('NDVI', 0):.3f}",
            "Temp (C)": f"{w.get('temp', latest.get('Avg_Temperature_C', 0)):.1f}",
        })
    st.dataframe(pd.DataFrame(comp_rows), width='stretch', hide_index=True)

with tab_ndvi:
    st.markdown(f"### NDVI Heatmap: {selected_shrine}")
    st.caption(f"Data source: {get_ndvi_source()}")

    ndvi_map = create_ndvi_map(selected_shrine)
    st_folium(ndvi_map, width=None, height=500, returned_objects=[])

    current_ndvi = df[df["Shrine"] == selected_shrine]["NDVI"].iloc[-1] if not df[df["Shrine"] == selected_shrine].empty else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Current NDVI", f"{current_ndvi:.3f}")
    c2.metric("Base NDVI", f"{SHRINE_REGIONS[selected_shrine]['base_ndvi']:.3f}")
    c3.metric("Change", f"{current_ndvi - SHRINE_REGIONS[selected_shrine]['base_ndvi']:+.3f}")

with tab_lulc:
    st.markdown(f"### Land Use / Land Cover: {selected_shrine}")

    lulc_map = create_lulc_map(selected_shrine)
    st_folium(lulc_map, width=None, height=450, returned_objects=[])

    # LULC bar chart
    lulc = get_lulc_data(selected_shrine)
    fig_lulc = px.bar(
        x=list(lulc.keys()), y=list(lulc.values()),
        color=list(lulc.keys()), color_discrete_map=LULC_COLORS,
        labels={"x": "Land Cover Class", "y": "Area (%)"},
        title=f"Land Cover Distribution - {selected_shrine}",
    )
    fig_lulc.update_layout(
        height=350, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"), showlegend=False,
        xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)"),
    )
    st.plotly_chart(fig_lulc, width='stretch')

with tab_trends:
    st.markdown(f"### NDVI Time Series: {selected_shrine}")
    ndvi_ts = get_ndvi_timeseries(selected_shrine, years=10)

    if not ndvi_ts.empty:
        fig_ndvi = go.Figure()
        fig_ndvi.add_trace(go.Scatter(
            x=ndvi_ts.index, y=ndvi_ts["NDVI"], mode="lines+markers",
            name="NDVI", line=dict(color="#22c55e", width=2), marker=dict(size=3),
            fill="tozeroy", fillcolor="rgba(34,197,94,0.06)",
        ))

        # Trend line
        if len(ndvi_ts) > 4:
            z = np.polyfit(range(len(ndvi_ts)), ndvi_ts["NDVI"].values, 1)
            trend_y = np.polyval(z, range(len(ndvi_ts)))
            fig_ndvi.add_trace(go.Scatter(
                x=ndvi_ts.index, y=trend_y, mode="lines", name="Trend",
                line=dict(color="#ef4444", width=1.5, dash="dash"),
            ))

        # Healthy threshold
        fig_ndvi.add_hline(y=0.5, line_dash="dot", line_color="#f59e0b", annotation_text="Healthy Threshold")

        fig_ndvi.update_layout(
            height=400, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"), xaxis=dict(showgrid=False, title=""),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", title="NDVI", range=[0, 0.85]),
            hovermode="x unified", legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig_ndvi, width='stretch')

        # Stats
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Mean NDVI", f"{ndvi_ts['NDVI'].mean():.3f}")
        s2.metric("Min NDVI", f"{ndvi_ts['NDVI'].min():.3f}")
        s3.metric("Max NDVI", f"{ndvi_ts['NDVI'].max():.3f}")
        trend_pct = (ndvi_ts['NDVI'].iloc[-1] - ndvi_ts['NDVI'].iloc[0]) / max(ndvi_ts['NDVI'].iloc[0], 0.01) * 100
        s4.metric("Total Change", f"{trend_pct:+.1f}%")
    else:
        st.info("No NDVI data available for this shrine.")
