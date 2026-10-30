"""Step 2: run sql/analysis.sql, build RFM segments + cohort matrix, export CSVs and charts."""
import re, sqlite3
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
con = sqlite3.connect(ROOT / "data" / "ecommerce.db")

# run every named query in analysis.sql
blocks = re.split(r"^-- name: (\w+)\s*$", (ROOT / "sql" / "analysis.sql").read_text(), flags=re.M)
res = {}
for name, body in zip(blocks[1::2], blocks[2::2]):
    res[name] = pd.read_sql(body.strip().rstrip(";"), con)
    res[name].to_csv(OUT / f"sql_{name}.csv", index=False)

# ---- RFM segments ----
rfm = res["rfm_scores"].copy()
def seg(r):
    R, F, M = r.r_score, r.f_score, r.m_score
    if R >= 4 and F >= 4: return "Champions"
    if R <= 2 and F >= 4 and M >= 4: return "Can't Lose Them"
    if R >= 3 and F >= 3: return "Loyal Customers"
    if R <= 2 and F >= 3: return "At Risk"
    if R >= 4 and F <= 2: return "New / Promising"
    if R == 3 and F <= 2: return "Needs Attention"
    return "Hibernating / Lost"
rfm["segment"] = rfm.apply(seg, axis=1)
rfm.to_csv(OUT / "rfm_customers.csv", index=False)
tot_rev = rfm.monetary.sum()
seg_sum = (rfm.groupby("segment").agg(customers=("customer_id", "count"), revenue=("monetary", "sum"),
           avg_recency_days=("recency_days", "mean"), avg_orders=("frequency", "mean"), avg_spend=("monetary", "mean"))
           .assign(customer_pct=lambda d: 100 * d.customers / d.customers.sum(), revenue_pct=lambda d: 100 * d.revenue / tot_rev)
           .sort_values("revenue", ascending=False).round(1))
seg_sum.to_csv(OUT / "rfm_segment_summary.csv")

# ---- Cohort matrix ----
co = res["cohort_retention"].copy()
# data ends 9 Dec 2011 -> drop the partial last month so retention is not understated
last_idx = co.cohort_index.max()
co = co[co.cohort_index + co.months_since < last_idx].copy()
co["cohort"] = co.cohort_index.map(lambda i: f"{(i-1)//12}-{(i-1)%12+1:02d}")
mat = co.pivot(index="cohort", columns="months_since", values="retention_pct")
size = co.drop_duplicates("cohort").set_index("cohort").cohort_size
mat.insert(0, "cohort_size", size); mat.to_csv(OUT / "cohort_retention_matrix.csv")
co[["cohort", "months_since", "cohort_size", "active_customers", "retention_pct"]].to_csv(OUT / "cohort_long.csv", index=False)

# ---- Charts ----
m = res["monthly_revenue"]
fig, ax = plt.subplots(figsize=(9, 3.6)); ax.bar(m.month_label, m.revenue / 1000, color="#4f46e5")
ax.set_ylabel("Revenue (GBP thousands)"); ax.set_title("Monthly revenue (Dec 2011 is a partial month: data ends 9 Dec)")
plt.xticks(rotation=45, ha="right"); plt.tight_layout(); plt.savefig(OUT / "monthly_revenue.png", dpi=130); plt.close()

fig, ax = plt.subplots(figsize=(8, 3.8)); s = seg_sum.sort_values("revenue_pct")
ax.barh(s.index, s.revenue_pct, color="#4f46e5"); ax.set_xlabel("% of identified-customer revenue")
for i, (v, c) in enumerate(zip(s.revenue_pct, s.customer_pct)): ax.text(v + .5, i, f"{v:.0f}% rev / {c:.0f}% customers", va="center", fontsize=8)
ax.set_xlim(0, s.revenue_pct.max() * 1.6); ax.set_title("Revenue by RFM segment"); plt.tight_layout(); plt.savefig(OUT / "rfm_segments.png", dpi=130); plt.close()

fig, ax = plt.subplots(figsize=(9, 5)); d = mat.drop(columns="cohort_size")
im = ax.imshow(d.values, cmap="Blues", vmin=0, vmax=60, aspect="auto")
ax.set_xticks(range(d.shape[1])); ax.set_xticklabels(d.columns); ax.set_yticks(range(len(d))); ax.set_yticklabels(d.index)
for i in range(d.shape[0]):
    for j in range(d.shape[1]):
        if not np.isnan(d.values[i, j]): ax.text(j, i, f"{d.values[i,j]:.0f}", ha="center", va="center", fontsize=7)
ax.set_xlabel("Months since first purchase"); ax.set_ylabel("Cohort (first-purchase month)"); ax.set_title("Customer retention by cohort (%)")
plt.colorbar(im); plt.tight_layout(); plt.savefig(OUT / "cohort_heatmap.png", dpi=130); plt.close()

# ---- Fact export for Power BI ----
pd.read_sql("""SELECT f.sales_key, f.invoice_no, d.date, d.month_label, d.month_name, d.weekday, f.customer_key, c.customer_id, c.country, c.region,
 p.stock_code, p.description, f.quantity, f.unit_price, f.revenue FROM fact_sales f JOIN dim_date d ON d.date_key=f.date_key
 LEFT JOIN dim_customer c ON c.customer_key=f.customer_key JOIN dim_product p ON p.product_key=f.product_key""", con).to_csv(OUT / "sales_flat.csv", index=False)

for n in ["kpi_summary", "repeat_purchase", "returns_summary", "region_revenue", "top_product_per_region"]: print(n); print(res[n].to_string(index=False)); print()
print("TOP PRODUCTS"); print(res["top_products"].head(5).to_string(index=False))
print("\nMONTHLY"); print(m.to_string(index=False))
print("\nSEGMENTS"); print(seg_sum.to_string())
print("\nCOHORT size & M1/M3/M6/M12"); print(mat[["cohort_size", 1, 3, 6, 11]].to_string() if 11 in mat.columns else mat.iloc[:, :8].to_string())
print("\ntop10 products revenue share", res["top_products"].head(10).revenue_share_pct.sum())
