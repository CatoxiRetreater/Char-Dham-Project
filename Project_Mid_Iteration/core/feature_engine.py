"""
feature_engine.py - Feature Engineering & Derived Metrics
==========================================================
Computes Ecosystem Stress Index (ESI) per SRS spec,
Tourism Pressure Index, NDVI features, correlation matrices,
and seasonal decomposition.
"""

import numpy as np
import pandas as pd
from typing import Optional


# ---------------------------------------------------------------------------
#  Ecosystem Stress Index (ESI) — per SRS Section 2.1.3
#  Weights: capacity=0.5, temperature=0.3, rainfall=0.2
# ---------------------------------------------------------------------------
def compute_esi(df: pd.DataFrame) -> pd.Series:
    """
    Compute Ecosystem Stress Index (0-100).
    Formula per SRS:
      ESI = 0.5 * capacity_ratio + 0.3 * temp_deviation + 0.2 * rain_deviation
    All sub-indices are min-max normalised before aggregation.
    """
    # Capacity component
    cap_ratio = df["Pilgrim_Count"] / df["Carrying_Capacity"].clip(lower=1)
    cap_norm = np.clip(cap_ratio / 1.5, 0, 1)

    # Temperature anomaly component
    if "Temp_Anomaly" in df.columns:
        temp_dev = df["Temp_Anomaly"].abs()
    else:
        if len(df) > 1 and "Shrine" in df.columns:
            mean_temp = df.groupby("Shrine")["Avg_Temperature_C"].transform("mean")
        else:
            mean_temp = df["Avg_Temperature_C"]
        temp_dev = (df["Avg_Temperature_C"] - mean_temp).abs()

    if len(df) > 1 and "Shrine" in df.columns:
        temp_std = df.groupby("Shrine")["Avg_Temperature_C"].transform("std").fillna(5.0).clip(lower=0.1)
    else:
        temp_std = pd.Series(5.0, index=df.index)  # Default stddev for single row
    temp_norm = np.clip(temp_dev / (temp_std * 3), 0, 1)

    # Rainfall deviation component
    if "Rain_Anomaly" in df.columns:
        rain_dev = df["Rain_Anomaly"].abs()
    else:
        if len(df) > 1 and "Shrine" in df.columns:
            mean_rain = df.groupby("Shrine")["Rainfall_mm"].transform("mean")
        else:
            mean_rain = df["Rainfall_mm"]
        rain_dev = (df["Rainfall_mm"] - mean_rain).abs()

    if len(df) > 1 and "Shrine" in df.columns:
        rain_std = df.groupby("Shrine")["Rainfall_mm"].transform("std").fillna(50.0).clip(lower=0.1)
    else:
        rain_std = pd.Series(50.0, index=df.index)  # Default stddev for single row
    rain_norm = np.clip(rain_dev / (rain_std * 3), 0, 1)

    # Weighted combination per SRS
    esi = (cap_norm * 0.5 + temp_norm * 0.3 + rain_norm * 0.2) * 100

    return np.clip(esi, 0, 100)


def get_esi_status(esi_value: float) -> tuple:
    """
    Return (status_label, color_hex, description) for an ESI value.
    Per SRS: <40 = Green, 40-70 = Yellow, >=70 = Red
    """
    if esi_value < 40:
        return "LOW", "#22c55e", "Ecosystem stress is within safe limits."
    elif esi_value < 70:
        return "MODERATE", "#f59e0b", "Ecosystem showing moderate pressure. Monitor closely."
    else:
        return "CRITICAL", "#ef4444", "Critical ecosystem stress. Immediate intervention required."


