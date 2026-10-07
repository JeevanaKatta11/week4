"""Sales Data Analysis - end-to-end pipeline (single file).

Run:  python main.py [--data data/sales_data.csv]
Does: load -> validate/clean -> analyse -> visualise -> write report tables.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless-safe backend
import matplotlib.pyplot as plt
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- DATA PIPELINE
logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["Date", "Product", "Quantity", "Price", "Customer_ID", "Region", "Total_Sales"]


class DataValidationError(Exception):
    """Raised when the dataset does not meet the expected structure."""


def load_data(path: str | Path) -> pd.DataFrame:
    """Load the CSV file, with clear errors for common failure modes."""
    path = Path(path)
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Data file not found: {path}") from None
    except pd.errors.EmptyDataError:
        raise DataValidationError(f"Data file is empty: {path}") from None
    except pd.errors.ParserError as exc:
        raise DataValidationError(f"Could not parse {path}: {exc}") from exc
    logger.info("Loaded %d rows x %d columns from %s", *df.shape, path)
    return df


def validate_schema(df: pd.DataFrame) -> None:
    """Check that all required columns are present and the data is non-empty."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(f"Missing required columns: {missing}")
    if df.empty:
        raise DataValidationError("Dataset contains no rows.")


def clean_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Clean the data and return (clean_df, cleaning_report).

    Steps: strip text, parse dates, coerce numerics, drop duplicates and
    invalid rows, and verify Total_Sales == Quantity * Price.
    """
    validate_schema(df)
    report = {"rows_in": len(df)}
    df = df.copy()

    # Standardise text columns
    for col in ["Product", "Region", "Customer_ID"]:
        df[col] = df[col].astype(str).str.strip()
    df["Product"] = df["Product"].str.title()
    df["Region"] = df["Region"].str.title()

    # Parse types (bad values become NaN/NaT and are removed below)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in ["Quantity", "Price", "Total_Sales"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    report["missing_values"] = int(df.isna().sum().sum())
    df = df.dropna()

    report["duplicates_removed"] = int(df.duplicated().sum())
    df = df.drop_duplicates()

    invalid = (df["Quantity"] <= 0) | (df["Price"] <= 0) | (df["Total_Sales"] <= 0)
    report["invalid_rows_removed"] = int(invalid.sum())
    df = df[~invalid]

    mismatch = (df["Quantity"] * df["Price"] != df["Total_Sales"])
    report["total_sales_mismatches"] = int(mismatch.sum())
    if mismatch.any():
        logger.warning("Recomputing Total_Sales for %d mismatched rows", mismatch.sum())
        df.loc[mismatch, "Total_Sales"] = df["Quantity"] * df["Price"]

    df = df.sort_values("Date").reset_index(drop=True)
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    df["Weekday"] = df["Date"].dt.day_name()

    report["rows_out"] = len(df)
    return df, report


# ---------------------------------------------------------------- ANALYSIS
def kpis(df: pd.DataFrame) -> dict:
    """Headline business metrics."""
    return {
        "total_revenue": int(df["Total_Sales"].sum()),
        "total_units": int(df["Quantity"].sum()),
        "transactions": len(df),
        "avg_order_value": float(df["Total_Sales"].mean()),
        "median_order_value": float(df["Total_Sales"].median()),
        "avg_units_per_order": float(df["Quantity"].mean()),
        "date_start": df["Date"].min().date().isoformat(),
        "date_end": df["Date"].max().date().isoformat(),
    }


def by_group(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Revenue, units, orders, average order value and revenue share per group."""
    g = df.groupby(col).agg(
        revenue=("Total_Sales", "sum"),
        units=("Quantity", "sum"),
        orders=("Total_Sales", "size"),
        avg_order_value=("Total_Sales", "mean"),
        avg_unit_price=("Price", "mean"),
    )
    g["revenue_share_pct"] = g["revenue"] / g["revenue"].sum() * 100
    return g.sort_values("revenue", ascending=False).round(2)


def monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue per month plus month-over-month growth (%)."""
    m = df.groupby("Month").agg(revenue=("Total_Sales", "sum"), orders=("Total_Sales", "size"))
    m["mom_growth_pct"] = m["revenue"].pct_change() * 100
    return m.round(2)


def product_region_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue pivot: products (rows) x regions (columns)."""
    return df.pivot_table(index="Product", columns="Region", values="Total_Sales",
                          aggfunc="sum", fill_value=0)


