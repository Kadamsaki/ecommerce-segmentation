-- MySQL 8 version of the star schema (the project was built and verified on SQLite; same table/column names).
CREATE DATABASE IF NOT EXISTS ecommerce; USE ecommerce;
CREATE TABLE dim_customer (customer_key INT PRIMARY KEY, customer_id INT NOT NULL, country VARCHAR(50), region VARCHAR(20));
CREATE TABLE dim_product  (product_key INT PRIMARY KEY, stock_code VARCHAR(20) NOT NULL, description VARCHAR(255));
CREATE TABLE dim_date (date_key INT PRIMARY KEY, `date` DATE, `year` INT, `month` INT, month_name VARCHAR(3), month_label CHAR(7),
                       quarter INT, weekday VARCHAR(3), month_index INT, day_num INT);
CREATE TABLE fact_sales (sales_key INT PRIMARY KEY, invoice_no VARCHAR(12), date_key INT, customer_key INT NULL, product_key INT,
                         quantity INT, unit_price DECIMAL(10,2), revenue DECIMAL(12,2),
                         FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
                         FOREIGN KEY (customer_key) REFERENCES dim_customer(customer_key),
                         FOREIGN KEY (product_key) REFERENCES dim_product(product_key));
CREATE TABLE fact_returns (invoice_no VARCHAR(12), stock_code VARCHAR(20), quantity INT, revenue DECIMAL(12,2));
CREATE INDEX ix_fact_cust ON fact_sales(customer_key); CREATE INDEX ix_fact_date ON fact_sales(date_key); CREATE INDEX ix_fact_prod ON fact_sales(product_key);
-- Load: export each SQLite table to CSV (python src/export_csv.py) then:
-- LOAD DATA LOCAL INFILE 'data/export/dim_customer.csv' INTO TABLE dim_customer FIELDS TERMINATED BY ',' ENCLOSED BY '"' IGNORE 1 LINES;
-- (repeat for each table; for fact_sales use NULLIF handling or load the empty customer_key as NULL)
