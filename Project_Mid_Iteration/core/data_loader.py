"""
data_loader.py — Data Loading, Cleaning & Preprocessing Pipeline
=================================================================
Handles ingestion of Excel datasets, merging, feature creation,
and caching for the Char Dham Intelligence Dashboard.
"""

import os
import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

CLIMATE_FILE = DATA_DIR / "Climate Dataset.xlsx"
FOOTFALL_FILE = DATA_DIR / "Tourist Footfall Dataset.xlsx"

MERGE_KEYS = ["Year", "Month", "Shrine", "District"]

SHRINE_COORDS = {
    "Kedarnath":  {"lat": 30.7352, "lon": 79.0669, "alt": 3583, "district": "Rudraprayag"},
    "Badrinath":  {"lat": 30.7440, "lon": 79.4930, "alt": 3133, "district": "Chamoli"},
    "Gangotri":   {"lat": 30.9947, "lon": 78.9398, "alt": 3100, "district": "Uttarkashi"},
    "Yamunotri":  {"lat": 31.0140, "lon": 78.4600, "alt": 3293, "district": "Uttarkashi"},
}

ALL_SHRINES = list(SHRINE_COORDS.keys())


# ---------------------------------------------------------------------------
#  Primary loader (cached)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner="Loading datasets…")
def load_and_merge_data() -> pd.DataFrame:
    """
    Load both Excel files, merge on common keys, clean, and return a
    single unified DataFrame with all climate + tourism features.
    """
    # --- Load raw ---
    df_climate = pd.read_excel(CLIMATE_FILE)
    df_footfall = pd.read_excel(FOOTFALL_FILE)

    # --- Merge ---
    df = pd.merge(
        df_footfall, df_climate,
        on=MERGE_KEYS, how="inner",
        suffixes=("_tourist", "_climate"),
    )

    # Resolve duplicate columns — prefer climate dataset for climate cols
    dup_cols_to_drop = [c for c in df.columns if c.endswith("_tourist")]
    # But keep unique tourist columns (e.g., Pilgrim_Count, etc.)
    tourist_only = []
    for c in dup_cols_to_drop:
        base = c.replace("_tourist", "")
        if f"{base}_climate" in df.columns:
            df.rename(columns={f"{base}_climate": base}, inplace=True)
        else:
            tourist_only.append(c)
    df.drop(columns=[c for c in dup_cols_to_drop if c not in tourist_only], inplace=True)
    for c in tourist_only:
        df.rename(columns={c: c.replace("_tourist", "")}, inplace=True)

    # --- Clean ---
    df = _clean(df)

    # --- Feature enrichment ---
    df = _enrich(df)

    return df


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Handle missing values, type conversions, and basic validation."""
    # Fill Festival_Event NaN with "None"
    df["Festival_Event"] = df["Festival_Event"].fillna("None")

    # Ensure correct types
    df["Year"] = df["Year"].astype(int)
    df["Month"] = df["Month"].astype(int)
    df["Pilgrim_Count"] = df["Pilgrim_Count"].astype(int)
    df["Carrying_Capacity"] = df["Carrying_Capacity"].astype(int)
    df["Peak_Season"] = df["Peak_Season"].astype(int)

    # Cap extreme values (outlier clipping at 1st/99th percentile)
    for col in ["Pilgrim_Count", "Rainfall_mm", "Avg_Temperature_C"]:
        if col in df.columns:
            low = df[col].quantile(0.01)
            high = df[col].quantile(0.99)
            df[col] = df[col].clip(low, high)

    # Drop exact duplicates
    df.drop_duplicates(inplace=True)

    return df


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Create derived features and computed columns."""
    # Date column
    df["Date"] = pd.to_datetime(
        df["Year"].astype(str) + "-" + df["Month"].astype(str) + "-01"
    )
    df.sort_values("Date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Cyclical month encoding (helps ML models)
    df["Month_Sin"] = np.sin(2 * np.pi * df["Month"] / 12)
    df["Month_Cos"] = np.cos(2 * np.pi * df["Month"] / 12)

    # Capacity utilization ratio
    df["Capacity_Utilization"] = df["Pilgrim_Count"] / df["Carrying_Capacity"]

    # Temperature anomaly (deviation from shrine-month mean)
    monthly_mean = df.groupby(["Shrine", "Month"])["Avg_Temperature_C"].transform("mean")
    df["Temp_Anomaly"] = df["Avg_Temperature_C"] - monthly_mean

    # Rainfall anomaly
    monthly_rain = df.groupby(["Shrine", "Month"])["Rainfall_mm"].transform("mean")
    df["Rain_Anomaly"] = df["Rainfall_mm"] - monthly_rain

    # Waste per pilgrim (derived)
    if "Estimated_Waste_Tons" in df.columns:
        df["Waste_Per_Pilgrim_Kg"] = (df["Estimated_Waste_Tons"] * 1000) / df["Pilgrim_Count"].clip(lower=1)
    else:
        df["Estimated_Waste_Tons"] = df["Pilgrim_Count"] * 0.005
        df["Waste_Per_Pilgrim_Kg"] = 5.0

    # Year-over-year growth %
    df["YoY_Growth"] = df.groupby(["Shrine", "Month"])["Pilgrim_Count"].pct_change(fill_method=None) * 100
    df["YoY_Growth"] = df["YoY_Growth"].fillna(0)

    return df


# ---------------------------------------------------------------------------
#  Convenience accessors
# ---------------------------------------------------------------------------
def get_shrine_data(df: pd.DataFrame, shrine: str) -> pd.DataFrame:
    """Filter dataframe for a specific shrine."""
    return df[df["Shrine"] == shrine].copy()


def get_latest_record(df: pd.DataFrame, shrine: str) -> pd.Series:
    """Get the most recent data record for a shrine."""
    shrine_df = get_shrine_data(df, shrine)
    if shrine_df.empty:
        return pd.Series()
    return shrine_df.iloc[-1]


def get_available_shrines(df: pd.DataFrame) -> list:
    """Return sorted list of unique shrine names."""
    return sorted(df["Shrine"].unique().tolist())


def get_year_range(df: pd.DataFrame) -> tuple:
    """Return (min_year, max_year) tuple."""
    return int(df["Year"].min()), int(df["Year"].max())


def get_summary_stats(df: pd.DataFrame) -> dict:
    """Compute high-level summary statistics across all shrines."""
    return {
        "total_records": len(df),
        "shrines": get_available_shrines(df),
        "year_range": get_year_range(df),
        "total_pilgrims": int(df["Pilgrim_Count"].sum()),
        "avg_pilgrims_monthly": int(df["Pilgrim_Count"].mean()),
        "max_pilgrims_monthly": int(df["Pilgrim_Count"].max()),
        "avg_temp": round(df["Avg_Temperature_C"].mean(), 1),
        "avg_rainfall": round(df["Rainfall_mm"].mean(), 1),
        "avg_capacity_util": round(df["Capacity_Utilization"].mean(), 2),
    }