def top_orders(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    return df.nlargest(n, "Total_Sales")[["Date", "Product", "Quantity", "Price", "Region", "Total_Sales"]]


def concentration(df: pd.DataFrame, top_pct: float = 0.2) -> float:
    """Share of revenue coming from the top `top_pct` of orders (Pareto check)."""
    s = df["Total_Sales"].sort_values(ascending=False)
    k = max(1, int(round(len(s) * top_pct)))
    return float(s.head(k).sum() / s.sum() * 100)


def price_variability(df: pd.DataFrame) -> pd.DataFrame:
    """Min / mean / max unit price and coefficient of variation per product."""
    g = df.groupby("Product")["Price"].agg(["min", "mean", "max", "std"])
    g["cv_pct"] = g["std"] / g["mean"] * 100
    return g.round(1)


def correlations(df: pd.DataFrame) -> pd.DataFrame:
    return df[["Quantity", "Price", "Total_Sales"]].corr().round(3)


# ---------------------------------------------------------------- VISUALISATION

PALETTE = ["#2F5D8A", "#E07A3F", "#4C9F70", "#B5485D", "#8A7BC8"]
plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 160, "axes.spines.top": False,
    "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlesize": 13,
    "font.size": 10,
})


def _millions(x, _pos=None):
    return f"{x/1e6:.1f}M"


def _save(fig, out_dir: Path, name: str) -> Path:
    path = out_dir / name
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def bar_revenue_by_product(prod: pd.DataFrame, out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(prod.index, prod["revenue"], color=PALETTE[: len(prod)])
    ax.bar_label(bars, labels=[f"{v/1e6:.2f}M" for v in prod["revenue"]], padding=3)
    ax.set_title("Total Revenue by Product")
    ax.set_ylabel("Revenue")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(_millions))
    ax.set_ylim(0, prod["revenue"].max() * 1.12)
    return _save(fig, out_dir, "01_revenue_by_product_bar.png")


def line_monthly_trend(trend: pd.DataFrame, out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(trend.index, trend["revenue"], marker="o", lw=2.5, color=PALETTE[0])
    for x, y in zip(trend.index, trend["revenue"]):
        ax.annotate(f"{y/1e6:.2f}M", (x, y), textcoords="offset points", xytext=(0, 9), ha="center")
    ax.set_title("Monthly Revenue Trend")
    ax.set_ylabel("Revenue")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(_millions))
    ax.set_ylim(0, trend["revenue"].max() * 1.2)
    ax.grid(axis="y", alpha=0.3)
    ax.text(0.99, 0.02, "Note: final month is a partial month.", transform=ax.transAxes,
            ha="right", fontsize=8, style="italic")
    return _save(fig, out_dir, "02_monthly_revenue_line.png")


