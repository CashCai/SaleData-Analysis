"""
数据导入模块 — Excel 上传、清洗、入库
"""

import pandas as pd
import streamlit as st
from utils.data_cleaner import normalize_columns, clean_data, validate_data
from database.db_manager import backup_database, get_connection


SALES_ORDERS_COLUMNS = [
    "order_id", "customer_name", "customer_phone", "product_name",
    "category", "brand", "model", "quantity", "amount", "subsidy_amount",
    "subsidy_status", "sale_date", "channel", "address", "geo_code",
]


def import_to_db(df: pd.DataFrame):
    """将清洗后的数据写入 SQLite（替换全部数据）"""
    backup_database()
    conn = get_connection()

    # 确保 DataFrame 包含所有标准列，避免 to_sql 破坏表结构
    for col in SALES_ORDERS_COLUMNS:
        if col not in df.columns:
            df[col] = None

    # 只保留标准列，移除导入数据中多余的列
    df = df[[c for c in SALES_ORDERS_COLUMNS if c in df.columns]]

    df.to_sql("sales_orders", conn, if_exists="replace", index=False)

    # 更新客户汇总表
    _update_customers_table(df, conn)
    # 更新商品信息表
    _update_products_table(df, conn)

    conn.commit()
    conn.close()


def _update_customers_table(df: pd.DataFrame, conn):
    """更新客户汇总表"""
    if "customer_phone" not in df.columns:
        return

    customer_stats = df.groupby("customer_phone").agg(
        customer_name=("customer_name", "first"),
        first_purchase=("sale_date", "min"),
        last_purchase=("sale_date", "max"),
        purchase_count=("order_id", "count"),
        total_amount=("amount", "sum"),
    ).reset_index()

    for _, row in customer_stats.iterrows():
        phone = row["customer_phone"]
        if pd.isna(phone):
            continue

        span = (row["last_purchase"] - row["first_purchase"]).days
        cycle = round(span / (row["purchase_count"] - 1), 1) if row["purchase_count"] > 1 else None

        conn.execute(
            """INSERT OR REPLACE INTO customers
               (customer_phone, customer_name, first_purchase, last_purchase,
                purchase_count, total_amount, avg_purchase_cycle)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (phone, row["customer_name"], row["first_purchase"].date() if pd.notna(row["first_purchase"]) else None,
             row["last_purchase"].date() if pd.notna(row["last_purchase"]) else None,
             int(row["purchase_count"]), float(row["total_amount"]), cycle),
        )


def _update_products_table(df: pd.DataFrame, conn):
    """更新商品信息表"""
    if "product_name" not in df.columns:
        return

    product_stats = df.groupby("product_name").agg(
        category=("category", "first"),
        brand=("brand", "first"),
        model=("model", "first"),
        total_sales=("quantity", "sum"),
        total_revenue=("amount", "sum"),
    ).reset_index()

    for _, row in product_stats.iterrows():
        product_id = row["product_name"]
        conn.execute(
            """INSERT OR REPLACE INTO products
               (product_id, product_name, category, brand, model, total_sales, total_revenue)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (product_id, row["product_name"], row["category"], row["brand"],
             row["model"], int(row["total_sales"]), float(row["total_revenue"])),
        )


def run_import_ui():
    """Streamlit 导入界面"""
    st.subheader("数据导入")

    uploaded_file = st.file_uploader(
        "拖拽 Excel 文件到这里，或点击浏览",
        type=["xlsx", "xls"],
        help="支持 .xlsx 和 .xls 格式",
    )

    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            st.info(f"已读取 {len(df)} 行数据，{len(df.columns)} 个字段")

            df = normalize_columns(df)
            df = clean_data(df)

            warnings = validate_data(df)
            for w in warnings:
                st.warning(w)

            import_to_db(df)
            st.success(f"导入成功！共 {len(df)} 条记录")

            st.write("**数据预览（前 5 行）：**")
            st.dataframe(df.head(5))

            col1, col2, col3 = st.columns(3)
            col1.metric("总行数", len(df))
            col2.metric("日期范围",
                        f"{df['sale_date'].min().date()} ~ {df['sale_date'].max().date()}"
                        if "sale_date" in df.columns else "-")
            col3.metric("品类数",
                        df["category"].nunique() if "category" in df.columns else "-")

        except Exception as e:
            st.error(f"导入失败：{str(e)}")
