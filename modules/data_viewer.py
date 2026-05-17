"""
数据查看模块 — 分页浏览、全文搜索、中文列名
"""

import pandas as pd
import streamlit as st

# 英文 → 中文列名映射
CN_COLUMN_MAP: dict[str, str] = {
    "order_id": "订单编号",
    "customer_name": "客户姓名",
    "customer_phone": "客户电话",
    "product_name": "商品名称",
    "category": "品类",
    "brand": "品牌",
    "model": "型号",
    "quantity": "数量",
    "amount": "应付总额",
    "subsidy_amount": "国补金额",
    "subsidy_status": "是否核销国补卷",
    "sale_date": "签单日期",
    "channel": "渠道",
    "address": "地址",
    "geo_code": "经纬度",
}

# 展示列顺序（优先展示重要字段）
DISPLAY_COLUMNS: list[str] = [
    "sale_date", "order_id", "customer_name", "customer_phone",
    "product_name", "category", "brand", "model", "quantity",
    "amount", "subsidy_amount", "subsidy_status", "channel", "address",
]


def render_data_viewer(df: pd.DataFrame):
    """分页、可搜索的数据表格查看器，所有列名以中文显示"""
    st.subheader("数据查看 — 销售订单明细")

    # 搜索栏
    search = st.text_input(
        "搜索", placeholder="输入关键字搜索（支持任意字段）...",
        label_visibility="collapsed",
    )

    filtered = df.copy()
    if search:
        mask = filtered.astype(str).apply(
            lambda x: x.str.contains(search, case=False, na=False)
        ).any(axis=1)
        filtered = filtered[mask]

    total = len(filtered)
    if total == 0:
        st.info("无匹配数据")
        return

    # 分页设置
    col_page_size, col_page_num, col_info = st.columns([1, 2, 1])
    with col_page_size:
        page_size = st.selectbox("每页行数", [50, 100, 200], index=1)
    total_pages = max(1, (total + page_size - 1) // page_size)
    with col_page_num:
        page = st.number_input("页码", min_value=1, max_value=total_pages, value=1)
    with col_info:
        st.caption(f"共 {total} 条记录")

    start = (page - 1) * page_size
    end = start + page_size

    # 选取存在的列、应用中文列名
    available_cols = [c for c in DISPLAY_COLUMNS if c in filtered.columns]
    display_df = (
        filtered[available_cols]
        .iloc[start:end]
        .rename(columns=CN_COLUMN_MAP)
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "应付总额": st.column_config.NumberColumn(format="¥%.2f"),
            "国补金额": st.column_config.NumberColumn(format="¥%.2f"),
            "签单日期": st.column_config.DateColumn(format="YYYY-MM-DD"),
        },
    )

    st.caption(f"第 {page}/{total_pages} 页，显示 {start+1}–{min(end, total)} 条")
