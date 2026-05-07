"""
models.py - Machine Learning Models
======================================
Implements three forecasting models with expanded feature sets:
  1. RandomForest (19 climate+tourism+engineered features)
  2. SARIMA (seasonal time series)
  3. LSTM (deep learning sequence prediction)
"""

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score,
    mean_absolute_percentage_error,
)
from sklearn.preprocessing import MinMaxScaler
import statsmodels.api as sm
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Full feature set available from both datasets + engineered
RF_FEATURES_FULL = [
    "Month", "Avg_Temperature_C", "Max_Temperature_C", "Min_Temperature_C",
    "Rainfall_mm", "Relative_Humidity_%", "Wind_Speed_mps",
    "Solar_Radiation", "Snowfall_mm",
    "Peak_Season", "Accessibility_Index",
    "Carrying_Capacity", "Estimated_Waste_Tons",
    "Month_Sin", "Month_Cos", "Temp_Anomaly", "Rain_Anomaly",
    "YoY_Growth", "Capacity_Utilization",
]


def evaluate_model(y_true, y_pred) -> dict:
    """Compute RMSE, MAE, R-squared, MAPE."""
    y_true = np.array(y_true).flatten()
    y_pred = np.array(y_pred).flatten()
    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_true, y_pred = y_true[mask], y_pred[mask]

    if len(y_true) == 0:
        return {"rmse": np.nan, "mae": np.nan, "r2": np.nan, "mape": np.nan}

    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
        "mape": float(mean_absolute_percentage_error(y_true, y_pred) * 100),
    }


def get_available_features(df: pd.DataFrame) -> list:
    """Return the subset of RF_FEATURES_FULL that exist in the dataframe."""
    return [f for f in RF_FEATURES_FULL if f in df.columns]


