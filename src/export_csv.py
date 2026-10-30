"""Optional: export star-schema tables to CSV for loading into MySQL / Power BI."""
import sqlite3
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent; out = ROOT / "data" / "export"; out.mkdir(exist_ok=True)
con = sqlite3.connect(ROOT / "data" / "ecommerce.db")
for t in ["dim_customer", "dim_product", "dim_date", "fact_sales", "fact_returns"]:
    pd.read_sql(f"select * from {t}", con).to_csv(out / f"{t}.csv", index=False)
print("exported to", out)
