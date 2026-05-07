"""
alerts.py - Multi-Factor Alert Engine
========================================
Generates color-coded alerts with severity levels.
Returns clean data structures suitable for native Streamlit rendering.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
#  Alert Data Structures
# ---------------------------------------------------------------------------
@dataclass
class AlertLevel:
    name: str       # LOW, MODERATE, HIGH, CRITICAL
    priority: int   # 0-3
    color: str

ALERT_LEVELS = {
    "LOW":      AlertLevel("LOW", 0, "#22c55e"),
    "MODERATE": AlertLevel("MODERATE", 1, "#f59e0b"),
    "HIGH":     AlertLevel("HIGH", 2, "#f97316"),
    "CRITICAL": AlertLevel("CRITICAL", 3, "#ef4444"),
}


@dataclass
class Alert:
    shrine: str
    category: str
    level: AlertLevel
    title: str
    message: str
    recommendation: str
    value: float = 0.0
    threshold: float = 0.0


# ---------------------------------------------------------------------------
#  Default Thresholds
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLDS = {
    "capacity_util_low": 0.60,
    "capacity_util_medium": 0.85,
    "capacity_util_high": 1.00,
    "temp_anomaly_moderate": 3.0,
    "temp_anomaly_high": 6.0,
    "esi_moderate": 40,
    "esi_critical": 70,
    "ndvi_decline_moderate": -0.05,
    "ndvi_decline_high": -0.10,
}


# ---------------------------------------------------------------------------
#  Individual Alert Checks
# ---------------------------------------------------------------------------
def check_tourist_overload(shrine: str, pilgrim_count: int, capacity: int,
                           thresholds: dict = None) -> Alert:
    """Check capacity utilization level."""
    t = thresholds or DEFAULT_THRESHOLDS
    ratio = pilgrim_count / max(capacity, 1)

    if ratio >= t["capacity_util_high"]:
        level = ALERT_LEVELS["CRITICAL"]
        msg = f"Capacity exceeded at {ratio*100:.0f}%. Pilgrim count ({pilgrim_count:,}) exceeds carrying capacity ({capacity:,})."
        rec = "Immediately restrict new entries. Deploy crowd management teams. Activate overflow zones."
    elif ratio >= t["capacity_util_medium"]:
        level = ALERT_LEVELS["HIGH"]
        msg = f"Capacity utilization at {ratio*100:.0f}%. Approaching safe limits."
        rec = "Issue crowd advisories. Prepare for potential entry restrictions. Increase monitoring."
    elif ratio >= t["capacity_util_low"]:
        level = ALERT_LEVELS["MODERATE"]
        msg = f"Moderate utilization at {ratio*100:.0f}%. Within operational range."
        rec = "Continue standard monitoring. Prepare contingency plans for peak hours."
    else:
        level = ALERT_LEVELS["LOW"]
        msg = f"Low utilization at {ratio*100:.0f}%. Well within safe limits."
        rec = "No action required. Normal operations."

    return Alert(
        shrine=shrine, category="tourist_overload", level=level,
        title=f"Capacity: {ratio*100:.0f}%", message=msg,
        recommendation=rec, value=ratio, threshold=t["capacity_util_high"],
    )


def check_climate_stress(shrine: str, temp_anomaly: float, rainfall: float,
                         humidity: float, thresholds: dict = None) -> Alert:
    """Check climate stress based on temperature anomaly."""
    t = thresholds or DEFAULT_THRESHOLDS
    temp_dev = abs(temp_anomaly)

    if temp_dev >= t["temp_anomaly_high"]:
        level = ALERT_LEVELS["HIGH"]
        msg = f"Temperature anomaly of {temp_anomaly:+.1f}C detected. Extreme deviation from historical average."
        rec = "Issue weather warnings. Review pilgrim safety protocols. Monitor for heat/cold stress incidents."
    elif temp_dev >= t["temp_anomaly_moderate"]:
        level = ALERT_LEVELS["MODERATE"]
        msg = f"Temperature anomaly of {temp_anomaly:+.1f}C. Notable deviation from baseline."
        rec = "Increase weather monitoring frequency. Prepare advisory communications."
    else:
        level = ALERT_LEVELS["LOW"]
        msg = f"Temperature within normal range. Anomaly: {temp_anomaly:+.1f}C."
        rec = "No climate concerns. Continue routine monitoring."

    return Alert(
        shrine=shrine, category="climate_stress", level=level,
        title=f"Temp Anomaly: {temp_anomaly:+.1f}C", message=msg,
        recommendation=rec, value=temp_dev, threshold=t["temp_anomaly_high"],
    )


def check_ndvi_degradation(shrine: str, ndvi_change: float, current_ndvi: float,
                           thresholds: dict = None) -> Alert:
    """Check vegetation health degradation."""
    t = thresholds or DEFAULT_THRESHOLDS

    if ndvi_change <= t["ndvi_decline_high"]:
        level = ALERT_LEVELS["CRITICAL"]
        msg = f"Severe NDVI decline of {ndvi_change:.3f}. Current NDVI: {current_ndvi:.3f}. Significant vegetation loss detected."
        rec = "Initiate ecological assessment. Restrict construction activity. Implement reforestation measures."
    elif ndvi_change <= t["ndvi_decline_moderate"]:
        level = ALERT_LEVELS["HIGH"]
        msg = f"NDVI decline of {ndvi_change:.3f}. Current NDVI: {current_ndvi:.3f}. Vegetation stress observed."
        rec = "Monitor vegetation health closely. Review impact of construction and tourism on surrounding areas."
    else:
        level = ALERT_LEVELS["LOW"]
        msg = f"NDVI stable or improving ({ndvi_change:+.3f}). Current: {current_ndvi:.3f}."
        rec = "Vegetation health normal. Continue periodic satellite monitoring."

    return Alert(
        shrine=shrine, category="ndvi_degradation", level=level,
        title=f"NDVI Change: {ndvi_change:+.3f}", message=msg,
        recommendation=rec, value=ndvi_change, threshold=t["ndvi_decline_high"],
    )


def check_esi_alert(shrine: str, esi_value: float, thresholds: dict = None) -> Alert:
    """Check ESI composite level."""
    t = thresholds or DEFAULT_THRESHOLDS

    if esi_value >= t["esi_critical"]:
        level = ALERT_LEVELS["CRITICAL"]
        msg = f"ESI at {esi_value:.1f}/100 (Critical). Ecosystem under severe combined stress."
        rec = "Coordinate multi-agency response. Implement immediate tourism restrictions. Deploy environmental monitoring teams."
    elif esi_value >= t["esi_moderate"]:
        level = ALERT_LEVELS["MODERATE"]
        msg = f"ESI at {esi_value:.1f}/100 (Moderate). Ecosystem experiencing combined pressure."
        rec = "Increase monitoring frequency. Review carrying capacity limits. Prepare escalation procedures."
    else:
        level = ALERT_LEVELS["LOW"]
        msg = f"ESI at {esi_value:.1f}/100 (Low). Ecosystem within healthy parameters."
        rec = "Continue standard operations and monitoring."

    return Alert(
        shrine=shrine, category="esi", level=level,
        title=f"ESI: {esi_value:.1f}/100", message=msg,
        recommendation=rec, value=esi_value, threshold=t["esi_critical"],
    )


# ---------------------------------------------------------------------------
#  Aggregate Alert Generation
# ---------------------------------------------------------------------------
def generate_all_alerts(
    df: pd.DataFrame,
    shrine: str,
    thresholds: dict = None,
) -> List[Alert]:
    """Generate all alerts for a given shrine using latest data."""
    t = thresholds or DEFAULT_THRESHOLDS
    shrine_df = df[df["Shrine"] == shrine]
    if shrine_df.empty:
        return []

    latest = shrine_df.iloc[-1]
    alerts = []

    # Tourist overload
    alerts.append(check_tourist_overload(
        shrine, int(latest["Pilgrim_Count"]), int(latest["Carrying_Capacity"]), t
    ))

    # Climate stress
    temp_anomaly = float(latest.get("Temp_Anomaly", 0))
    rainfall = float(latest.get("Rainfall_mm", 0))
    humidity = float(latest.get("Relative_Humidity_%", 60))
    alerts.append(check_climate_stress(shrine, temp_anomaly, rainfall, humidity, t))

    # NDVI degradation
    ndvi_change = float(latest.get("NDVI_Change", 0))
    current_ndvi = float(latest.get("NDVI", 0.5))
    alerts.append(check_ndvi_degradation(shrine, ndvi_change, current_ndvi, t))

    # ESI
    esi = float(latest.get("ESI", 0))
    alerts.append(check_esi_alert(shrine, esi, t))

    return alerts


def get_overall_risk_level(alerts: List[Alert]) -> AlertLevel:
    """Return the highest severity level from a list of alerts."""
    if not alerts:
        return ALERT_LEVELS["LOW"]
    return max(alerts, key=lambda a: a.level.priority).level


def count_alerts_by_level(alerts: List[Alert]) -> dict:
    """Count alerts per severity level."""
    counts = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "CRITICAL": 0}
    for a in alerts:
        counts[a.level.name] = counts.get(a.level.name, 0) + 1
    return counts
