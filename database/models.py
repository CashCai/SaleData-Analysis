"""
数据表定义 — SQLite 建表语句
"""

CREATE_SALES_ORDERS = """
CREATE TABLE IF NOT EXISTS sales_orders (
    order_id        TEXT PRIMARY KEY,
    customer_name   TEXT,
    customer_phone  TEXT,
    product_name    TEXT,
    category        TEXT,
    brand           TEXT,
    model           TEXT,
    quantity        INTEGER DEFAULT 1,
    amount          REAL,
    subsidy_amount  REAL DEFAULT 0,
    subsidy_status  TEXT DEFAULT '未核销',
    sale_date       DATE,
    channel         TEXT,
    address         TEXT,
    geo_code        TEXT
);
"""

CREATE_CUSTOMERS = """
CREATE TABLE IF NOT EXISTS customers (
    customer_phone     TEXT PRIMARY KEY,
    customer_name      TEXT,
    first_purchase     DATE,
    last_purchase      DATE,
    purchase_count     INTEGER DEFAULT 1,
    total_amount       REAL,
    avg_purchase_cycle INTEGER,
    rfm_score          TEXT
);
"""

CREATE_PRODUCTS = """
CREATE TABLE IF NOT EXISTS products (
    product_id      TEXT PRIMARY KEY,
    product_name    TEXT,
    category        TEXT,
    brand           TEXT,
    model           TEXT,
    sale_price      REAL,
    total_sales     INTEGER DEFAULT 0,
    total_revenue   REAL DEFAULT 0
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sale_date ON sales_orders(sale_date);",
    "CREATE INDEX IF NOT EXISTS idx_category ON sales_orders(category);",
    "CREATE INDEX IF NOT EXISTS idx_brand ON sales_orders(brand);",
    "CREATE INDEX IF NOT EXISTS idx_customer_phone ON sales_orders(customer_phone);",
    "CREATE INDEX IF NOT EXISTS idx_subsidy_status ON sales_orders(subsidy_status);",
    "CREATE INDEX IF NOT EXISTS idx_purchase_count ON customers(purchase_count);",
    "CREATE INDEX IF NOT EXISTS idx_product_category ON products(category);",
    "CREATE INDEX IF NOT EXISTS idx_product_brand ON products(brand);",
]

ALL_TABLES = [CREATE_SALES_ORDERS, CREATE_CUSTOMERS, CREATE_PRODUCTS]