# ---------------------------------------------------------------------------
#  Tourism Pressure Index (TPI)
# ---------------------------------------------------------------------------
def compute_tourism_pressure_index(df: pd.DataFrame) -> pd.Series:
    """
    Composite index combining pilgrim density with environmental factors.
    """
    overcrowd = np.clip(df["Pilgrim_Count"] / df["Carrying_Capacity"].clip(lower=1), 0, 3) / 3

    if "Estimated_Waste_Tons" in df.columns:
        q95 = df["Estimated_Waste_Tons"].quantile(0.95)
        q95 = max(q95, 0.01)
        waste_norm = np.clip(df["Estimated_Waste_Tons"] / q95, 0, 1)
    else:
        waste_norm = overcrowd * 0.5

    if "Accessibility_Index" in df.columns:
        access_strain = 1 - df["Accessibility_Index"].clip(0, 1)
    else:
        access_strain = np.full(len(df), 0.3)

    tpi = (overcrowd * 0.50 + waste_norm * 0.30 + access_strain * 0.20) * 100
    return np.clip(tpi, 0, 100)


# ---------------------------------------------------------------------------
#  NDVI Features
# ---------------------------------------------------------------------------
def compute_ndvi_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add NDVI-related features. Computes from climate data if not present."""
    result = df.copy()

    if "NDVI" not in result.columns:
        month_factor = np.sin(np.pi * (result["Month"] - 3) / 6).clip(0, 1) * 0.3
        alt_factor = 1 - (result["Altitude_m"] - 3000) / 1000 * 0.15
        base = 0.35
        np.random.seed(42)
        noise = np.random.normal(0, 0.04, len(result))
        result["NDVI"] = np.clip(base + month_factor * alt_factor + noise, 0.1, 0.85)

    result["NDVI_Change"] = result.groupby("Shrine")["NDVI"].diff().fillna(0)

    result["Veg_Health"] = pd.cut(
        result["NDVI"],
        bins=[0, 0.2, 0.35, 0.5, 0.65, 1.0],
        labels=["Barren", "Sparse", "Moderate", "Healthy", "Dense"],
    )

    if "Forest_Cover_Loss_Ha" not in result.columns:
        pressure = result["Pilgrim_Count"] / result["Carrying_Capacity"]
        np.random.seed(42)
        result["Forest_Cover_Loss_Ha"] = np.clip(
            pressure * np.random.uniform(0.5, 2.0, len(result)), 0, 8
        )

    return result


# ---------------------------------------------------------------------------
#  Correlation Analysis
# ---------------------------------------------------------------------------
def compute_correlation_matrix(
    df: pd.DataFrame,
    columns: Optional[list] = None,
) -> pd.DataFrame:
    """Compute correlation matrix for selected numeric columns."""
    if columns is None:
        columns = [
            "Pilgrim_Count", "Avg_Temperature_C", "Rainfall_mm",
            "Relative_Humidity_%", "Wind_Speed_mps", "Estimated_Waste_Tons",
            "Capacity_Utilization",
        ]
    available = [c for c in columns if c in df.columns]
    return df[available].corr()


# ---------------------------------------------------------------------------
#  Seasonal Decomposition
# ---------------------------------------------------------------------------
def compute_seasonal_decomposition(
    series: pd.Series,
    period: int = 12,
) -> dict:
    """Decompose time series into trend, seasonal, and residual."""
    try:
        from statsmodels.tsa.seasonal import STL
        stl = STL(series.dropna(), period=period, robust=True)
        result = stl.fit()
        return {
            "trend": result.trend,
            "seasonal": result.seasonal,
            "residual": result.resid,
            "observed": series,
        }
    except Exception:
        trend = series.rolling(window=period, center=True, min_periods=1).mean()
        detrended = series - trend
        seasonal = detrended.groupby(detrended.index.month if hasattr(detrended.index, 'month')
                                      else np.arange(len(detrended)) % period).transform("mean")
        residual = series - trend - seasonal
        return {
            "trend": trend,
            "seasonal": seasonal,
            "residual": residual,
            "observed": series,
        }


# ---------------------------------------------------------------------------
#  Classify stress level
# ---------------------------------------------------------------------------
def classify_stress(value: float, thresholds: tuple = (40, 70)) -> str:
    """Classify a 0-100 stress score. Per SRS: <40=LOW, 40-70=MODERATE, >=70=CRITICAL."""
    if value < thresholds[0]:
        return "LOW"
    elif value < thresholds[1]:
        return "MODERATE"
    else:
        return "CRITICAL"