def pie_region_share(region: pd.DataFrame, out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    ax.pie(region["revenue"], labels=region.index, autopct="%1.1f%%", startangle=90,
           colors=PALETTE, wedgeprops={"edgecolor": "white", "linewidth": 2})
    ax.set_title("Revenue Share by Region")
    return _save(fig, out_dir, "03_region_share_pie.png")


def hist_order_values(df: pd.DataFrame, out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(df["Total_Sales"], bins=12, color=PALETTE[2], edgecolor="white")
    ax.axvline(df["Total_Sales"].mean(), color=PALETTE[1], ls="--", lw=2,
               label=f"Mean: {df['Total_Sales'].mean():,.0f}")
    ax.axvline(df["Total_Sales"].median(), color=PALETTE[3], ls=":", lw=2,
               label=f"Median: {df['Total_Sales'].median():,.0f}")
    ax.set_title("Distribution of Order Values")
    ax.set_xlabel("Order value")
    ax.set_ylabel("Number of orders")
    ax.legend()
    return _save(fig, out_dir, "04_order_value_histogram.png")


def heatmap_product_region(matrix: pd.DataFrame, out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(matrix.values, cmap="Blues")
    ax.set_xticks(range(len(matrix.columns)), matrix.columns)
    ax.set_yticks(range(len(matrix.index)), matrix.index)
    thresh = matrix.values.max() * 0.55
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v = matrix.values[i, j]
            ax.text(j, i, f"{v/1e6:.2f}M", ha="center", va="center",
                    color="white" if v > thresh else "black")
    ax.set_title("Revenue Heatmap: Product x Region")
    for s in ax.spines.values():
        s.set_visible(False)
    fig.colorbar(im, ax=ax, label="Revenue", shrink=0.8)
    return _save(fig, out_dir, "05_product_region_heatmap.png")


def scatter_qty_price(df: pd.DataFrame, out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 5))
    for color, (name, grp) in zip(PALETTE, df.groupby("Product")):
        ax.scatter(grp["Price"], grp["Quantity"], s=grp["Total_Sales"] / 2500,
                   alpha=0.65, color=color, label=name, edgecolor="white")
    ax.set_title("Unit Price vs Quantity (bubble size = order value)")
    ax.set_xlabel("Unit price")
    ax.set_ylabel("Quantity")
    ax.legend(title="Product", loc="upper right", fontsize=8, markerscale=0.5)
    return _save(fig, out_dir, "06_price_quantity_scatter.png")


# ---------------------------------------------------------------- MAIN
ROOT = Path(__file__).resolve().parent


def run(data_path: Path) -> dict:
    out_vis = ROOT / "visualizations"
    out_rep = ROOT / "report"
    out_vis.mkdir(exist_ok=True)
    out_rep.mkdir(exist_ok=True)

    # 1. Load + clean
    raw = load_data(data_path)
    df, clean_report = clean_data(raw)
    df.to_csv(ROOT / "data" / "sales_data_clean.csv", index=False)

    # 2. Analyse
    results = {
        "kpis": kpis(df),
        "cleaning": clean_report,
        "by_product": by_group(df, "Product"),
        "by_region": by_group(df, "Region"),
        "monthly": monthly_trend(df),
        "matrix": product_region_matrix(df),
        "top_orders": top_orders(df),
        "top20_share": concentration(df, 0.2),
        "price_var": price_variability(df),
        "corr": correlations(df),
    }

    # 3. Visualise
    charts = [
        bar_revenue_by_product(results["by_product"], out_vis),
        line_monthly_trend(results["monthly"], out_vis),
        pie_region_share(results["by_region"], out_vis),
        hist_order_values(df, out_vis),
        heatmap_product_region(results["matrix"], out_vis),
        scatter_qty_price(df, out_vis),
    ]

    # 4. Save summary tables for the report
    results["by_product"].to_csv(out_rep / "summary_by_product.csv")
    results["by_region"].to_csv(out_rep / "summary_by_region.csv")
    results["monthly"].to_csv(out_rep / "summary_monthly.csv")
    (out_rep / "kpis.json").write_text(json.dumps(
        {"kpis": results["kpis"], "cleaning": clean_report,
         "top20_orders_revenue_share_pct": round(results["top20_share"], 1)}, indent=2))

    results["charts"] = [str(c.relative_to(ROOT)) for c in charts]
    return results


def print_summary(r: dict) -> None:
    k = r["kpis"]
    print("=" * 60)
    print(f"SALES ANALYSIS  ({k['date_start']} to {k['date_end']})")
    print("=" * 60)
    print(f"Cleaning: {r['cleaning']}")
    print(f"Total revenue : {k['total_revenue']:,}")
    print(f"Units sold    : {k['total_units']:,}")
    print(f"Transactions  : {k['transactions']}")
    print(f"Avg order     : {k['avg_order_value']:,.0f} (median {k['median_order_value']:,.0f})")
    print("\nBy product:\n", r["by_product"])
    print("\nBy region:\n", r["by_region"])
    print("\nMonthly:\n", r["monthly"])
    print("\nProduct x Region revenue:\n", r["matrix"])
    print("\nTop 5 orders:\n", r["top_orders"])
    print(f"\nTop 20% of orders = {r['top20_share']:.1f}% of revenue")
    print("\nUnit price variability:\n", r["price_var"])
    print("\nCorrelations:\n", r["corr"])
    print("\nCharts saved:", *r["charts"], sep="\n  ")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sales data analysis pipeline")
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "sales_data.csv")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.getLogger("matplotlib").setLevel(logging.WARNING)  # silence plotting chatter
    try:
        print_summary(run(args.data))
    except (FileNotFoundError, DataValidationError) as exc:
        logging.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
