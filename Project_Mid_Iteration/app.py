import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import statsmodels.api as sm
import numpy as np
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="Tourism Pressure & Ecosystem Stress",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS (Dark Mode & Premium UI) ---
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #00E676;
    }
    
    /* Metric Cards */
    div[data-testid="stMetricValue"] {
        font-size: 2.2rem;
        font-weight: 800;
        color: #00E676;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 1.1rem;
        color: #B0BEC5;
        font-weight: 500;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #1E2127;
        border-radius: 8px;
        color: #FAFAFA;
        padding: 10px 24px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #2A2E35;
    }
    .stTabs [aria-selected="true"] {
        background-color: #00E676;
        color: #0E1117 !important;
        font-weight: 800;
    }
    
    /* Alert Customization */
    .stAlert {
        border-radius: 10px;
        padding: 15px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# --- Data Loading and Processing ---
@st.cache_data
def load_data():
    try:
        # Load datasets
        df_footfall = pd.read_excel('Tourist Footfall Dataset.xlsx')
        df_climate = pd.read_excel('Climate Dataset.xlsx')
        
        # Merge datasets
        merge_cols = ['Year', 'Month', 'Shrine', 'District']
        df = pd.merge(df_footfall, df_climate, on=merge_cols, how='inner', suffixes=('_drop', ''))
        
        # Drop duplicate columns from footfall dataset
        df = df[[col for col in df.columns if not col.endswith('_drop')]]
        
        # --- HIDDEN BACKEND LOGIC (Mid-Term Evaluation Constraints) ---
        # Backend processing for Waste and Satellite Data
        if 'Estimated_Waste_Tons' not in df.columns:
            # Synthetic placeholder if not in dataset
            df['Estimated_Waste_Tons'] = df['Pilgrim_Count'] * 0.005 # 5kg waste per pilgrim
        else:
            # Logic exists, but purely backend
            df['Estimated_Waste_Tons_Processed'] = df['Estimated_Waste_Tons'] * 1.1 
            
        # Synthetic placeholders for Satellite/GIS data (Backend only)
        df['NDVI'] = np.random.uniform(0.2, 0.8, size=len(df))
        df['Forest_Cover_Loss_Ha'] = np.random.uniform(0, 5, size=len(df))
        # -----------------------------------------------------------------
        
        # Create a date column for time series plotting
        df['Date'] = pd.to_datetime(df['Year'].astype(str) + '-' + df['Month'].astype(str) + '-01')
        df = df.sort_values('Date')
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}\\n\\nPlease ensure 'Tourist Footfall Dataset.xlsx' and 'Climate Dataset.xlsx' are present in the app directory.")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.stop()

# --- Sidebar ---
st.sidebar.markdown('<h2><span style="color:#00E676"></span> Dashboard Controls</h2>', unsafe_allow_html=True)
st.sidebar.markdown("---")

available_shrines = df['Shrine'].unique().tolist()
selected_shrine = st.sidebar.selectbox("Select Shrine", available_shrines)

# Filter data based on selection
df_filtered = df[df['Shrine'] == selected_shrine].copy()

# --- Calculate Ecosystem Stress Index (ESI) ---
mean_temp = df_filtered['Avg_Temperature_C'].mean()
mean_rain = df_filtered['Rainfall_mm'].mean()
temp_dev = np.abs(df_filtered['Avg_Temperature_C'] - mean_temp)
rain_dev = np.abs(df_filtered['Rainfall_mm'] - mean_rain)

temp_max = temp_dev.max() if temp_dev.max() > 0 else 1
rain_max = rain_dev.max() if rain_dev.max() > 0 else 1
temp_dev_norm = temp_dev / temp_max
rain_dev_norm = rain_dev / rain_max

capacity_ratio = df_filtered['Pilgrim_Count'] / df_filtered['Carrying_Capacity']
capacity_ratio_norm = np.clip(capacity_ratio, 0, 1.5) / 1.5

df_filtered['ESI'] = ((capacity_ratio_norm * 0.6) + (temp_dev_norm * 0.2) + (rain_dev_norm * 0.2)) * 100
df_filtered['ESI'] = np.clip(df_filtered['ESI'], 0, 100)

