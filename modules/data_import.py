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
    "latitude", "longitude",
]


def _geocode_addresses(df: pd.DataFrame) -> pd.DataFrame:
    """将地址批量解析为经纬度"""
    if "address" not in df.columns:
        return df

    from utils.geo_coder import geocode
    from config import AMAP_API_KEY

    if not AMAP_API_KEY:
        return df

    # 默认地区前缀（云梦本地数据，短地址补全省市县）
    DEFAULT_REGION = "湖北省孝感市云梦县"

    def _normalize_addr(addr: str) -> str:
        """如果地址缺少行政区域前缀，补全省市县"""
        if pd.isna(addr):
            return addr
        addr = str(addr).strip()
        # 只检查开头是否已有省/市/县级前缀，避免"镇""区"等中间关键词误判
        if not any(kw in addr[:4] for kw in ("省", "市", "县")):
            return f"{DEFAULT_REGION}{addr}"
        return addr

    # 补全省市县地址后再进行地理编码
    unique_addrs = df["address"].dropna().unique()
    if len(unique_addrs) == 0:
        return df

    coords = {}
    progress = st.status(f"正在地理编码 {len(unique_addrs)} 个地址...")
    for i, addr in enumerate(unique_addrs):
        full_addr = _normalize_addr(addr)
        result = geocode(full_addr)
        if result:
            coords[addr] = (result["lat"], result["lng"])
        if (i + 1) % 10 == 0:
            progress.write(f"已处理 {i + 1}/{len(unique_addrs)}")

    progress.write(f"完成，共解析 {len(coords)}/{len(unique_addrs)} 个地址")
    progress.update(state="complete")

    if coords:
        df["latitude"] = df["address"].map(lambda a: coords.get(a, (None, None))[0] if pd.notna(a) else None)
        df["longitude"] = df["address"].map(lambda a: coords.get(a, (None, None))[1] if pd.notna(a) else None)
        # 将短地址更新为完整地址（含省市区前缀）
        df["address"] = df["address"].apply(_normalize_addr)

    return df


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


def _ffill_merged_cells(df: pd.DataFrame, uploaded_file) -> pd.DataFrame:
    """探测 Excel 中纵向合并的单元格，forward-fill 填充空值"""
    try:
        import openpyxl
        # 兼容文件对象（Streamlit）和路径字符串
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
        wb = openpyxl.load_workbook(uploaded_file)
        ws = wb.active

        header = [cell.value for cell in ws[1]]

        # 找到应付总额、商品单价、数量的列索引
        amount_col = price_col = qty_col = None
        for i, h in enumerate(header):
            if h:
                h_str = str(h).replace('（', '(').replace('）', ')')
                if '应付总额' in h_str:
                    amount_col = i
                elif '商品售价' in h_str or '商品单价' in h_str:
                    price_col = i
                elif '数量' in h_str or '销量' in h_str:
                    qty_col = i

        # 记录应付总额列中因合并而 NaN 的行
        merged_amount_rows = set()

        for mr in ws.merged_cells.ranges:
            if mr.min_col == mr.max_col and mr.min_row > 1 and mr.min_row < mr.max_row:
                col_idx = mr.min_col - 1
                if col_idx >= len(df.columns):
                    continue

                # 记录应付总额列中的合并行（全部行都用单价替换）
                if amount_col is not None and col_idx == amount_col:
                    for r in range(mr.min_row - 2, mr.max_row - 1):
                        merged_amount_rows.add(r)

                # 前向填充所有合并列
                for row_idx in range(mr.min_row - 1, mr.max_row - 1):
                    if pd.isna(df.iloc[row_idx, col_idx]):
                        df.iloc[row_idx, col_idx] = df.iloc[row_idx - 1, col_idx]

        # 应付总额列中原本合并的行，用商品售价 × 数量计算实际金额
        if amount_col is not None and price_col is not None:
            for row_idx in merged_amount_rows:
                price_val = df.iloc[row_idx, price_col]
                qty_val = df.iloc[row_idx, qty_col] if qty_col is not None else None
                if pd.notna(price_val):
                    if qty_val is not None and pd.notna(qty_val):
                        try:
                            qty_val = float(qty_val)
                        except (ValueError, TypeError):
                            qty_val = 1
                    else:
                        qty_val = 1
                    df.iloc[row_idx, amount_col] = price_val * qty_val

    except Exception:
        pass  # 探测失败不影响正常导入
    return df


def run_import_ui():
    """Streamlit 导入界面"""
    st.subheader("数据导入")

    st.markdown("""
    **操作指引：**
    1. **上传文件** — 点击下方按钮选择 Excel 文件（.xlsx / .xls）
    2. **确认数据** — 检查导入后的数据预览是否完整、正确
    3. **进入看板** — 确认无误后，点击底部「进入销售看板」开始分析
    """)

    uploaded_file = st.file_uploader(
        "选择 Excel 文件（.xlsx / .xls）",
        type=["xlsx", "xls"],
        help="支持 .xlsx 和 .xls 格式",
    )

    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            st.info(f"已读取 {len(df)} 行数据，{len(df.columns)} 个字段")

            # 处理合并单元格（纵向合并的单元格 forward-fill）
            df = _ffill_merged_cells(df, uploaded_file)

            df = normalize_columns(df)
            df = clean_data(df)

            # 如果高德 API Key 已配置，自动从地址解析经纬度
            df = _geocode_addresses(df)

            warnings = validate_data(df)
            for w in warnings:
                st.warning(w)

            import_to_db(df)

            # 立即刷新 session state 数据，确保图表使用最新的导入数据
            from database.db_manager import read_all_orders
            rows = read_all_orders()
            if rows:
                df_loaded = pd.DataFrame(rows)
                df_loaded["sale_date"] = pd.to_datetime(df_loaded["sale_date"], errors="coerce")
                st.session_state.df = df_loaded
                st.session_state.data_loaded = True

            st.success(f"导入成功！共 {len(df)} 条记录")

            with st.expander("数据预览（前 5 行）", expanded=True):
                from modules.data_viewer import DISPLAY_COLUMNS, CN_COLUMN_MAP
                avail = [c for c in DISPLAY_COLUMNS if c in df.columns]
                preview = df[avail].head(5).rename(columns=CN_COLUMN_MAP)
                st.dataframe(
                    preview,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "应付总额": st.column_config.NumberColumn(format="¥%.2f"),
                        "国补金额": st.column_config.NumberColumn(format="¥%.2f"),
                        "签单日期": st.column_config.DateColumn(format="YYYY-MM-DD"),
                    },
                )

            col1, col2, col3 = st.columns(3)
            col1.metric("总行数", len(df))
            col2.metric("日期范围",
                        f"{df['sale_date'].min().date()} ~ {df['sale_date'].max().date()}"
                        if "sale_date" in df.columns else "-")
            col3.metric("品类数",
                        df["category"].nunique() if "category" in df.columns else "-")


        except Exception as e:
            st.error(f"导入失败：{str(e)}")
