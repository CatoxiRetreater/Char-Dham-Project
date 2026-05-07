"""
Predictions - Multi-Model Forecasting
========================================
RF (19 features), SARIMA (seasonal), LSTM with comparison, SHAP, decomposition.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

from core.data_loader import load_and_merge_data, SHRINE_COORDS, get_shrine_data
from core.feature_engine import compute_esi, compute_ndvi_features, compute_tourism_pressure_index, compute_seasonal_decomposition
from core.models import train_random_forest, train_sarima, train_lstm, rf_predict, compute_shap_values, get_available_features

st.set_page_config(page_title="Predictions | Char Dham", page_icon="M", layout="wide")
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
    st.markdown("### Prediction Controls")
    selected_shrine = st.selectbox("Select Shrine", list(SHRINE_COORDS.keys()), key="pred_shrine")
    st.markdown("---")
    st.markdown("##### Model Selection")
    use_rf = st.checkbox("Random Forest", value=True)
    use_sarima = st.checkbox("SARIMA", value=True)
    use_lstm = st.checkbox("LSTM", value=True)
    st.markdown("---")
    forecast_months = st.slider("Forecast Horizon (months)", 3, 24, 12)

shrine_df = get_shrine_data(df, selected_shrine)
if len(shrine_df) < 15:
    st.error("Insufficient data for modeling (need at least 15 records).")
    st.stop()

# --- Header ---
st.markdown(f"# Predictions: {selected_shrine}")
st.caption("Multi-model forecasting with Random Forest, SARIMA, and LSTM neural networks")
st.markdown("---")

# --- Train Models ---
available_feats = get_available_features(shrine_df)
ts_data = shrine_df.set_index("Date")["Pilgrim_Count"]

rf_result, sarima_result, lstm_result = None, None, None

if use_rf and len(available_feats) >= 3:
    rf_result = train_random_forest(shrine_df[available_feats], shrine_df["Pilgrim_Count"])

if use_sarima:
    sarima_result = train_sarima(ts_data, forecast_steps=forecast_months)

if use_lstm:
    lstm_result = train_lstm(ts_data, forecast_steps=forecast_months)

# --- Model Comparison ---
st.markdown("### Model Performance Comparison")

metrics_list = []
if rf_result:
    m = rf_result["metrics"].copy()
    m["Model"] = "Random Forest"
    m["Features"] = rf_result["n_features"]
    metrics_list.append(m)

if sarima_result and sarima_result.get("success"):
    m = sarima_result["metrics"].copy()
    order = sarima_result["order"]
    seasonal = sarima_result["seasonal_order_str"]
    m["Model"] = f"SARIMA{order}{seasonal}"
    m["AIC"] = round(sarima_result.get("aic", 0), 1)
    m["BIC"] = round(sarima_result.get("bic", 0), 1)
    metrics_list.append(m)

if lstm_result and lstm_result.get("success"):
    m = lstm_result["metrics"].copy()
    m["Model"] = "LSTM"
    metrics_list.append(m)

if metrics_list:
    best = min(metrics_list, key=lambda x: x.get("rmse", float("inf")))

    mcols = st.columns(len(metrics_list))
    for i, md in enumerate(metrics_list):
        with mcols[i]:
            is_best = md["Model"] == best["Model"]
            label = f"{md['Model']} {'(Best)' if is_best else ''}"
            st.metric(label, f"R2 = {md.get('r2', 0):.3f}")
            st.metric("RMSE", f"{md.get('rmse', 0):,.0f}")
            st.metric("MAE", f"{md.get('mae', 0):,.0f}")
            st.metric("MAPE", f"{md.get('mape', 0):.1f}%")
            if "Features" in md:
                st.caption(f"Using {md['Features']} features")
            if "AIC" in md:
                st.caption(f"AIC: {md['AIC']} | BIC: {md.get('BIC', 'N/A')}")

st.markdown("---")

# --- Forecast Chart ---
st.markdown("### Forecast Projection")

fig_forecast = go.Figure()

hist = shrine_df.tail(36)
fig_forecast.add_trace(go.Scatter(
    x=hist["Date"], y=hist["Pilgrim_Count"], mode="lines+markers",
    name="Historical", line=dict(color="#e2e8f0", width=2), marker=dict(size=3),
))
fig_forecast.add_trace(go.Scatter(
    x=hist["Date"], y=hist["Carrying_Capacity"], mode="lines",
    name="Capacity Limit", line=dict(color="#ef4444", width=1, dash="dot"),
))

if sarima_result and sarima_result.get("success"):
    d = sarima_result["future_dates"]
    fig_forecast.add_trace(go.Scatter(x=d, y=sarima_result["forecast_mean"],
        mode="lines+markers",
        name=f"SARIMA{sarima_result['order']}{sarima_result['seasonal_order_str']}",
        line=dict(color="#22c55e", width=2, dash="dash"), marker=dict(size=4)))
    fig_forecast.add_trace(go.Scatter(
        x=list(d) + list(d[::-1]),
        y=list(sarima_result["forecast_ci_upper"]) + list(sarima_result["forecast_ci_lower"][::-1]),
        fill="toself", fillcolor="rgba(34,197,94,0.08)",
        line=dict(color="rgba(0,0,0,0)"), showlegend=True, name="SARIMA 95% CI"))

if lstm_result and lstm_result.get("success"):
    d = lstm_result["future_dates"]
    fig_forecast.add_trace(go.Scatter(x=d, y=lstm_result["forecast_mean"],
        mode="lines+markers", name="LSTM",
        line=dict(color="#ec4899", width=2, dash="dash"), marker=dict(size=4, symbol="diamond")))
    fig_forecast.add_trace(go.Scatter(
        x=list(d) + list(d[::-1]),
        y=list(lstm_result["forecast_ci_upper"]) + list(lstm_result["forecast_ci_lower"][::-1]),
        fill="toself", fillcolor="rgba(236,72,153,0.08)",
        line=dict(color="rgba(0,0,0,0)"), showlegend=True, name="LSTM CI"))

if rf_result:
    last_date = shrine_df["Date"].iloc[-1]
    next_date = last_date + pd.DateOffset(months=1)
    last_feats = shrine_df[available_feats].iloc[-1:]
    rf_pred = rf_predict(rf_result["model"], last_feats)
    fig_forecast.add_trace(go.Scatter(x=[next_date], y=[rf_pred], mode="markers",
        name="RF Next Month", marker=dict(color="#3b82f6", size=12, symbol="star")))

fig_forecast.update_layout(
    height=450, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e2e8f0"), xaxis=dict(showgrid=False),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", title="Pilgrim Count"),
    hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
st.plotly_chart(fig_forecast, width='stretch')
st.markdown("---")

# --- Detailed Model Insights (Tabs) ---
st.markdown("### Model Insights")

tab_rf, tab_sarima, tab_lstm, tab_decomp = st.tabs(["Random Forest", "SARIMA", "LSTM", "Seasonal Decomposition"])

with tab_rf:
    if rf_result:
        st.caption(f"Trained with {rf_result['n_features']} features | CV R-squared: {rf_result['cv_r2_mean']:.3f} +/- {rf_result['cv_r2_std']:.3f}")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Actual vs Predicted")
            fig_ap = px.scatter(x=rf_result["y_test"], y=rf_result["y_pred"],
                labels={"x": "Actual", "y": "Predicted"}, color_discrete_sequence=["#3b82f6"])
            maxv = max(rf_result["y_test"].max(), rf_result["y_pred"].max())
            minv = min(rf_result["y_test"].min(), rf_result["y_pred"].min())
            fig_ap.add_shape(type="line", line=dict(dash="dash", color="gray"), x0=minv, y0=minv, x1=maxv, y1=maxv)
            fig_ap.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"), height=320)
            st.plotly_chart(fig_ap, width='stretch')

        with c2:
            st.markdown("#### Feature Importance")
            imp = rf_result["feature_importance"]
            imp_sorted = dict(sorted(imp.items(), key=lambda x: x[1], reverse=True))
            fig_imp = px.bar(x=list(imp_sorted.values()), y=list(imp_sorted.keys()), orientation="h",
                labels={"x": "Importance", "y": ""}, color=list(imp_sorted.values()), color_continuous_scale="Blues")
            fig_imp.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"), height=320, yaxis=dict(categoryorder="total ascending"), showlegend=False)
            st.plotly_chart(fig_imp, width='stretch')

        # SHAP
        st.markdown("#### SHAP Explainability")
        st.caption("Adjust values below to see how each feature drives the prediction:")

        n_feats = len(available_feats)
        cols_per_row = min(n_feats, 5)
        shap_inputs = {}

        for row_start in range(0, n_feats, cols_per_row):
            row_feats = available_feats[row_start:row_start + cols_per_row]
            shap_row = st.columns(len(row_feats))
            for j, feat in enumerate(row_feats):
                with shap_row[j]:
                    default = float(shrine_df[feat].mean())
                    shap_inputs[feat] = st.number_input(feat, value=default, key=f"shap_{feat}")

        shap_df = pd.DataFrame([shap_inputs])
        shap_pred = rf_predict(rf_result["model"], shap_df)
        st.metric("Predicted Pilgrim Count", f"{shap_pred:,.0f}")

        shap_result = compute_shap_values(rf_result["model"], shap_df, available_feats)
        if shap_result["success"]:
            sv = pd.DataFrame({"Feature": shap_result["feature_names"], "SHAP Value": shap_result["shap_values"]})
            sv = sv.reindex(sv["SHAP Value"].abs().sort_values(ascending=True).index)
            fig_shap = px.bar(sv, x="SHAP Value", y="Feature", orientation="h",
                color="SHAP Value", color_continuous_scale="RdBu", color_continuous_midpoint=0,
                title="Feature Contribution to Prediction")
            fig_shap.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"), height=max(280, n_feats * 22))
            st.plotly_chart(fig_shap, width='stretch')
    else:
        st.info("Random Forest model not enabled or insufficient features.")

with tab_sarima:
    if sarima_result and sarima_result.get("success"):
        order_str = f"SARIMA{sarima_result['order']}{sarima_result['seasonal_order_str']}"
        st.markdown(f"**Order:** {order_str} | **AIC:** {sarima_result['aic']:.1f} | **BIC:** {sarima_result['bic']:.1f}")

        if sarima_result.get("lb_pvalue") is not None:
            lb_pass = "Pass" if sarima_result["lb_pvalue"] > 0.05 else "Fail"
            st.caption(f"Ljung-Box Test (lag=10): p-value = {sarima_result['lb_pvalue']:.4f} ({lb_pass} — {'no' if lb_pass == 'Pass' else ''} significant autocorrelation in residuals)")

        # Actual vs Fitted + Residuals (equal to RF's visualizations)
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("#### Actual vs Fitted")
            y_actual = sarima_result["y_actual"]
            y_fitted = sarima_result["fitted_values"]
            # Align and drop NaN
            aligned = pd.DataFrame({"Actual": y_actual, "Fitted": y_fitted}).dropna()
            if not aligned.empty:
                fig_af = px.scatter(
                    x=aligned["Actual"], y=aligned["Fitted"],
                    labels={"x": "Actual", "y": "Fitted"},
                    color_discrete_sequence=["#22c55e"],
                )
                maxv = max(aligned["Actual"].max(), aligned["Fitted"].max())
                minv = min(aligned["Actual"].min(), aligned["Fitted"].min())
                fig_af.add_shape(type="line", line=dict(dash="dash", color="gray"),
                                x0=minv, y0=minv, x1=maxv, y1=maxv)
                fig_af.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0"), height=320,
                )
                st.plotly_chart(fig_af, width='stretch')

        with c2:
            st.markdown("#### Residual Distribution")
            residuals = sarima_result["residuals"].dropna()
            if not residuals.empty:
                fig_hist = px.histogram(
                    residuals, nbins=30,
                    labels={"value": "Residual", "count": "Frequency"},
                    color_discrete_sequence=["#22c55e"],
                )
                fig_hist.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0"), height=320, showlegend=False,
                )
                st.plotly_chart(fig_hist, width='stretch')

        # Residuals over time
        st.markdown("#### Residuals Over Time")
        residuals = sarima_result["residuals"].dropna()
        if not residuals.empty:
            fig_resid = go.Figure()
            fig_resid.add_trace(go.Scatter(
                x=residuals.index, y=residuals.values,
                mode="lines", line=dict(color="#22c55e", width=1.5),
                name="Residuals",
            ))
            fig_resid.add_hline(y=0, line_dash="dot", line_color="#94a3b8")
            # Add +/- 2 std bands
            std_r = residuals.std()
            fig_resid.add_hline(y=2*std_r, line_dash="dash", line_color="rgba(239,68,68,0.4)",
                                annotation_text="+2 Std", annotation_position="right")
            fig_resid.add_hline(y=-2*std_r, line_dash="dash", line_color="rgba(239,68,68,0.4)",
                                annotation_text="-2 Std", annotation_position="right")
            fig_resid.update_layout(
                height=250, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"), xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", title="Residual"),
                showlegend=False,
            )
            st.plotly_chart(fig_resid, width='stretch')

        # Forecast table
        st.markdown("#### Forecast Table")
        fc_table = pd.DataFrame({
            "Date": sarima_result["future_dates"].strftime("%Y-%m"),
            "Predicted": [f"{v:,.0f}" for v in sarima_result["forecast_mean"]],
            "Lower CI": [f"{v:,.0f}" for v in sarima_result["forecast_ci_lower"]],
            "Upper CI": [f"{v:,.0f}" for v in sarima_result["forecast_ci_upper"]],
        })
        st.dataframe(fc_table, width='stretch', hide_index=True)
    else:
        err = sarima_result.get("error", "Unknown") if sarima_result else "Not enabled"
        st.warning(f"SARIMA: {err}")

with tab_lstm:
    if lstm_result and lstm_result.get("success"):
        st.markdown("**Architecture:** LSTM(64) > Dropout(0.2) > LSTM(32) > Dropout(0.2) > Dense(16) > Dense(1)")

        if "y_test" in lstm_result and "y_pred" in lstm_result:
            c1, c2 = st.columns(2)
            with c1:
                fig_la = px.scatter(x=lstm_result["y_test"], y=lstm_result["y_pred"],
                    labels={"x": "Actual", "y": "Predicted"}, title="LSTM: Actual vs Predicted",
                    color_discrete_sequence=["#ec4899"])
                fig_la.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"), height=320)
                st.plotly_chart(fig_la, width='stretch')
            with c2:
                fc_l = pd.DataFrame({
                    "Date": lstm_result["future_dates"].strftime("%Y-%m"),
                    "Predicted": [f"{max(0,v):,.0f}" for v in lstm_result["forecast_mean"]],
                    "Lower CI": [f"{max(0,v):,.0f}" for v in lstm_result["forecast_ci_lower"]],
                    "Upper CI": [f"{max(0,v):,.0f}" for v in lstm_result["forecast_ci_upper"]],
                })
                st.dataframe(fc_l, width='stretch', hide_index=True)
    else:
        err = lstm_result.get("error", "Unknown") if lstm_result else "Not enabled"
        st.warning(f"LSTM: {err}")

with tab_decomp:
    st.markdown("#### Seasonal Decomposition (STL)")
    decomp = compute_seasonal_decomposition(ts_data)

    for name, color in [("Observed", "#e2e8f0"), ("Trend", "#22c55e"), ("Seasonal", "#3b82f6"), ("Residual", "#f59e0b")]:
        series = decomp[name.lower()]
        fig_c = go.Figure()
        fig_c.add_trace(go.Scatter(x=series.index, y=series.values, mode="lines",
            line=dict(color=color, width=1.5), name=name))
        fig_c.update_layout(title=name, height=180, margin=dict(l=50, r=20, t=30, b=20),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0", size=11), xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)"), showlegend=False)
        st.plotly_chart(fig_c, width='stretch')
