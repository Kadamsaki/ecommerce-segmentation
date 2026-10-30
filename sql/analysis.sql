-- Analysis queries. Written to run on both SQLite and MySQL 8 (CTEs + window functions).
-- Date arithmetic uses dim_date.month_index / day_num so no dialect-specific date functions are needed.
-- Each block starts with "-- name: <name>" (the Python runner uses this to export results).

-- name: kpi_summary
SELECT ROUND(SUM(f.revenue), 0)                                   AS total_revenue,
       COUNT(DISTINCT f.invoice_no)                               AS total_orders,
       COUNT(DISTINCT f.customer_key)                             AS identified_customers,
       ROUND(SUM(f.revenue) / COUNT(DISTINCT f.invoice_no), 2)    AS avg_order_value
FROM fact_sales f;

-- name: monthly_revenue
-- Revenue trend with month-over-month growth (LAG window function)
WITH m AS (
    SELECT d.month_label, d.month_index, SUM(f.revenue) AS revenue,
           COUNT(DISTINCT f.invoice_no) AS orders, COUNT(DISTINCT f.customer_key) AS customers
    FROM fact_sales f JOIN dim_date d ON d.date_key = f.date_key
    GROUP BY d.month_label, d.month_index
)
SELECT month_label, ROUND(revenue, 0) AS revenue, orders, customers,
       ROUND(revenue / orders, 2) AS aov,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month_index)) / LAG(revenue) OVER (ORDER BY month_index), 1) AS mom_growth_pct
FROM m ORDER BY month_index;

-- name: top_products
SELECT ROW_NUMBER() OVER (ORDER BY SUM(f.revenue) DESC) AS rnk, p.stock_code, p.description,
       SUM(f.quantity) AS units, ROUND(SUM(f.revenue), 0) AS revenue,
       ROUND(100.0 * SUM(f.revenue) / SUM(SUM(f.revenue)) OVER (), 2) AS revenue_share_pct
FROM fact_sales f JOIN dim_product p ON p.product_key = f.product_key
GROUP BY p.stock_code, p.description
ORDER BY revenue DESC LIMIT 20;

-- name: region_revenue
SELECT COALESCE(c.region, 'Unidentified') AS region, ROUND(SUM(f.revenue), 0) AS revenue,
       COUNT(DISTINCT f.invoice_no) AS orders,
       ROUND(100.0 * SUM(f.revenue) / SUM(SUM(f.revenue)) OVER (), 1) AS revenue_share_pct
FROM fact_sales f LEFT JOIN dim_customer c ON c.customer_key = f.customer_key
GROUP BY COALESCE(c.region, 'Unidentified') ORDER BY revenue DESC;

-- name: country_revenue
SELECT c.country, ROUND(SUM(f.revenue), 0) AS revenue, COUNT(DISTINCT c.customer_key) AS customers,
       RANK() OVER (ORDER BY SUM(f.revenue) DESC) AS rnk
FROM fact_sales f JOIN dim_customer c ON c.customer_key = f.customer_key
GROUP BY c.country ORDER BY revenue DESC;

-- name: top_product_per_region
-- Best-selling product in each region (RANK partitioned by region)
WITH x AS (
    SELECT c.region, p.description, SUM(f.revenue) AS revenue,
           RANK() OVER (PARTITION BY c.region ORDER BY SUM(f.revenue) DESC) AS rk
    FROM fact_sales f JOIN dim_customer c ON c.customer_key = f.customer_key
                      JOIN dim_product  p ON p.product_key  = f.product_key
    GROUP BY c.region, p.description
)
SELECT region, description, ROUND(revenue, 0) AS revenue FROM x WHERE rk = 1 ORDER BY revenue DESC;

-- name: repeat_purchase
-- Repeat-purchase rate = share of identified customers with 2+ orders
WITH o AS (
    SELECT customer_key, COUNT(DISTINCT invoice_no) AS orders
    FROM fact_sales WHERE customer_key IS NOT NULL GROUP BY customer_key
)
SELECT COUNT(*) AS customers,
       SUM(CASE WHEN orders >= 2 THEN 1 ELSE 0 END) AS repeat_customers,
       ROUND(100.0 * SUM(CASE WHEN orders >= 2 THEN 1 ELSE 0 END) / COUNT(*), 1) AS repeat_rate_pct,
       ROUND(AVG(orders), 2) AS avg_orders_per_customer
FROM o;

-- name: rfm_scores
-- RFM: Recency (days since last order), Frequency (distinct orders), Monetary (total revenue).
-- Snapshot date = day after the last transaction. R and M scored 1-5 with NTILE, F scored with fixed bands
-- (most customers have very few orders, so quintiles of F would split ties arbitrarily).
WITH snap AS (SELECT MAX(day_num) + 1 AS snap_day FROM dim_date),
base AS (
    SELECT f.customer_key,
           (SELECT snap_day FROM snap) - MAX(d.day_num) AS recency_days,
           COUNT(DISTINCT f.invoice_no)                  AS frequency,
           ROUND(SUM(f.revenue), 2)                      AS monetary
    FROM fact_sales f JOIN dim_date d ON d.date_key = f.date_key
    WHERE f.customer_key IS NOT NULL
    GROUP BY f.customer_key
)
SELECT b.customer_key, c.customer_id, c.country, b.recency_days, b.frequency, b.monetary,
       6 - NTILE(5) OVER (ORDER BY b.recency_days, b.customer_key) AS r_score,
       CASE WHEN b.frequency = 1 THEN 1 WHEN b.frequency = 2 THEN 2 WHEN b.frequency <= 4 THEN 3
            WHEN b.frequency <= 8 THEN 4 ELSE 5 END AS f_score,
       NTILE(5) OVER (ORDER BY b.monetary, b.customer_key) AS m_score
FROM base b JOIN dim_customer c ON c.customer_key = b.customer_key;

-- name: cohort_retention
-- Monthly cohorts: customers grouped by first-purchase month; retention = share active k months later.
WITH first_m AS (
    SELECT f.customer_key, MIN(d.month_index) AS cohort_index
    FROM fact_sales f JOIN dim_date d ON d.date_key = f.date_key
    WHERE f.customer_key IS NOT NULL GROUP BY f.customer_key
),
activity AS (
    SELECT DISTINCT f.customer_key, d.month_index AS active_index
    FROM fact_sales f JOIN dim_date d ON d.date_key = f.date_key
    WHERE f.customer_key IS NOT NULL
),
joined AS (
    SELECT fm.cohort_index, a.active_index - fm.cohort_index AS months_since, a.customer_key
    FROM first_m fm JOIN activity a ON a.customer_key = fm.customer_key
),
sizes AS (SELECT cohort_index, COUNT(*) AS cohort_size FROM first_m GROUP BY cohort_index)
SELECT j.cohort_index, j.months_since, s.cohort_size, COUNT(DISTINCT j.customer_key) AS active_customers,
       ROUND(100.0 * COUNT(DISTINCT j.customer_key) / s.cohort_size, 1) AS retention_pct
FROM joined j JOIN sizes s ON s.cohort_index = j.cohort_index
GROUP BY j.cohort_index, j.months_since, s.cohort_size
ORDER BY j.cohort_index, j.months_since;

-- name: returns_summary
SELECT ROUND(-SUM(r.revenue), 0) AS returned_value,
       (SELECT ROUND(SUM(revenue), 0) FROM fact_sales) AS gross_sales,
       ROUND(100.0 * -SUM(r.revenue) / (SELECT SUM(revenue) FROM fact_sales), 2) AS return_rate_pct
FROM fact_returns r;
