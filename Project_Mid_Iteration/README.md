# 🏔️ Char Dham Ecosystem Intelligence Dashboard

> AI-powered real-time monitoring of tourism pressure, climate impact, and ecosystem health across Kedarnath, Badrinath, Gangotri & Yamunotri.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat&logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red?style=flat&logo=streamlit)
![TensorFlow](https://img.shields.io/badge/TensorFlow-2.15+-orange?style=flat&logo=tensorflow)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Setup & Installation](#-setup--installation)
- [API Integration](#-api-integration)
- [Models & Logic](#-models--logic)
- [Deployment](#-deployment)

---

## ✨ Features

### 🏠 Home — Overview Dashboard
- Real-time KPI cards (total pilgrims, ESI average, active alerts)
- Per-shrine status cards with live weather, NDVI, and capacity utilization
- Interactive sparkline trends for all 4 shrines
- Aggregated ESI comparison chart

### 📊 Real-Time Monitoring (Page 1)
- **Live Weather**: OpenWeatherMap API integration for real-time temperature, humidity, wind, rainfall
- **5-Day Forecast**: 3-hourly weather projections with temperature & rain overlays
- **ESI Gauge**: Real-time Ecosystem Stress Index indicator
- **Pilgrim Activity Tracker**: Simulated daily visitor estimation
- **Historical Analysis**: Footfall trends, climate scatter plots, seasonality heatmaps, correlation matrix

### 🔮 Predictions (Page 2)
- **Random Forest**: Climate-feature-based regression with cross-validation
- **ARIMA**: Auto-order selection time series forecasting (AIC-optimized)
- **LSTM**: Deep learning sequence prediction (2-layer architecture)
- **Model Comparison**: Side-by-side RMSE, MAE, R², MAPE metrics
- **SHAP Explainability**: Feature contribution analysis for RF predictions
- **Seasonal Decomposition**: STL trend/seasonal/residual breakdown

### 🗺️ Geospatial Maps (Page 3)
- **Shrine Overview Map**: Interactive Folium map with all 4 shrines, color-coded by status
- **NDVI Heatmap**: Vegetation health visualization with MODIS/synthetic data
- **Land Cover Classification**: LULC distribution with pie charts and map overlays
- **NDVI Time Series**: 15-year vegetation trend analysis
- **GEE Integration**: Seamless fallback from Google Earth Engine to synthetic data

### 🚨 Alerts (Page 4)
- **Multi-Factor Risk Engine**: Tourist overload, climate stress, NDVI degradation, ESI
- **Color-Coded Alert Cards**: Per-shrine risk assessment (LOW → CRITICAL)
- **Adjustable Thresholds**: User-configurable alert parameters
- **AI Recommendations**: Context-specific action items per alert level
- **Historical Alert Patterns**: Annual stress level distribution analysis
- **Downloadable Reports**: PDF and CSV export

### 🧪 What-If Simulator (Page 5)
- **Scenario Sliders**: Adjust pilgrims, temperature, rainfall, NDVI, humidity, capacity
- **Side-by-Side Comparison**: Current vs simulated ESI with delta indicator
- **Simulated Alerts**: Real-time alert trigger preview
- **Sensitivity Analysis**: ESI response curves for each parameter
- **RF Prediction**: AI prediction under the configured scenario

---

## 🏗 Architecture

```
Project_Mid_Iteration/
├── 🏠_Home.py                        # Main entry point
├── pages/
│   ├── 1_📊_Real_Time_Monitoring.py   # Live monitoring
│   ├── 2_🔮_Predictions.py            # ML forecasting
│   ├── 3_🗺️_Geospatial_Maps.py       # Maps & NDVI
│   ├── 4_🚨_Alerts.py                 # Risk alerts
│   └── 5_🧪_What_If_Simulator.py      # Scenario planning
├── core/
│   ├── __init__.py
│   ├── data_loader.py                 # Data pipeline
│   ├── weather_api.py                 # OpenWeatherMap client
│   ├── feature_engine.py              # ESI, TPI, NDVI features
│   ├── models.py                      # RF, ARIMA, LSTM
│   ├── alerts.py                      # Multi-factor alert engine
│   ├── geospatial.py                  # GEE + Folium maps
│   └── report_generator.py            # PDF/CSV reports
├── assets/
│   └── style.css                      # Premium UI stylesheet
├── data/
│   ├── Climate Dataset.xlsx
│   ├── Tourist Footfall Dataset.xlsx
│   └── cache/                         # API response cache
├── .env                               # API keys
├── .streamlit/config.toml             # Theme config
├── requirements.txt
└── README.md
```

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.10 or higher
- pip package manager

### Step 1: Clone / Navigate to Project
```bash
cd "d:\UPES\SEM VI\Minor\Project_Mid_Iteration"
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment
Create/edit `.env` file:
```env
OPENWEATHER_API_KEY=your_openweather_api_key_here
GEE_PROJECT=your-gee-project-id
```

### Step 4: Run Dashboard
```bash
streamlit run 🏠_Home.py
```

The dashboard will open at `http://localhost:8501`

### Optional: Google Earth Engine Setup
```bash
pip install earthengine-api
earthengine authenticate
```
The geospatial module will automatically detect GEE and switch from synthetic to real NDVI/LULC data.

---

## 🔑 API Integration

### OpenWeatherMap
- **Endpoint**: `https://api.openweathermap.org/data/2.5/weather` (current) and `/forecast` (5-day)
- **Auth**: API key via `.env` → `OPENWEATHER_API_KEY`
- **Rate Limit**: 60 calls/min (free tier). Caching (30-min TTL) avoids hitting limits.
- **Fallback**: Historical baseline data (seasonal averages) when API is unreachable.
- **Data Used**: Temperature, humidity, wind speed, cloud cover, rainfall, pressure

### Google Earth Engine (Optional)
- **Product**: MODIS/006/MOD13Q1 (16-day NDVI)
- **Auth**: Service account or interactive `earthengine authenticate`
- **Fallback**: Realistic synthetic NDVI with seasonal patterns and altitude effects

---

## 🧠 Models & Logic

### 1. Random Forest Regressor
- **Features**: Month, Avg_Temperature_C, Rainfall_mm, Month_Sin, Month_Cos
- **Hyperparameters**: 200 trees, max_depth=12, min_samples_split=5
- **Validation**: 80/20 split + 5-fold cross-validation
- **Explainability**: SHAP TreeExplainer for feature contributions

### 2. ARIMA (AutoRegressive Integrated Moving Average)
- **Auto-Order Selection**: Iterates over p∈{0,1,2}, d∈{0,1}, q∈{0,1,2} — selects by lowest AIC
- **Forecast**: 12-month ahead with 95% confidence intervals
- **Input**: Monthly Pilgrim_Count time series (DatetimeIndex)

### 3. LSTM (Long Short-Term Memory)
- **Architecture**: LSTM(64) → Dropout(0.2) → LSTM(32) → Dropout(0.2) → Dense(16, ReLU) → Dense(1)
- **Lookback Window**: 12 months
- **Training**: Early stopping (patience=10), Adam optimizer, MSE loss
- **Scaling**: MinMaxScaler (0,1)
- **CI Estimation**: Progressive ±5-20% widening

### 4. Ecosystem Stress Index (ESI)
```
ESI = (Capacity_Ratio × 0.45 + Temp_Anomaly × 0.15 + Rain_Deviation × 0.15
     + Humidity_Stress × 0.10 + Waste_Pressure × 0.15) × 100
```
Range: 0–100 | Levels: LOW (<30), MODERATE (30-55), HIGH (55-75), CRITICAL (>75)

### 5. Alert Engine
Multi-factor risk scoring combining:
- Tourist overload (capacity utilization)
- Climate stress (temperature + rainfall anomalies + humidity extremes)
- NDVI degradation (vegetation loss detection)
- ESI composite (overall ecosystem health)

---

## 🚀 Deployment

### Local
```bash
streamlit run 🏠_Home.py
```

### Streamlit Cloud
1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect repo → Set main file to `🏠_Home.py`
4. Add secrets: `OPENWEATHER_API_KEY = "your_key"`
5. Deploy

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8501
CMD ["streamlit", "run", "🏠_Home.py", "--server.port=8501"]
```

---

## 📄 License

This project is developed for academic purposes at UPES — School of Computer Science.

---

*Built with ❤️ using Streamlit, TensorFlow, Plotly, Folium, and scikit-learn*
