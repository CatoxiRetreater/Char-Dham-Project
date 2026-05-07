"""
Home - Char Dham Intelligence Dashboard
==========================================
Interactive overview with filters, shrine cards, ESI chart, and alerts banner.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path

from core.data_loader import load_and_merge_data, get_summary_stats, SHRINE_COORDS
from core.feature_engine import compute_esi, compute_ndvi_features, compute_tourism_pressure_index, get_esi_status
from core.weather_api import get_all_shrine_weather
from core.alerts import generate_all_alerts

# --- Page Config ---
st.set_page_config(
    page_title="Char Dham Dashboard",
    page_icon="M",
    layout="wide",
    initial_sidebar_state="expanded",
)

css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# --- Data ---
@st.cache_data(ttl=3600)
def prepare_data():
    df = load_and_merge_data()
    if df.empty:
        return df
    df["ESI"] = compute_esi(df)
    df = compute_ndvi_features(df)
    df["TPI"] = compute_tourism_pressure_index(df)
    return df

df = prepare_data()

if df.empty:
    st.error("Failed to load datasets. Ensure data files are in the data/ directory.")
    st.stop()

st.session_state["df"] = df

# --- Sidebar ---
with st.sidebar:
    st.markdown("### Char Dham Dashboard")
    st.caption("AI-Powered Tourism & Ecosystem Intelligence")
    st.markdown("---")

    st.markdown("##### Live Weather")
    weather_data = get_all_shrine_weather()
    st.session_state["weather_data"] = weather_data

    for shrine_name, w in weather_data.items():
        source_tag = "LIVE" if "API" in w.get("source", "") else "HIST"
        rain_str = f" | {w.get('rain_1h', 0):.1f}mm/h" if w.get("rain_1h", 0) > 0 else ""
        st.markdown(
            f'<div class="info-card">'
            f'<div style="display:flex;justify-content:space-between;">'
            f'<b>{shrine_name}</b>'
            f'<span style="font-size:0.65rem;color:#64748b;">{source_tag}</span>'
            f'</div>'
            f'<div style="margin-top:4px;font-size:0.78rem;color:#94a3b8;">'
            f'{w["temp"]:.1f}C &nbsp; {w["humidity"]}% RH &nbsp; {w["wind_speed"]} m/s{rain_str}'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.caption("Data refreshes every 30 minutes")

# --- Header ---
st.markdown("# Char Dham Ecosystem Intelligence")
st.caption("Real-time monitoring of tourism pressure, climate impact, and ecosystem health across Kedarnath, Badrinath, Gangotri and Yamunotri")
st.markdown("---")

# --- Filters ---
filter_cols = st.columns([2, 2, 1])

with filter_cols[0]:
    all_shrines = list(SHRINE_COORDS.keys())
    selected_shrines = st.multiselect(
        "Filter Shrines",
        all_shrines,
        default=all_shrines,
        key="home_shrine_filter",
    )
    if not selected_shrines:
        selected_shrines = all_shrines

with filter_cols[1]:
    year_min, year_max = int(df["Year"].min()), int(df["Year"].max())
    year_range = st.slider(
        "Year Range",
        min_value=year_min,
        max_value=year_max,
        value=(year_min, year_max),
        key="home_year_filter",
    )

with filter_cols[2]:
    season_filter = st.selectbox(
        "Season",
        ["All", "Peak Season", "Off Season"],
        key="home_season_filter",
    )

# Apply filters
filtered_df = df[
    (df["Shrine"].isin(selected_shrines)) &
    (df["Year"] >= year_range[0]) &
    (df["Year"] <= year_range[1])
]
if season_filter == "Peak Season":
    filtered_df = filtered_df[filtered_df["Peak_Season"] == 1]
elif season_filter == "Off Season":
    filtered_df = filtered_df[filtered_df["Peak_Season"] == 0]

if filtered_df.empty:
    st.warning("No data matches the selected filters. Adjust your selections above.")
    st.stop()

st.markdown("---")

# --- KPI Row ---
stats = get_summary_stats(filtered_df)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Pilgrims", f"{stats['total_pilgrims']:,}", f"{year_range[1] - year_range[0] + 1} years")
k2.metric("Avg Monthly", f"{stats['avg_pilgrims_monthly']:,}")

latest_month_total = filtered_df[filtered_df["Date"] == filtered_df["Date"].max()]["Pilgrim_Count"].sum()
k3.metric("Latest Month", f"{latest_month_total:,}")

avg_esi = filtered_df.groupby("Shrine")["ESI"].last().mean()
esi_label, _, _ = get_esi_status(avg_esi)
k4.metric("Avg ESI", f"{avg_esi:.1f}", esi_label)

# Alerts — always computed on full latest data (not filtered subset)
all_alerts = []
for shrine in SHRINE_COORDS:
    all_alerts.extend(generate_all_alerts(df, shrine))
high_alerts = sum(1 for a in all_alerts if a.level.priority >= 2)
k5.metric("Active Alerts", str(high_alerts), f"of {len(all_alerts)} total")

st.markdown("---")

# --- Alerts Summary Banner ---
critical_alerts = [a for a in all_alerts if a.level.priority >= 2]
if critical_alerts:
    sorted_alerts = sorted(critical_alerts, key=lambda a: a.level.priority, reverse=True)
    top_alerts = sorted_alerts[:3]

    st.markdown("### Active Alerts")
    alert_cols = st.columns(len(top_alerts))
    for i, alert in enumerate(top_alerts):
        with alert_cols[i]:
            if alert.level.name == "CRITICAL":
                st.error(f"**{alert.shrine}** — {alert.title}")
            else:
                st.warning(f"**{alert.shrine}** — {alert.title}")
            st.caption(alert.recommendation[:100])
    st.markdown("---")

# --- Shrine Status ---
st.markdown("### Shrine Status Overview")

active_shrines = [s for s in SHRINE_COORDS.keys() if s in selected_shrines]
cols = st.columns(len(active_shrines) if active_shrines else 1)

for idx, shrine in enumerate(active_shrines):
    with cols[idx]:
        shrine_df = filtered_df[filtered_df["Shrine"] == shrine]
        if shrine_df.empty:
            st.info(f"No data for {shrine}")
            continue

        latest = shrine_df.iloc[-1]
        esi = latest["ESI"]
        status, color, _ = get_esi_status(esi)
        pilgrims = int(latest["Pilgrim_Count"])
        capacity = int(latest["Carrying_Capacity"])
        util = pilgrims / max(capacity, 1) * 100
        w = weather_data.get(shrine, {})
        live_temp = w.get("temp", latest.get("Avg_Temperature_C", 0))
        ndvi = latest.get("NDVI", 0)
        coords = SHRINE_COORDS[shrine]

        # ESI gauge (compact)
        fig_mini = go.Figure(go.Indicator(
            mode="gauge+number",
            value=esi,
            number={"suffix": "", "font": {"size": 28, "color": color}},
            gauge={
                "axis": {"range": [0, 100], "visible": False},
                "bar": {"color": color, "thickness": 0.4},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 40], "color": "rgba(34,197,94,0.10)"},
                    {"range": [40, 70], "color": "rgba(245,158,11,0.10)"},
                    {"range": [70, 100], "color": "rgba(239,68,68,0.10)"},
                ],
            },
        ))
        fig_mini.update_layout(
            height=130, margin=dict(l=10, r=10, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
        )
        st.plotly_chart(fig_mini, width='stretch')

        st.markdown(f"**{shrine}** — {status}")
        st.caption(f"{coords['district']} | {coords['alt']}m")

        c1, c2 = st.columns(2)
        c1.metric("Pilgrims", f"{pilgrims:,}")
        c2.metric("Temp", f"{live_temp:.1f}C")

        # Capacity progress bar
        util_frac = min(util / 100, 1.0)
        st.progress(util_frac, text=f"Capacity: {util:.0f}%")

        # NDVI health badge
        if ndvi >= 0.5:
            st.success(f"NDVI: {ndvi:.3f} — Healthy")
        elif ndvi >= 0.35:
            st.info(f"NDVI: {ndvi:.3f} — Moderate")
        else:
            st.warning(f"NDVI: {ndvi:.3f} — Sparse")

st.markdown("---")

# --- ESI Comparison ---
st.markdown("### Ecosystem Stress Index")

# ESI filters
esi_filter_cols = st.columns([2, 3])
with esi_filter_cols[0]:
    esi_time_range = st.selectbox(
        "Time Range",
        ["All Data", "Last 1 Year", "Last 3 Years", "Last 5 Years"],
        key="esi_time_range",
    )
with esi_filter_cols[1]:
    esi_shrines = st.multiselect(
        "Shrines on Chart",
        all_shrines,
        default=selected_shrines,
        key="esi_shrine_filter",
    )
    if not esi_shrines:
        esi_shrines = selected_shrines

# Apply ESI time filter
esi_df = df[df["Shrine"].isin(esi_shrines)]
if esi_time_range == "Last 1 Year":
    cutoff = esi_df["Date"].max() - pd.DateOffset(years=1)
    esi_df = esi_df[esi_df["Date"] >= cutoff]
elif esi_time_range == "Last 3 Years":
    cutoff = esi_df["Date"].max() - pd.DateOffset(years=3)
    esi_df = esi_df[esi_df["Date"] >= cutoff]
elif esi_time_range == "Last 5 Years":
    cutoff = esi_df["Date"].max() - pd.DateOffset(years=5)
    esi_df = esi_df[esi_df["Date"] >= cutoff]

shrine_colors = {"Kedarnath": "#22c55e", "Badrinath": "#3b82f6", "Gangotri": "#f59e0b", "Yamunotri": "#ec4899"}

fig_esi = go.Figure()
for shrine in esi_shrines:
    shrine_data = esi_df[esi_df["Shrine"] == shrine]
    if shrine_data.empty:
        continue
    fig_esi.add_trace(go.Scatter(
        x=shrine_data["Date"], y=shrine_data["ESI"],
        mode="lines+markers", name=shrine,
        line=dict(color=shrine_colors.get(shrine, "#94a3b8"), width=2), marker=dict(size=3),
    ))

fig_esi.add_hrect(y0=0, y1=40, fillcolor="rgba(34,197,94,0.04)", line_width=0)
fig_esi.add_hrect(y0=40, y1=70, fillcolor="rgba(245,158,11,0.04)", line_width=0)
fig_esi.add_hrect(y0=70, y1=100, fillcolor="rgba(239,68,68,0.04)", line_width=0)

fig_esi.update_layout(
    height=380, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e2e8f0"),
    xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", title="ESI (0-100)", range=[0, 100]),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_esi, width='stretch')