# ============================================================================
#  1. Random Forest Regressor (expanded features)
# ============================================================================
@st.cache_resource(show_spinner="Training Random Forest model...")
def train_random_forest(
    _X: pd.DataFrame,
    _y: pd.Series,
    n_estimators: int = 300,
    max_depth: int = 15,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Train RF with expanded feature set."""
    # Drop NaN rows
    valid_mask = _X.notna().all(axis=1) & _y.notna()
    X_clean = _X[valid_mask].copy()
    y_clean = _y[valid_mask].copy()

    X_train, X_test, y_train, y_test = train_test_split(
        X_clean, y_clean, test_size=test_size, random_state=random_state
    )

    model = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_split=5,
        min_samples_leaf=2,
        max_features="sqrt",
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    cv_scores = cross_val_score(model, X_clean, y_clean, cv=5, scoring="r2")
    importances = dict(zip(X_clean.columns, model.feature_importances_))

    return {
        "model": model,
        "metrics": evaluate_model(y_test, y_pred),
        "cv_r2_mean": float(cv_scores.mean()),
        "cv_r2_std": float(cv_scores.std()),
        "feature_importance": importances,
        "y_test": y_test.values,
        "y_pred": y_pred,
        "X_test": X_test,
        "features_used": list(X_clean.columns),
        "n_features": len(X_clean.columns),
    }


def rf_predict(model, input_data: pd.DataFrame) -> float:
    """Make a single prediction."""
    return float(model.predict(input_data)[0])


# ============================================================================
#  2. SARIMA Time Series Model (replaces basic ARIMA)
# ============================================================================
@st.cache_resource(show_spinner="Training SARIMA model...")
def train_sarima(
    _series: pd.Series,
    seasonal_period: int = 12,
    forecast_steps: int = 12,
) -> dict:
    """
    Fit SARIMA with two-phase optimized grid search.

    Phase 1 (Coarse): p,q ∈ {0,1}, d ∈ {0,1}, P,Q ∈ {0,1}, D ∈ {0,1}, s=12
             → 2×2×2 × 2×2×2 = 64 fits
    Phase 2 (Refine): Expand p,q to {0,1,2} around the best seasonal order
             → up to 9 fits

    Total: ~73 fits — good accuracy-speed balance.
    """
    ts = _series.dropna()
    if len(ts) < 24:
        return {"success": False, "error": "Insufficient data (need >= 24 observations)"}

    try:
        best_aic = np.inf
        best_order = (1, 1, 1)
        best_seasonal = (0, 1, 0, seasonal_period)

        # Phase 1: Coarse search
        for p in [0, 1]:
            for d in [0, 1]:
                for q in [0, 1]:
                    for P in [0, 1]:
                        for D in [0, 1]:
                            for Q in [0, 1]:
                                try:
                                    model = sm.tsa.statespace.SARIMAX(
                                        ts,
                                        order=(p, d, q),
                                        seasonal_order=(P, D, Q, seasonal_period),
                                        enforce_stationarity=False,
                                        enforce_invertibility=False,
                                    )
                                    result = model.fit(disp=False, maxiter=100)
                                    if result.aic < best_aic:
                                        best_aic = result.aic
                                        best_order = (p, d, q)
                                        best_seasonal = (P, D, Q, seasonal_period)
                                except Exception:
                                    continue

        # Phase 2: Refine non-seasonal p,q around best seasonal order
        P_best, D_best, Q_best = best_seasonal[0], best_seasonal[1], best_seasonal[2]
        for p in [0, 1, 2]:
            for q in [0, 1, 2]:
                if (p, best_order[1], q) == best_order:
                    continue  # Already tested
                try:
                    model = sm.tsa.statespace.SARIMAX(
                        ts,
                        order=(p, best_order[1], q),
                        seasonal_order=(P_best, D_best, Q_best, seasonal_period),
                        enforce_stationarity=False,
                        enforce_invertibility=False,
                    )
                    result = model.fit(disp=False, maxiter=100)
                    if result.aic < best_aic:
                        best_aic = result.aic
                        best_order = (p, best_order[1], q)
                except Exception:
                    continue

        # Final fit with best parameters
        final_model = sm.tsa.statespace.SARIMAX(
            ts,
            order=best_order,
            seasonal_order=(P_best, D_best, Q_best, seasonal_period),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        result = final_model.fit(disp=False, maxiter=200)

        # Forecast
        forecast = result.get_forecast(steps=forecast_steps)
        mean_forecast = forecast.predicted_mean
        conf_int = forecast.conf_int(alpha=0.05)

        last_date = ts.index[-1]
        future_dates = pd.date_range(
            start=last_date + pd.DateOffset(months=1),
            periods=forecast_steps,
            freq="MS",
        )

        # In-sample fitted values and residuals for diagnostics
        fitted = result.fittedvalues
        residuals = result.resid

        # In-sample metrics (skip initial NaN burn-in)
        valid_start = max(best_order[1] + best_seasonal[1] * seasonal_period, 1)
        in_sample_actual = ts.values[valid_start:]
        in_sample_fitted = fitted.values[valid_start:]
        in_sample_metrics = evaluate_model(in_sample_actual, in_sample_fitted)

        # Ljung-Box test for residual autocorrelation
        try:
            lb_result = sm.stats.acorr_ljungbox(residuals.dropna(), lags=[10], return_df=True)
            lb_pvalue = float(lb_result["lb_pvalue"].iloc[0])
        except Exception:
            lb_pvalue = None

        seasonal_order_str = f"({P_best},{D_best},{Q_best},{seasonal_period})"

        return {
            "success": True,
            "model": result,
            "order": best_order,
            "seasonal_order": (P_best, D_best, Q_best, seasonal_period),
            "seasonal_order_str": seasonal_order_str,
            "forecast_mean": np.maximum(mean_forecast.values, 0),
            "forecast_ci_lower": np.maximum(conf_int.iloc[:, 0].values, 0),
            "forecast_ci_upper": conf_int.iloc[:, 1].values,
            "future_dates": future_dates,
            "metrics": in_sample_metrics,
            "aic": float(result.aic),
            "bic": float(result.bic),
            "fitted_values": fitted,
            "residuals": residuals,
            "y_actual": ts,
            "lb_pvalue": lb_pvalue,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
#  3. LSTM Model
# ============================================================================
@st.cache_resource(show_spinner="Training LSTM neural network...")
def train_lstm(
    _series: pd.Series,
    lookback: int = 12,
    epochs: int = 100,
    batch_size: int = 16,
    forecast_steps: int = 12,
) -> dict:
    """Train LSTM for time series forecasting."""
    try:
        import tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout
        from tensorflow.keras.callbacks import EarlyStopping
        tf.get_logger().setLevel("ERROR")
    except ImportError:
        return {"success": False, "error": "TensorFlow not installed. Run: pip install tensorflow"}

    ts = _series.dropna().values.reshape(-1, 1).astype("float32")

    if len(ts) < lookback + 10:
        return {"success": False, "error": f"Insufficient data (need >= {lookback + 10})"}

    try:
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled = scaler.fit_transform(ts)

        X, y = [], []
        for i in range(lookback, len(scaled)):
            X.append(scaled[i - lookback:i, 0])
            y.append(scaled[i, 0])
        X, y = np.array(X), np.array(y)
        X = X.reshape(X.shape[0], X.shape[1], 1)

        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=(lookback, 1)),
            Dropout(0.2),
            LSTM(32, return_sequences=False),
            Dropout(0.2),
            Dense(16, activation="relu"),
            Dense(1),
        ])

        model.compile(optimizer="adam", loss="mse", metrics=["mae"])
        early_stop = EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True)

        model.fit(
            X_train, y_train,
            validation_split=0.2,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=[early_stop],
            verbose=0,
        )

        y_pred_scaled = model.predict(X_test, verbose=0).flatten()
        y_test_inv = scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()
        y_pred_inv = scaler.inverse_transform(y_pred_scaled.reshape(-1, 1)).flatten()
        metrics = evaluate_model(y_test_inv, y_pred_inv)

        last_sequence = scaled[-lookback:].reshape(1, lookback, 1)
        predictions = []
        current_seq = last_sequence.copy()

        for _ in range(forecast_steps):
            pred = model.predict(current_seq, verbose=0)[0, 0]
            predictions.append(pred)
            current_seq = np.roll(current_seq, -1, axis=1)
            current_seq[0, -1, 0] = pred

        forecast_values = scaler.inverse_transform(
            np.array(predictions).reshape(-1, 1)
        ).flatten()

        ci_width = np.abs(forecast_values) * np.linspace(0.05, 0.20, forecast_steps)
        ci_lower = forecast_values - ci_width
        ci_upper = forecast_values + ci_width

        last_date = _series.dropna().index[-1]
        future_dates = pd.date_range(
            start=last_date + pd.DateOffset(months=1),
            periods=forecast_steps,
            freq="MS",
        )

        return {
            "success": True,
            "forecast_mean": forecast_values,
            "forecast_ci_lower": ci_lower,
            "forecast_ci_upper": ci_upper,
            "future_dates": future_dates,
            "metrics": metrics,
            "y_test": y_test_inv,
            "y_pred": y_pred_inv,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
#  SHAP Explainability
# ============================================================================
def compute_shap_values(model, X_input: pd.DataFrame, feature_names: list) -> dict:
    """Compute SHAP values for a Random Forest prediction."""
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_input)

        if isinstance(shap_values, list):
            shap_values = shap_values[0]

        shap_array = shap_values[0] if len(shap_values.shape) > 1 else shap_values

        base_value = explainer.expected_value
        if isinstance(base_value, (np.ndarray, list)):
            base_value = float(base_value[0])

        return {
            "success": True,
            "shap_values": shap_array,
            "base_value": float(base_value),
            "feature_names": feature_names,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
