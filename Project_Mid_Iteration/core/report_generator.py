"""
report_generator.py — Downloadable Report Generator
======================================================
Generates PDF and CSV reports for the Char Dham Intelligence
Dashboard, including summary statistics, model predictions,
alert summaries, and geospatial highlights.
"""

import io
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional

import re

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False


def _strip_emoji(text: str) -> str:
    """Remove emoji and other non-Latin-1 characters for PDF compatibility."""
    # Remove emoji / supplementary Unicode characters
    text = re.sub(
        r'[\U0001F000-\U0001FFFF\U00002702-\U000027B0\U000024C2-\U0001F251'
        r'\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF'
        r'\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\u200d\ufe0f]+',
        '', text
    )
    # Replace any remaining non-latin-1 chars
    text = text.encode('latin-1', errors='ignore').decode('latin-1')
    return text.strip()


# ============================================================================
#  PDF Report Generator
# ============================================================================
class CharDhamReport(FPDF if FPDF_AVAILABLE else object):
    """Custom PDF report with Char Dham branding."""

    def __init__(self):
        if not FPDF_AVAILABLE:
            raise ImportError("fpdf2 is required. Install: pip install fpdf2")
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(0, 150, 80)
        self.cell(0, 10, "Char Dham Intelligence Dashboard", 0, new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M IST')}", 0,
                  new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(5)
        # Horizontal rule
        self.set_draw_color(0, 150, 80)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}} | Char Dham Research Team | Confidential", 0, align="C")

    def add_section_title(self, title: str):
        if self.page == 0:
            self.add_page()
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(0, 100, 60)
        self.cell(0, 10, _strip_emoji(title), 0, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(0, 150, 80)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def add_body_text(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 6, _strip_emoji(text))
        self.ln(3)

    def add_kpi_row(self, label: str, value: str, unit: str = ""):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(60, 60, 60)
        self.cell(80, 7, _strip_emoji(label), 0)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(0, 120, 70)
        self.cell(0, 7, _strip_emoji(f"{value} {unit}"), 0, new_x="LMARGIN", new_y="NEXT")

    def add_table(self, headers: list, rows: list):
        """Add a simple table to the report."""
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(0, 150, 80)
        self.set_text_color(255, 255, 255)
        col_width = (self.w - 20) / len(headers)

        for header in headers:
            self.cell(col_width, 8, str(header), 1, fill=True, align="C")
        self.ln()

        self.set_font("Helvetica", "", 9)
        self.set_text_color(40, 40, 40)
        fill = False
        for row in rows:
            if fill:
                self.set_fill_color(240, 248, 240)
            for val in row:
                self.cell(col_width, 7, str(val), 1, fill=fill, align="C")
            self.ln()
            fill = not fill

    def add_alert_entry(self, level: str, title: str, message: str):
        """Add a color-coded alert entry."""
        color_map = {
            "CRITICAL": (255, 23, 68),
            "HIGH": (255, 145, 0),
            "MODERATE": (255, 214, 0),
            "LOW": (0, 200, 100),
        }
        r, g, b = color_map.get(level, (120, 120, 120))

        self.set_font("Helvetica", "B", 10)
        self.set_text_color(r, g, b)
        self.cell(0, 7, _strip_emoji(f"[{level}] {title}"), 0, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 5, _strip_emoji(message))
        self.ln(3)


def generate_shrine_report(
    shrine: str,
    df: pd.DataFrame,
    predictions: Optional[dict] = None,
    alerts: Optional[list] = None,
    model_metrics: Optional[dict] = None,
) -> bytes:
    """
    Generate a comprehensive PDF report for a shrine.
    Returns report as bytes for download.
    """
    if not FPDF_AVAILABLE:
        return b""

    pdf = CharDhamReport()
    pdf.alias_nb_pages()
    pdf.add_page()

    shrine_df = df[df["Shrine"] == shrine]
    if shrine_df.empty:
        pdf.add_body_text(f"No data available for {shrine}.")
        return bytes(pdf.output())

    latest = shrine_df.iloc[-1]

    # --- Title ---
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 12, f"Shrine Report: {shrine}", 0, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)

    # --- Section 1: Overview ---
    pdf.add_section_title("1. Overview & Key Metrics")
    pdf.add_kpi_row("Total Data Records", str(len(shrine_df)))
    pdf.add_kpi_row("Year Range", f"{int(shrine_df['Year'].min())} - {int(shrine_df['Year'].max())}")
    pdf.add_kpi_row("Latest Pilgrim Count", f"{int(latest['Pilgrim_Count']):,}")
    pdf.add_kpi_row("Carrying Capacity", f"{int(latest['Carrying_Capacity']):,}")
    pdf.add_kpi_row("Capacity Utilization", f"{latest.get('Capacity_Utilization', 0)*100:.1f}", "%")
    pdf.add_kpi_row("Average Temperature", f"{shrine_df['Avg_Temperature_C'].mean():.1f}", "°C")
    pdf.add_kpi_row("Average Rainfall", f"{shrine_df['Rainfall_mm'].mean():.1f}", "mm")

    esi = latest.get("ESI", 0)
    pdf.add_kpi_row("Current ESI", f"{esi:.1f}", "/ 100")
    pdf.ln(5)

    # --- Section 2: Historical Summary ---
    pdf.add_section_title("2. Historical Statistics")
    stats_headers = ["Metric", "Mean", "Min", "Max", "Std Dev"]
    stats_rows = []
    for col in ["Pilgrim_Count", "Avg_Temperature_C", "Rainfall_mm", "Estimated_Waste_Tons"]:
        if col in shrine_df.columns:
            s = shrine_df[col]
            stats_rows.append([
                col.replace("_", " "),
                f"{s.mean():,.1f}",
                f"{s.min():,.1f}",
                f"{s.max():,.1f}",
                f"{s.std():,.1f}",
            ])
    if stats_rows:
        pdf.add_table(stats_headers, stats_rows)
    pdf.ln(5)

    # --- Section 3: Model Results ---
    if model_metrics:
        pdf.add_section_title("3. ML Model Performance")
        for model_name, metrics in model_metrics.items():
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(0, 100, 60)
            pdf.cell(0, 7, f"Model: {model_name}", 0, new_x="LMARGIN", new_y="NEXT")
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    pdf.add_kpi_row(f"  {k.upper()}", f"{v:.3f}")
        pdf.ln(5)

    # --- Section 4: Predictions ---
    if predictions:
        pdf.add_section_title("4. Forecast Summary")
        for model_name, pred_data in predictions.items():
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 7, f"{model_name} Forecast:", 0, new_x="LMARGIN", new_y="NEXT")
            if "forecast_mean" in pred_data and pred_data.get("future_dates") is not None:
                headers = ["Date", "Predicted Pilgrims"]
                rows = []
                dates = pred_data["future_dates"]
                means = pred_data["forecast_mean"]
                for d, m in zip(dates, means):
                    rows.append([
                        d.strftime("%Y-%m") if hasattr(d, "strftime") else str(d),
                        f"{m:,.0f}",
                    ])
                pdf.add_table(headers, rows[:6])  # Show first 6 months
                pdf.ln(3)

    # --- Section 5: Alerts ---
    if alerts:
        pdf.add_page()
        pdf.add_section_title("5. Active Alerts & Recommendations")
        for alert in alerts:
            pdf.add_alert_entry(alert.level.name, alert.title, f"{alert.message}\nRecommendation: {alert.recommendation}")

    # --- Footer note ---
    pdf.ln(10)
    pdf.add_body_text(
        "This report was auto-generated by the Char Dham Intelligence Dashboard. "
        "Data sources include historical records, OpenWeatherMap API, and ML model outputs. "
        "Predictions are estimates and should be validated with ground-truth observations."
    )

    return bytes(pdf.output())


# ============================================================================
#  CSV Exports
# ============================================================================
def generate_csv_export(df: pd.DataFrame, shrine: Optional[str] = None) -> str:
    """Generate CSV string for download. Optionally filter by shrine."""
    if shrine:
        df = df[df["Shrine"] == shrine]
    return df.to_csv(index=False)


def generate_summary_csv(df: pd.DataFrame) -> str:
    """Generate a high-level summary CSV across all shrines."""
    summary = df.groupby("Shrine").agg({
        "Pilgrim_Count": ["count", "mean", "max", "sum"],
        "Avg_Temperature_C": ["mean", "min", "max"],
        "Rainfall_mm": ["mean", "max"],
        "Carrying_Capacity": "first",
    })
    summary.columns = ["_".join(col).strip() for col in summary.columns]
    return summary.to_csv()