st.sidebar.markdown("---")
st.sidebar.markdown("### Live Weather (Mock Data)")
import datetime
import random
current_month = datetime.datetime.now().month
# Historical ranges for selected shrine and month
hist_month_df = df_filtered[df_filtered['Month'] == current_month]
if not hist_month_df.empty:
    b_temp = hist_month_df['Avg_Temperature_C'].mean()
    b_rain = hist_month_df['Rainfall_mm'].mean()
else:
    b_temp = df_filtered['Avg_Temperature_C'].mean()
    b_rain = df_filtered['Rainfall_mm'].mean()

# Mock live values adding slight noise
mock_temp = b_temp + random.uniform(-2.0, 2.0)
mock_rain = max(0, b_rain + random.uniform(-10.0, 10.0))
mock_humidity = random.uniform(50.0, 85.0)

s_col1, s_col2, s_col3 = st.sidebar.columns(3)
s_col1.metric("Temp", f"{mock_temp:.1f} °C")
s_col2.metric("Rain", f"{mock_rain:.1f} mm")
s_col3.metric("Humid", f"{mock_humidity:.0f} %")

st.sidebar.info("Live weather simulated based on historical climate ranges for current month. Replace with OpenWeatherMap API later.")

# --- Main Content ---
st.markdown(f"<h1>AI Tourism Pressure Dashboard: <span style='color:#FFFFFF'>{selected_shrine}</span></h1>", unsafe_allow_html=True)
st.markdown("Monitor historical footfall and predict future carrying capacity violations to proactively manage ecosystem stress.")
st.write("")

# Top Level Metrics
col1, col2, col3 = st.columns(3)
with col1:
    latest_pilgrims = df_filtered['Pilgrim_Count'].iloc[-1]
    st.metric("Latest Monthly Pilgrims", f"{latest_pilgrims:,.0f}")
with col2:
    avg_temp = df_filtered['Avg_Temperature_C'].mean()
    st.metric("Average Temperature", f"{avg_temp:.1f} °C")
with col3:
    capacity = df_filtered['Carrying_Capacity'].iloc[0]
    st.metric("Ecosystem Carrying Capacity", f"{capacity:,.0f}")

st.markdown("---")

# --- Ecosystem Health Overview ---
st.markdown("Ecosystem Health Overview")

current_esi = df_filtered['ESI'].iloc[-1]
if current_esi < 40:
    light_color = "#00E676" # Green
    status = "LOW"
elif current_esi < 75:
    light_color = "#FFD600" # Yellow
    status = "MODERATE"
else:
    light_color = "#FF1744" # Red
    status = "CRITICAL"

