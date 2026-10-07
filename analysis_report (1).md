# Sales Data Analysis Report

**Dataset:** `sales_data.csv` (100 transactions, 1 Jan – 9 Apr 2024)
**Tools:** Python, pandas, matplotlib
**Author:** Jeevana Katta

---

## 1. Executive Summary

The business generated **12,365,048** in revenue from **478 units** across **100 orders** in 100 days. The average order was worth **123,650**, but the median was only **97,956**, so a minority of large orders pulls the average up.

Three findings matter most:

1. **Revenue depends on order size, not order volume.** Exactly one order was placed every day, yet monthly revenue swung between 2.66M and 4.49M. Order value is the lever.
2. **Laptops and the North/South regions drive the business.** Laptops bring 31.5% of revenue; North and South together bring 62.5%.
3. **West is the weak region.** It has almost as many orders as North (26 vs 28) but an average order value about 43% lower (81.7K vs 142.3K).

---

## 2. Data Quality and Cleaning

| Check | Result |
|---|---|
| Rows loaded | 100 |
| Missing values | 0 |
| Duplicate rows | 0 |
| Invalid rows (qty/price/total <= 0) | 0 |
| `Total_Sales != Quantity x Price` | 0 mismatches |
| Unique customers | 100 (every customer bought once) |

The dataset was already clean. The pipeline still validates every one of these checks, so it will catch problems if a messier file is supplied (see `tests/`).

**Data limitations to keep in mind**

- **No repeat customers.** Each Customer_ID appears once, so retention and lifetime value cannot be analysed.
- **Unit prices vary widely within a product.** A laptop sells for anywhere between 2,603 and 45,023. Price variation (coefficient of variation) is 49-61% for every product, which suggests discounting, different configurations, or synthetic data. Treat price-based conclusions with care.
- **April is a partial month** (9 days), so it is not comparable with the other months.
- **Small sample.** With 100 rows, patterns like weekday effects are suggestive, not conclusive.

---

## 3. Analysis and Insights

### 3.1 Revenue by product (bar chart)

![Revenue by product](../visualizations/01_revenue_by_product_bar.png)

| Product | Revenue | Share | Orders | Avg order value |
|---|---|---|---|---|
| Laptop | 3,889,210 | 31.5% | 24 | 162,050 |
| Tablet | 2,884,340 | 23.3% | 26 | 110,936 |
| Phone | 2,859,394 | 23.1% | 20 | 142,970 |
| Headphones | 1,384,033 | 11.2% | 15 | 92,269 |
| Monitor | 1,348,071 | 10.9% | 15 | 89,871 |

**Insight:** Laptops lead on revenue despite *not* having the most orders. Tablets sell most often (26 orders) but at a lower value per order. Phones have the second-highest average order (142,970) from only 20 orders, so there is room to grow by selling more of them. Headphones and Monitors together bring only 22% of revenue.

### 3.2 Monthly trend (line chart)

![Monthly revenue](../visualizations/02_monthly_revenue_line.png)

| Month | Revenue | Orders | Avg order value | Change vs prior month |
|---|---|---|---|---|
| Jan | 4,120,524 | 31 | 132,920 | - |
| Feb | 2,656,050 | 29 | 91,588 | -35.5% |
| Mar | 4,485,006 | 31 | 144,678 | +68.9% |
| Apr (9 days) | 1,103,468 | 9 | 122,608 | partial |

**Insight:** February fell 35.5% even though order count was almost unchanged (29 vs 31, and February has 29 days in 2024). The drop came entirely from a lower average order value (91.6K vs 132.9K). March recovered to the best month of the period. April's average order value (122.6K) is in line with Jan-Mar, so the early-April run rate looks healthy.

### 3.3 Regional performance (pie chart + heatmap)

![Region share](../visualizations/03_region_share_pie.png)

| Region | Revenue | Share | Orders | Avg order value |
|---|---|---|---|---|
| North | 3,983,635 | 32.2% | 28 | 142,273 |
| South | 3,737,852 | 30.2% | 27 | 138,439 |
| East | 2,519,639 | 20.4% | 19 | 132,613 |
| West | 2,123,922 | 17.2% | 26 | 81,689 |

**Insight:** West is the clearest opportunity. It has nearly the same number of orders as North and South but the lowest value per order. Its average unit price (about 22.3K) is also the lowest of any region, so West customers appear to buy cheaper items or at lower prices. East has the opposite issue: healthy order value but the fewest orders (19).

![Product x Region heatmap](../visualizations/05_product_region_heatmap.png)

**Insight:** Revenue is concentrated in a few product-region pairs: Laptops in North (1.80M), Phones in South (1.47M), Laptops in South (1.37M) and Tablets in North (1.19M). Weak spots stand out too: Monitors in South (only 39.9K) and Laptops in East (222K). These are good candidates for a targeted promotion or a check on stock and sales coverage.

### 3.4 Order value distribution (histogram)

![Order value histogram](../visualizations/04_order_value_histogram.png)

**Insight:** The distribution is right-skewed (skewness 0.88): the mean (123.7K) sits well above the median (98.0K). The top 20% of orders produce **46.8%** of revenue. Orders of 7+ units are only 30% of all orders but account for **51%** of revenue. Encouraging bulk purchases is therefore a direct way to grow revenue.

### 3.5 Price vs quantity (scatter plot)

![Price vs quantity](../visualizations/06_price_quantity_scatter.png)

**Insight:** Quantity and unit price are essentially uncorrelated (r = 0.008), meaning customers do not buy fewer units when the price is higher. Both quantity (r = 0.69) and price (r = 0.65) are strongly tied to order value. In practice, large orders come either from high quantities *or* high prices, and the data shows no sign that raising prices reduced volume.

### 3.6 Day-of-week pattern (supporting observation)

Average order value by weekday ranges from 66.2K on Thursday to 168.0K on Tuesday (about 14 orders per weekday). This is worth monitoring but, with so few data points per day, it should not be treated as a firm pattern.

---

## 4. Recommendations

1. **Protect and grow Laptops** (highest revenue and highest order value), especially in East where they under-perform.
2. **Lift West's order value** through bundles or upselling, since order count there is already healthy.
3. **Push bulk purchases** with quantity-based offers; large-quantity orders drive half of revenue.
4. **Investigate February's low average order value** to see whether it was promotion-driven or a seasonal effect.
5. **Standardise pricing.** A 49-61% price spread within one product makes forecasting and margin analysis hard.
6. **Start tracking repeat purchases.** One-time customers only means retention cannot be measured yet.

---

## 5. Technical Notes

- **Pipeline:** load (`load_data`) -> validate schema -> clean (`clean_data`) -> analyse (`analysis.py`) -> visualise (`visualize.py`).
- **Cleaning logic:** trim and title-case text, parse dates and numbers (invalid values become NaN and are dropped), remove duplicates and non-positive values, recompute `Total_Sales` if it disagrees with `Quantity x Price`.
- **Metrics:** groupby aggregations (sum, mean, count), month-over-month % change, pivot table, Pareto concentration (share of revenue from the top 20% of orders), Pearson correlation.
- **Validation:** 12 automated pytest tests cover errors (missing file, missing columns, empty data), cleaning behaviour, and metric correctness.
