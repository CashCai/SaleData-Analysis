"""
国补核销预警模块 — 跟踪补贴核销状态
"""

import pandas as pd
import streamlit as st
from config import SUBSIDY_DEADLINE_DAYS


def check_subsidy_alerts(df: pd.DataFrame, deadline_days: int = SUBSIDY_DEADLINE_DAYS) -> pd.DataFrame:
    """检查国补核销状态，返回带预警标记的数据"""
    if "subsidy_amount" not in df.columns:
        return pd.DataFrame()

    alert_df = df[df["subsidy_amount"] > 0].copy()

    if alert_df.empty:
        return alert_df

    today = pd.Timestamp.now().normalize()
    alert_df["核销截止日"] = alert_df["sale_date"] + pd.Timedelta(days=deadline_days)
    alert_df["剩余天数"] = (alert_df["核销截止日"] - today).dt.days

    def alert_level(days, status):
        if status == "已核销":
            return "已核销"
        if days < 0:
            return "已逾期"
        if days <= 7:
            return "即将到期"
        return "待核销"

    alert_df["预警状态"] = alert_df.apply(
        lambda r: alert_level(r["剩余天数"], r.get("subsidy_status", "未核销")), axis=1
    )

    return alert_df.sort_values("剩余天数")


def render_subsidy_alert_ui(df: pd.DataFrame):
    """国补预警页面"""
    st.subheader("国补核销预警")

    deadline_days = st.sidebar.number_input(
        "核销期限（天）", min_value=7, max_value=90, value=SUBSIDY_DEADLINE_DAYS,
    )

    alert_df = check_subsidy_alerts(df, deadline_days)

    if alert_df.empty:
        if "subsidy_amount" not in df.columns:
            st.info("数据中不含国补金额字段，无法分析补贴核销情况")
        else:
            st.info("当前数据中没有享受国补的订单")
        return

    total_subsidy = alert_df["subsidy_amount"].sum()
    overdue = alert_df[alert_df["预警状态"] == "已逾期"]
    urgent = alert_df[alert_df["预警状态"] == "即将到期"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("国补订单总数", f"{len(alert_df)}")
    col2.metric("补贴总金额", f"¥{total_subsidy:,.0f}")
    col3.metric("已逾期", f"{len(overdue)} 单",
                delta=f"¥{overdue['subsidy_amount'].sum():,.0f}" if not overdue.empty else None,
                delta_color="inverse")
    col4.metric("即将到期", f"{len(urgent)} 单",
                delta=f"¥{urgent['subsidy_amount'].sum():,.0f}" if not urgent.empty else None)

    # 预警明细
    st.write("**预警明细：**")
    display_cols = ["order_id", "customer_name", "product_name", "amount",
                    "subsidy_amount", "sale_date", "核销截止日", "剩余天数", "预警状态"]

    available_cols = [c for c in display_cols if c in alert_df.columns]

    def color_status(val):
        colors = {"已逾期": "color: red; font-weight: bold",
                  "即将到期": "color: #f39c12; font-weight: bold",
                  "已核销": "color: green",
                  "待核销": "color: gray"}
        return colors.get(val, "")

    styled = alert_df[available_cols].style.map(color_status, subset=["预警状态"])

    st.dataframe(
        styled,
        use_container_width=True,
        column_config={
            "amount": st.column_config.NumberColumn("销售金额", format="¥%.2f"),
            "subsidy_amount": st.column_config.NumberColumn("补贴金额", format="¥%.2f"),
            "sale_date": st.column_config.DateColumn("销售日期"),
            "核销截止日": st.column_config.DateColumn("核销截止日"),
            "剩余天数": st.column_config.NumberColumn("剩余天数"),
        },
    )
