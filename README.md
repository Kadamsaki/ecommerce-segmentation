# E-Commerce Sales & Customer Segmentation Analysis

SQL-first analysis of 541,909 real transactions from a UK online gift retailer (UCI *Online Retail*, Dec 2010 - Dec 2011): star-schema database, revenue/product/region analysis, RFM segmentation, cohort retention, and business recommendations.

**Stack:** SQL (MySQL 8-compatible; verified on SQLite), Python (pandas, matplotlib), Power BI.

## Key results
| Metric | Value |
|---|---|
| Revenue (clean sales) | GBP 10.25M across 19,773 orders |
| Average order value | GBP 518 (many customers are wholesalers) |
| Repeat-purchase rate | 65.3% of identified customers ordered 2+ times (4.25 orders on average) |
| Cancelled-order value | 4.6% of gross sales |
| Revenue concentration | UK 70.7%, Europe 12.5%, 14.7% has no customer ID |
| Seasonality | Sep-Nov generated 35% of annual revenue |
| Product mix | Long tail: top 10 products are only 9.5% of revenue |

**RFM segments (4,334 identified customers):**
| Segment | Customers | % of revenue |
|---|---|---|
| Champions | 18.9% | 61.6% |
| Loyal Customers | 18.2% | 15.6% |
| Hibernating / Lost | 31.0% | 7.8% |
| New / Promising | 11.9% | 4.8% |
| At Risk | 7.0% | 4.8% |
| Needs Attention | 11.1% | 2.9% |
| Can't Lose Them | 2.0% | 2.7% |

## Recommendations
1. **Protect Champions** (820 customers, 62% of revenue): loyalty tiers, early access, account managers. Losing 10% of them would cost roughly GBP 540k a year.
2. **Win back "Can't Lose Them" and "At Risk"** (391 customers, ~GBP 650k historic spend, 120-140 days since last order) with personalised outreach before they become Lost.
3. **Convert New / Promising customers to a second order.** One-month retention is only 15-23% for 2011 cohorts, so a second-order incentive has room to work.
4. **Plan around seasonality.** Build stock and campaigns from August, since Sep-Nov is 35% of revenue; run promotions to lift the Feb and Apr dips.
5. **Close the tracking gap.** 14.7% of revenue (GBP 1.5M) has no customer ID; encourage account creation at checkout so these buyers can be segmented.

## Data and design
- **Cleaning:** removed 5,268 duplicates; set aside 9,251 cancellation lines (kept as `fact_returns`); removed non-product lines (postage, fees, manual adjustments) and rows with zero/negative quantity or price. Result: 522,537 sales lines.
- **Star schema:** `fact_sales` + `dim_customer`, `dim_product`, `dim_date` (plus `fact_returns`). `dim_date` carries `month_index` and `day_num` so cohort and recency maths needs no dialect-specific date functions.
- **SQL:** joins, CTEs, window functions (LAG for MoM growth, NTILE for RFM, RANK/ROW_NUMBER for rankings) in `sql/analysis.sql`.
- **RFM:** snapshot = day after last transaction; Recency and Monetary scored with NTILE(5); Frequency scored with fixed bands (1, 2, 3-4, 5-8, 9+ orders) because most customers have 1-2 orders and quintiles would split ties arbitrarily.
- **Cohorts:** customers grouped by first-purchase month; retention = share active k months later.

## Caveats
- The data ends on **9 Dec 2011**; December is partial and is excluded from retention figures and ignored when judging trends.
- The **2010-12 cohort** is not all new customers: it includes everyone already active when the data starts, so its retention is higher.
- ~25% of rows have no CustomerID, so RFM and cohorts cover identified customers only.
- Segment cut-offs are rule-based choices, not a fitted model.
- Built and tested on SQLite; `sql/schema_mysql.sql` provides the MySQL 8 schema, which I have not run against a live MySQL server.

## Run
```
pip install -r requirements.txt
python src/build_db.py     # clean + build star schema -> data/ecommerce.db
python src/analyze.py      # run SQL, RFM, cohorts -> outputs/
```
Put the raw file at `data/online_retail.csv`. For Power BI, import `outputs/sales_flat.csv`, `rfm_customers.csv`, `rfm_segment_summary.csv`, `cohort_long.csv` and `sql_monthly_revenue.csv`.