health_col1, health_col2 = st.columns([1, 2])
with health_col1:
    st.markdown("#### Traffic Light Indicator")
    st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: center; flex-direction: column; height: 100%; padding-top: 10px;">
            <div style="width: 100px; height: 100px; border-radius: 50%; background-color: {light_color}; box-shadow: 0 0 20px {light_color}; margin-bottom: 20px;"></div>
            <h3 style="color: {light_color}; margin: 0;">{status} STRESS</h3>
            <p style="color: #B0BEC5; text-align: center; font-size: 1.1rem; margin-top: 10px;">Ecosystem stress is {status.lower()}.</p>
        </div>
    """, unsafe_allow_html=True)

with health_col2:
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = current_esi,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Current Ecosystem Stress Index (ESI)", 'font': {'color': '#FAFAFA'}},
        gauge = {
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': light_color},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 40], 'color': 'rgba(0, 230, 118, 0.3)'},
                {'range': [40, 75], 'color': 'rgba(255, 214, 0, 0.3)'},
                {'range': [75, 100], 'color': 'rgba(255, 23, 68, 0.3)'}
            ],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': current_esi
            }
        }
    ))
    fig_gauge.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#FAFAFA'))
    st.plotly_chart(fig_gauge, width='stretch')

st.markdown("---")

# --- Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(["Historical Trends", "Climate EDA", "AI Early Warning System", "Geospatial Monitoring"])

with tab1:
    st.markdown("### Historical Pilgrim Footfall")
    
    # Interactive Plotly Line Chart
    fig_trend = px.line(
        df_filtered, 
        x='Date', 
        y='Pilgrim_Count', 
        title=f'Pilgrim Footfall Over Time ({selected_shrine})',
        markers=True,
        color_discrete_sequence=['#00E676']
    )
    
    fig_trend.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#FAFAFA'),
        xaxis=dict(showgrid=False, title="Timeline"),
        yaxis=dict(showgrid=True, gridcolor='#333333', title='Number of Pilgrims'),
        hovermode="x unified"
    )
    st.plotly_chart(fig_trend, width='stretch')

    st.markdown("---")
    st.markdown("### Ecosystem Stress Index Trend")
    fig_esi_trend = px.line(
        df_filtered, 
        x='Date', 
        y='ESI', 
        title=f'Ecosystem Stress Index Over Time ({selected_shrine})',
        markers=True,
        color_discrete_sequence=['#FFD600']
    )
    fig_esi_trend.add_hrect(y0=0, y1=40, line_width=0, fillcolor="green", opacity=0.1)
    fig_esi_trend.add_hrect(y0=40, y1=75, line_width=0, fillcolor="yellow", opacity=0.1)
    fig_esi_trend.add_hrect(y0=75, y1=100, line_width=0, fillcolor="red", opacity=0.1)
    
    fig_esi_trend.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#FAFAFA'),
        xaxis=dict(showgrid=False, title="Timeline"),
        yaxis=dict(showgrid=True, gridcolor='#333333', title='Stress Index (0-100)'),
        hovermode="x unified"
    )
    st.plotly_chart(fig_esi_trend, width='stretch')

with tab2:
    st.markdown("### Climate Impact Analysis")
    st.markdown("Explore how climatic factors (Temperature and Rainfall) correlate with visitor numbers.")
    
    col_plot1, col_plot2 = st.columns(2)
    
    with col_plot1:
        # Scatter Plot: Temp vs Pilgrims
        fig_temp = px.scatter(
            df_filtered, 
            x='Avg_Temperature_C', 
            y='Pilgrim_Count',
            color='Month',
            size='Pilgrim_Count',
            hover_data=['Year'],
            title="Temperature vs Pilgrim Footfall",
            color_continuous_scale="Viridis",
            trendline="ols" if len(df_filtered) > 10 else None
        )
        fig_temp.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#FAFAFA'))
        fig_temp.update_traces(marker=dict(line=dict(width=1, color='DarkSlateGrey')))
        st.plotly_chart(fig_temp, width='stretch')

    with col_plot2:
        # Scatter Plot: Rainfall vs Pilgrims
        fig_rain = px.scatter(
            df_filtered, 
            x='Rainfall_mm', 
            y='Pilgrim_Count',
            color='Month',
            size='Pilgrim_Count',
            hover_data=['Year'],
            title="Rainfall vs Pilgrim Footfall",
            color_continuous_scale="PuBuGn",
            trendline="lowess" if len(df_filtered) > 10 else None
        )
        fig_rain.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#FAFAFA'))
        fig_rain.update_traces(marker=dict(line=dict(width=1, color='DarkSlateGrey')))
        st.plotly_chart(fig_rain, width='stretch')

    st.markdown("---")
    st.markdown("### 🗓️ Seasonality Heatmap")
    # Pivot table for Seasonality
    season_df = df_filtered.pivot_table(index='Year', columns='Month', values='Pilgrim_Count', aggfunc='sum')
    fig_season = px.imshow(
        season_df, 
        text_auto=False, 
        aspect="auto", 
        color_continuous_scale="YlOrRd", 
        title="Pilgrim Footfall Seasonality (Highlighting Peaks)"
    )
    fig_season.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#FAFAFA'))
    st.plotly_chart(fig_season, width='stretch')

    st.markdown("---")
    st.markdown("### 🔗 Correlation Analysis")
    # Correlation Matrix (Strictly EXCLUDING Waste per Evaluation Constraints)
    corr_cols = ['Pilgrim_Count', 'Avg_Temperature_C', 'Rainfall_mm']
    corr_df = df_filtered[corr_cols].corr()
    
    fig_corr = px.imshow(
        corr_df, 
        text_auto=True, 
        aspect="auto", 
        color_continuous_scale="RdBu_r", 
        zmin=-1, 
        zmax=1, 
        title="Feature Correlation Matrix"
    )
    fig_corr.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#FAFAFA'))
    st.plotly_chart(fig_corr, width='stretch')

with tab3:
    st.markdown("### AI-Powered Footfall Prediction")
    st.markdown("Leverage Machine Learning to predict future footfall based on expected climate conditions. Helps in proactive management of ecosystem stress before limits are breached.")
    
    # --- Model Training ---
    features = ['Month', 'Avg_Temperature_C', 'Rainfall_mm']
    X = df_filtered[features]
    y = df_filtered['Pilgrim_Count']
    
    if len(X) < 10:
        st.warning("Insufficient historical data (minimum 10 records) to train and evaluate the AI model for this shrine.")
    else:
        # 1. Train/Test Split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # 2. Train Model
        model = RandomForestRegressor(n_estimators=150, random_state=42, max_depth=10)
        model.fit(X_train, y_train)

        
        # Predictions on test set for evaluation
        y_pred = model.predict(X_test)
        
        # Calculate Metrics
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        # 3. Model Insights UI
        with st.expander("📊 Model Insights & Training Visualizations", expanded=False):
            st.markdown("#### A. Model Performance")
            metric_cols = st.columns(3)
            metric_cols[0].metric("RMSE (Root Mean Squared Error)", f"{rmse:,.1f}")
            metric_cols[1].metric("MAE (Mean Absolute Error)", f"{mae:,.1f}")
            metric_cols[2].metric("R² Score", f"{r2:.3f}")
            
            st.markdown("---")
            
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                st.markdown("#### B. Actual vs Predicted")
                fig_act_pred = px.scatter(
                    x=y_test, y=y_pred, 
                    labels={'x': 'Actual Pilgrim Count', 'y': 'Predicted Pilgrim Count'},
                    title="Actual vs Predicted on Test Set",
                    color_discrete_sequence=['#00E676']
                )
                # Diagonal reference line
                max_val = max(y_test.max(), y_pred.max())
                min_val = min(y_test.min(), y_pred.min())
                fig_act_pred.add_shape(
                    type="line", line=dict(dash="dash", color="gray"),
                    x0=min_val, y0=min_val, x1=max_val, y1=max_val
                )
                fig_act_pred.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#FAFAFA'))
                st.plotly_chart(fig_act_pred, width='stretch')

            with chart_col2:
                st.markdown("#### C. Feature Importance")
                importances = model.feature_importances_
                fig_imp = px.bar(
                    x=importances, y=features, orientation='h',
                    labels={'x': 'Importance Score', 'y': 'Feature'},
                    title="Random Forest Feature Importance",
                    color=importances, color_continuous_scale="Viridis"
                )
                fig_imp.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#FAFAFA'), yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_imp, width='stretch')

            st.markdown("#### D. Prediction Residual Distribution")
            residuals = y_test - y_pred
            fig_resid = px.histogram(
                x=residuals, nbins=20,
                labels={'x': 'Residual Error (Actual - Predicted)'},
                title="Distribution of Prediction Errors",
                color_discrete_sequence=['#E91E63']
            )
            fig_resid.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#FAFAFA'))
            fig_resid.add_vline(x=0, line_dash="dash", line_color="white")
            st.plotly_chart(fig_resid, width='stretch')

        st.markdown("---")
        
        st.markdown("#### ⚙️ Select Forecasting Model for Alert System")
        model_choice = st.radio("Choose AI Model", ["RandomForest (Climate-based)", "ARIMA (Time Series)"], horizontal=True)
        
        st.markdown("---")
        
        # --- 1. Compute RandomForest Output ---
        st.markdown("#### 🎛️ Configure Climate Scenario (Next Month for RF)")
        
        sim_container = st.container()
        with sim_container:
            sim_col1, sim_col2, sim_col3 = st.columns(3)
            
            with sim_col1:
                input_month = st.slider("Target Month (1-12)", min_value=1, max_value=12, value=6, help="1=January, 12=December")
            with sim_col2:
                min_temp = float(df_filtered['Avg_Temperature_C'].min())
                max_temp = float(df_filtered['Avg_Temperature_C'].max())
                input_temp = st.slider("Expected Avg Temp (°C)", 
                                       min_value=max(-20.0, min_temp-10.0), 
                                       max_value=max_temp+10.0, 
                                       value=float(df_filtered['Avg_Temperature_C'].mean()))
            with sim_col3:
                min_rain = float(df_filtered['Rainfall_mm'].min())
                max_rain = float(df_filtered['Rainfall_mm'].max())
                input_rain = st.slider("Expected Rainfall (mm)", 
                                       min_value=max(0.0, min_rain-50.0), 
                                       max_value=max_rain+150.0, 
                                       value=float(df_filtered['Rainfall_mm'].mean()))
                
        rf_input_data = pd.DataFrame({'Month': [input_month], 'Avg_Temperature_C': [input_temp], 'Rainfall_mm': [input_rain]})
        rf_predicted_footfall = model.predict(rf_input_data)[0]
        
        st.markdown("---")
        
        # --- 2. Compute ARIMA Output ---
        ts_data = df_filtered.set_index('Date')['Pilgrim_Count']
        arima_success = False
        try:
            arima_model = sm.tsa.ARIMA(ts_data, order=(1, 1, 1))
            arima_result = arima_model.fit()
            
            forecast_steps = 12
            forecast = arima_result.get_forecast(steps=forecast_steps)
            mean_forecast = forecast.predicted_mean
            conf_int = forecast.conf_int()
            
            last_date = ts_data.index[-1]
            future_dates = [last_date + pd.DateOffset(months=i) for i in range(1, forecast_steps + 1)]
            
            arima_predicted_footfall = mean_forecast.iloc[0]
            arima_success = True
        except Exception as e:
            st.error(f"ARIMA modeling failed. Ensure enough contiguous historical data is available. Error: {e}")
            arima_predicted_footfall = df_filtered['Pilgrim_Count'].mean()
            
        # --- 3. Model Comparison Chart ---
        st.markdown("#### 📊 Model Comparison & 12-Month Projection")
        
        fig_comp = go.Figure()
        
        # Historical Data (Last 12 months for clarity)
        fig_comp.add_trace(go.Scatter(
            x=ts_data.index[-12:], y=ts_data.values[-12:], 
            mode='lines+markers', name='Historical (Last 12m)',
            line=dict(color='#FAFAFA')
        ))
        
        # Plot ARIMA if successful
        if arima_success:
            fig_comp.add_trace(go.Scatter(
                x=future_dates, y=mean_forecast, 
                mode='lines+markers', name='ARIMA 6m Forecast',
                line=dict(color='#00E676', dash='dash')
            ))
            fig_comp.add_trace(go.Scatter(
                x=future_dates + future_dates[::-1],
                y=list(conf_int.iloc[:, 1]) + list(conf_int.iloc[:, 0])[::-1],
                fill='toself', fillcolor='rgba(0, 230, 118, 0.2)',
                line=dict(color='rgba(255,255,255,0)'),
                hoverinfo="skip", showlegend=True, name='ARIMA 95% CI'
            ))
            
        # Plot RF Next Month single point
        next_month_date = last_date + pd.DateOffset(months=1)
        fig_comp.add_trace(go.Scatter(
            x=[next_month_date], y=[rf_predicted_footfall], 
            mode='markers', name='RF Next Month Prediction',
            marker=dict(color='#E91E63', size=12, symbol='star')
        ))
        
        fig_comp.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#FAFAFA'),
            xaxis_title="Date", yaxis_title="Pilgrim Count",
            hovermode="x unified"
        )
        st.plotly_chart(fig_comp, width='stretch')
        
        st.markdown("---")
        
        # --- 4. Render Alert System based on Selection ---
        st.markdown(f"#### 🚨 Ecosystem Stress Alert System ({model_choice} Projection)")
        
        # Assign final output based on toggle 
        predicted_footfall = rf_predicted_footfall if "RandomForest" in model_choice else arima_predicted_footfall
        
        res_col1, res_col2 = st.columns([1, 2])
        
        with res_col1:
            st.metric("Predicted Pilgrim Footfall", f"{predicted_footfall:,.0f}")
            
        # Alert System Logic
        current_capacity = df_filtered['Carrying_Capacity'].iloc[-1]
        stress_ratio = predicted_footfall / current_capacity if current_capacity > 0 else 0
        
        with res_col2:
            if stress_ratio < 0.75:
                st.success(f"**Status: GREEN (Low Stress)** ✅\\n\\nPredicted footfall is safely within the designated carrying capacity. Ecosystem impact is managed. (Capacity Utilization: {stress_ratio*100:.1f}%)")
                st.info("💡 **AI Recommendation**: Normal operations. Maintain standard monitoring protocols.")
            elif stress_ratio <= 1.0:
                st.warning(f"**Status: YELLOW (Medium Stress)** ⚠️\\n\\nFootfall is approaching the maximum carrying capacity. Preventative regulatory measures recommended. (Capacity Utilization: {stress_ratio*100:.1f}%)")
                st.warning("💡 **AI Recommendation**: Suggest controlled entry. Deploy additional ground personnel and stagger visitor batches.")
            else:
                st.error(f"**Status: RED (Critical Danger)** 🚨\\n\\n**ALERT**: Predicted footfall EXCEEDS environmental carrying capacity! Imminent ecosystem stress risk. Immediate intervention required. (Capacity Utilization: {stress_ratio*100:.1f}%)")
                st.error("💡 **AI Recommendation**: Limit permits immediately. Activate emergency diversion protocols and halt incoming traffic.")

        # --- SHAP Explainability for RF ---
        if model_choice == "RandomForest (Climate-based)":
            st.markdown("---")
            st.markdown("#### 🧠 AI Explainability (SHAP Feature Contribution)")
            
            try:
                import shap
                # Compute SHAP for the specific configured scenario
                explainer = shap.TreeExplainer(model)
                shap_values = explainer.shap_values(rf_input_data)
                
                if isinstance(shap_values, list): # handle multi-output or different shap versions
                    shap_values = shap_values[0]
                    
                # Visualize using Plotly (Fast and Native to Streamlit)
                shap_df = pd.DataFrame({
                    'Feature': ['Month', 'Temperature', 'Rainfall'],
                    'SHAP Value': shap_values[0] if len(shap_values.shape) > 1 else shap_values
                })
                
                shap_df['Abs Value'] = shap_df['SHAP Value'].abs()
                shap_df = shap_df.sort_values(by='Abs Value', ascending=True)
                
                fig_shap = px.bar(
                    shap_df, 
                    x='SHAP Value', 
                    y='Feature', 
                    orientation='h',
                    title="How Features Influenced This Prediction",
                    color='SHAP Value',
                    color_continuous_scale="RdBu",
                    color_continuous_midpoint=0
                )
                
                base_value = explainer.expected_value
                if isinstance(base_value, np.ndarray) or isinstance(base_value, list):
                    base_value = base_value[0]
                
                fig_shap.add_annotation(
                    x=0, y=-0.5,
                    text=f"Base expectation: {base_value:,.0f} | Final Prediction: {rf_predicted_footfall:,.0f}",
                    showarrow=False,
                    font=dict(color="#B0BEC5")
                )
                
                fig_shap.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#FAFAFA'))
                st.plotly_chart(fig_shap, width='stretch')
            except Exception as e:
                st.warning(f"SHAP local explainability could not be rendered: {e}")

with tab4:
    st.markdown("### 🗺️ Char Dham Geospatial Monitoring")
    st.markdown("Live interactive map depicting current pilgrim load versus ecosystem carrying capacity across all integrated shrines.")
    
    # Prepare Map Data (Using latest data for all available shrines)
    latest_data = []
    for shrine in available_shrines:
        shrine_df = df[df['Shrine'] == shrine]
        if shrine_df.empty: continue
        
        latest_row = shrine_df.iloc[-1]
        pilgrims = latest_row['Pilgrim_Count']
        capacity = latest_row['Carrying_Capacity']
        ratio = pilgrims / capacity if capacity > 0 else 0
        
        if ratio < 0.75:
            status = 'Safe'
            color = '#00E676'
        elif ratio <= 1.0:
            status = 'Approaching Limit'
            color = '#FFD600'
        else:
            status = 'Exceeding Capacity'
            color = '#FF1744'
            
        latest_data.append({
            'Shrine': shrine,
            'Latitude': latest_row['Latitude'],
            'Longitude': latest_row['Longitude'],
            'Pilgrim Count': int(pilgrims),
            'Carrying Capacity': int(capacity),
            'Status': status,
            'Color': color,
            'Marker Size': 15 
        })
        
    if latest_data:
        df_map = pd.DataFrame(latest_data)
        
        fig_map = px.scatter_mapbox(
            df_map, 
            lat="Latitude", 
            lon="Longitude", 
            hover_name="Shrine", 
            hover_data={"Latitude": False, "Longitude": False, "Pilgrim Count": True, "Carrying Capacity": True, "Status": True, "Marker Size": False, "Color": False},
            color="Status",
            color_discrete_map={
                "Safe": "#00E676", 
                "Approaching Limit": "#FFD600", 
                "Exceeding Capacity": "#FF1744"
            },
            size="Marker Size",
            zoom=6, 
            height=600,
        )
        
        fig_map.update_layout(
            mapbox_style="carto-darkmatter", 
            margin={"r":0,"t":0,"l":0,"b":0}, 
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#FAFAFA')
        )
        
        st.plotly_chart(fig_map, width='stretch')
    else:
        st.info("No geospatial data available to populate the map.")
