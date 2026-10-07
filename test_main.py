"""Unit tests for the data pipeline and analysis functions. Run: pytest -v"""
import pandas as pd
import pytest

import main as app


@pytest.fixture
def sample():
    return pd.DataFrame({
        "Date": ["2024-01-01", "2024-01-02", "2024-02-01", "2024-02-02"],
        "Product": ["Phone", "laptop ", "Phone", "Tablet"],
        "Quantity": [2, 1, 3, 4],
        "Price": [100, 500, 100, 50],
        "Customer_ID": ["C1", "C2", "C3", "C4"],
        "Region": ["east", "North", "East", "West"],
        "Total_Sales": [200, 500, 300, 200],
    })


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        app.load_data("does_not_exist.csv")


def test_missing_columns_raises(sample):
    with pytest.raises(app.DataValidationError):
        app.clean_data(sample.drop(columns=["Region"]))


def test_empty_dataframe_raises(sample):
    with pytest.raises(app.DataValidationError):
        app.clean_data(sample.iloc[0:0])


def test_text_standardised(sample):
    df, _ = app.clean_data(sample)
    assert set(df["Product"]) == {"Phone", "Laptop", "Tablet"}
    assert set(df["Region"]) == {"East", "North", "West"}


def test_bad_values_dropped(sample):
    sample = sample.astype({"Quantity": object})
    sample.loc[0, "Quantity"] = "abc"
    sample.loc[1, "Date"] = "not-a-date"
    df, rep = app.clean_data(sample)
    assert len(df) == 2 and rep["missing_values"] == 2


def test_duplicates_removed(sample):
    df, rep = app.clean_data(pd.concat([sample, sample.iloc[[0]]]))
    assert rep["duplicates_removed"] == 1 and len(df) == 4


def test_negative_rows_removed(sample):
    sample.loc[0, "Quantity"] = -1
    sample.loc[0, "Total_Sales"] = -100
    df, rep = app.clean_data(sample)
    assert rep["invalid_rows_removed"] == 1


def test_total_sales_recomputed(sample):
    sample.loc[0, "Total_Sales"] = 999
    df, rep = app.clean_data(sample)
    assert rep["total_sales_mismatches"] == 1
    assert (df["Quantity"] * df["Price"] == df["Total_Sales"]).all()


def test_kpis(sample):
    df, _ = app.clean_data(sample)
    k = app.kpis(df)
    assert k["total_revenue"] == 1200 and k["total_units"] == 10 and k["transactions"] == 4


def test_by_group_shares_sum_to_100(sample):
    df, _ = app.clean_data(sample)
    assert app.by_group(df, "Product")["revenue_share_pct"].sum() == pytest.approx(100, abs=0.1)


def test_monthly_growth(sample):
    df, _ = app.clean_data(sample)
    m = app.monthly_trend(df)
    assert m.loc["2024-02", "mom_growth_pct"] == pytest.approx(-28.57, abs=0.01)


def test_concentration_bounds(sample):
    df, _ = app.clean_data(sample)
    assert 0 < app.concentration(df, 0.5) <= 100
