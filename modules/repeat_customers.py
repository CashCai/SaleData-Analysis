"""
回购顾客分析模块 — RFM 分层
"""

import pandas as pd
import streamlit as st
import plotly.express as px


def analyze_repeat_customers(df: pd.DataFrame) -> pd.DataFrame:
    """回购客户分析"""
    if "customer_phone" not in df.columns or "sale_date" not in df.columns:
        return pd.DataFrame()

    customer_stats = df.groupby("customer_phone").agg(
        购买次数=("order_id", "count"),
        累计消费=("amount", "sum"),
        最早购买=("sale_date", "min"),
        最近购买=("sale_date", "max"),
    ).reset_index()

    repeat = customer_stats[customer_stats["购买次数"] >= 2].copy()

    if repeat.empty:
        return repeat

    time_span = (repeat["最近购买"] - repeat["最早购买"]).dt.days
    repeat["回购周期(天)"] = (time_span / (repeat["购买次数"] - 1)).round(1)

    today = pd.Timestamp.now()
    repeat["R_天数"] = (today - repeat["最近购买"]).dt.days

    def rfm_label(row):
        if row["R_天数"] <= 90 and row["购买次数"] >= 3 and row["累计消费"] >= 10000:
            return "高价值客户"
        elif row["累计消费"] >= 10000:
            return "重要保持"
        elif row["R_天数"] <= 90 and row["累计消费"] >= 5000:
            return "重要发展"
        return "一般客户"

    repeat["RFM分层"] = repeat.apply(rfm_label, axis=1)
    repeat = repeat.sort_values("累计消费", ascending=False)

    return repeat


def render_repeat_customers_ui(df: pd.DataFrame):
    """回购分析页面"""
    st.subheader("回购顾客分析")

    result = analyze_repeat_customers(df)

    if "customer_phone" not in df.columns:
        st.info("数据中不含客户电话字段，无法分析回购客户")
        return

    total_customers = df["customer_phone"].nunique()
    repeat_count = len(result)
    repeat_rate = repeat_count / total_customers if total_customers > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("总客户数", str(total_customers))
    col2.metric("回购客户数", str(repeat_count))
    col3.metric("回购率", f"{repeat_rate:.1%}")

    if result.empty:
        st.info("当前筛选条件下没有回购客户（购买次数 ≥ 2）")
        return

    # RFM 分层饼图
    rfm_order = ["高价值客户", "重要保持", "重要发展", "一般客户"]
    result["RFM分层"] = pd.Categorical(result["RFM分层"], categories=rfm_order, ordered=True)

    fig_pie = px.pie(
        result,
        names="RFM分层",
        title="RFM 客户分层分布",
        color="RFM分层",
        color_discrete_map={
            "高价值客户": "#2ecc71",
            "重要保持": "#3498db",
            "重要发展": "#f39c12",
            "一般客户": "#95a5a6",
        },
        category_orders={"RFM分层": rfm_order},
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig_pie, use_container_width=True)

    # 客户列表
    st.write("**回购客户明细：**")
    display_cols = ["customer_phone", "购买次数", "累计消费", "回购周期(天)", "RFM分层"]
    st.dataframe(
        result[display_cols],
        use_container_width=True,
        column_config={
            "累计消费": st.column_config.NumberColumn(format="¥%.2f"),
        },
        hide_index=True,
    )
