"""Step 1: clean raw Online Retail data and load a star schema into SQLite (data/ecommerce.db).
The same schema is provided for MySQL in sql/schema_mysql.sql."""
import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
raw = pd.read_csv(ROOT / "data" / "online_retail.csv", encoding="latin1")
log = {"raw_rows": len(raw)}

# ---------- Cleaning ----------
df = raw.drop_duplicates().copy()
log["duplicates_removed"] = log["raw_rows"] - len(df)
df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], format="%m/%d/%y %H:%M")
df["InvoiceNo"] = df["InvoiceNo"].astype(str)
df["StockCode"] = df["StockCode"].astype(str).str.strip().str.upper()
df["Description"] = df["Description"].astype("string").str.strip().str.upper()

cancel = df.InvoiceNo.str.startswith("C")
log["cancellations_set_aside"] = int(cancel.sum())
# non-product lines (postage, fees, manual adjustments, samples)
non_product = df.StockCode.isin(["POST", "D", "M", "BANK CHARGES", "DOT", "CRUK", "S", "B", "AMAZONFEE", "C2", "PADS", "GIFT"]) \
              | df.StockCode.str.startswith("GIFT")
log["non_product_lines_removed"] = int((non_product & ~cancel).sum())
bad = (df.Quantity <= 0) | (df.UnitPrice <= 0)
log["bad_qty_or_price_removed"] = int((bad & ~cancel & ~non_product).sum())

sales = df[~cancel & ~non_product & ~bad].copy()
returns = df[cancel & ~non_product].copy()
sales["Revenue"] = (sales.Quantity * sales.UnitPrice).round(2)
returns["Revenue"] = (returns.Quantity * returns.UnitPrice).round(2)
log["sales_rows"] = len(sales); log["return_rows"] = len(returns)
log["sales_rows_without_customer_id"] = int(sales.CustomerID.isna().sum())

# ---------- Dimensions ----------
# product: one description per stock code (most frequent)
prod = (sales.groupby(["StockCode", "Description"]).size().reset_index(name="n")
        .sort_values(["StockCode", "n"], ascending=[True, False]).drop_duplicates("StockCode")[["StockCode", "Description"]]
        .reset_index(drop=True))
prod.insert(0, "product_key", prod.index + 1)

cust = (sales.dropna(subset=["CustomerID"]).sort_values("InvoiceDate")
        .groupby("CustomerID").agg(country=("Country", "last")).reset_index())
cust["CustomerID"] = cust.CustomerID.astype(int)
cust.insert(0, "customer_key", cust.index + 1)

region_map = {"United Kingdom": "UK", "EIRE": "Europe", "Germany": "Europe", "France": "Europe", "Netherlands": "Europe",
              "Spain": "Europe", "Belgium": "Europe", "Switzerland": "Europe", "Portugal": "Europe", "Italy": "Europe",
              "Norway": "Europe", "Sweden": "Europe", "Finland": "Europe", "Austria": "Europe", "Denmark": "Europe",
              "Channel Islands": "Europe", "Poland": "Europe", "Cyprus": "Europe", "Greece": "Europe", "Iceland": "Europe",
              "Malta": "Europe", "Lithuania": "Europe", "Czech Republic": "Europe", "Channel Islands ": "Europe", "European Community": "Europe",
              "Australia": "Asia-Pacific", "Japan": "Asia-Pacific", "Singapore": "Asia-Pacific", "Hong Kong": "Asia-Pacific",
              "USA": "Americas", "Canada": "Americas", "Brazil": "Americas"}
cust["region"] = cust.country.map(region_map).fillna("Other")

dates = pd.DataFrame({"date": pd.date_range(sales.InvoiceDate.min().normalize(), sales.InvoiceDate.max().normalize())})
dates["date_key"] = dates.date.dt.strftime("%Y%m%d").astype(int)
dates["year"] = dates.date.dt.year; dates["month"] = dates.date.dt.month
dates["month_name"] = dates.date.dt.strftime("%b"); dates["month_label"] = dates.date.dt.strftime("%Y-%m")
dates["quarter"] = dates.date.dt.quarter; dates["weekday"] = dates.date.dt.strftime("%a")
dates["month_index"] = dates.year * 12 + dates.month                      # portable month arithmetic
dates["day_num"] = (dates.date - pd.Timestamp("2010-01-01")).dt.days       # portable day arithmetic
dates["date"] = dates.date.dt.strftime("%Y-%m-%d")

# ---------- Fact ----------
f = sales.merge(prod, on="StockCode", suffixes=("", "_p")).merge(
    cust[["customer_key", "CustomerID"]], on="CustomerID", how="left")
f["date_key"] = f.InvoiceDate.dt.strftime("%Y%m%d").astype(int)
fact = f[["InvoiceNo", "date_key", "customer_key", "product_key", "Quantity", "UnitPrice", "Revenue"]].copy()
fact.columns = ["invoice_no", "date_key", "customer_key", "product_key", "quantity", "unit_price", "revenue"]
fact["customer_key"] = fact.customer_key.astype("Int64")
fact.insert(0, "sales_key", range(1, len(fact) + 1))
cust = cust.rename(columns={"CustomerID": "customer_id"}); prod = prod.rename(columns={"StockCode": "stock_code", "Description": "description"})

# ---------- Load ----------
db = ROOT / "data" / "ecommerce.db"
db.unlink(missing_ok=True)
con = sqlite3.connect(db)
for name, d in [("dim_customer", cust), ("dim_product", prod), ("dim_date", dates), ("fact_sales", fact)]:
    d.to_sql(name, con, index=False)
rt = returns.rename(columns={"InvoiceNo": "invoice_no", "StockCode": "stock_code", "Quantity": "quantity", "Revenue": "revenue"})
rt[["invoice_no", "stock_code", "quantity", "revenue"]].to_sql("fact_returns", con, index=False)
con.execute("CREATE INDEX ix_fact_cust ON fact_sales(customer_key)")
con.execute("CREATE INDEX ix_fact_date ON fact_sales(date_key)")
con.execute("CREATE INDEX ix_fact_prod ON fact_sales(product_key)")
con.commit()
for t in ["dim_customer", "dim_product", "dim_date", "fact_sales", "fact_returns"]:
    log[f"table_{t}"] = con.execute(f"select count(*) from {t}").fetchone()[0]
pd.Series(log).to_csv(ROOT / "outputs" / "cleaning_log.csv", header=["value"])
print(pd.Series(log).to_string())
