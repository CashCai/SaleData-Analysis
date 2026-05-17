"""
销售排行模块 — 按品类/品牌/型号查看 Top N
"""

import pandas as pd
import streamlit as st
import plotly.express as px
from config import PLOTLY_CONFIG


def generate_ranking(df: pd.DataFrame, group_by: str = "brand",
                     sort_by: str = "amount", top_n: int = 20) -> pd.DataFrame:
    """
    生成销售排行
    group_by: 'category' / 'brand' / 'model'
    sort_by: 'amount'（销售额）/ 'quantity'（销量）
    """
    if group_by not in df.columns:
        return pd.DataFrame()

    agg_dict = {"amount": "sum"}
    if "quantity" in df.columns:
        agg_dict["quantity"] = "sum"

    # 先取最大的 N 个，保持降序排序（热销在前，用于表格显示）
    ranking = df.groupby(group_by).agg(agg_dict).sort_values(sort_by, ascending=False)
    ranking = ranking.head(top_n).reset_index()

    col_map = {group_by: "维度", "amount": "销售额", "quantity": "销量"}
    ranking = ranking.rename(columns=col_map)

    # 占比按排序指标计算
    metric_col = "销售额" if sort_by == "amount" else "销量"
    total_all = ranking[metric_col].sum()
    ranking["占比显示"] = (ranking[metric_col] / total_all * 100).round(1).apply(lambda x: f"{x}%")
    ranking["排名"] = range(1, len(ranking) + 1)

    # 热销标记（前 10%）
    top10_pct = max(1, int(len(ranking) * 0.1))
    ranking["热销标记"] = ranking["排名"].apply(lambda x: "🔥" if x <= top10_pct else "")

    return ranking


def render_ranking_ui(df: pd.DataFrame):
    """排行页面 UI"""
    st.subheader("销售排行")

    col1, col2, col3 = st.columns(3)
    with col1:
        group_by = st.selectbox(
            "排行维度",
            ["category", "brand", "model"],
            format_func=lambda x: {"category": "品类", "brand": "品牌", "model": "型号"}.get(x, x),
        )
    with col2:
        sort_by = st.selectbox(
            "排序依据",
            ["amount", "quantity"],
            format_func=lambda x: "销售额" if x == "amount" else "销售量",
        )
    with col3:
        top_n = st.slider("显示数量", 5, 50, 20)

    ranking = generate_ranking(df, group_by, sort_by, top_n)

    if ranking.empty:
        st.info(f"数据中不含「{group_by}」字段，无法生成排行")
        return

    # 横向柱状图
    x_col = "销售额" if sort_by == "amount" else "销量"
    dim_label = {"category": "品类", "brand": "品牌", "model": "型号"}.get(group_by, group_by)

    # 图表数据按升序排列，使最大的显示在最下面
    chart_data = ranking.sort_values(x_col, ascending=True)

    fig = px.bar(
        chart_data,
        x=x_col,
        y="维度",
        orientation="h",
        text="占比显示",
        title=f"{dim_label} 销售排行 Top {top_n}",
        custom_data=["排名", "销售额", "销量", "热销标记"],
    )

    fig.update_traces(
        textposition="outside",
        marker_color="#1f77b4",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "排名: #%{customdata[0]}<br>"
            "销售额: ¥%{customdata[1]:,.0f}<br>"
            "销量: %{customdata[2]} 台<br>"
            "%{customdata[3]}"
            "<extra></extra>"
        ),
    )
    fig.update_layout(
        yaxis={"categoryorder": "array", "categoryarray": chart_data["维度"].tolist()},
        xaxis_title=x_col,
        height=500,
        margin=dict(l=10, r=40, t=40, b=10),
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=f"rank_chart_{group_by}_{sort_by}_{top_n}")

    st.dataframe(
        ranking[["排名", "维度", "销售额", "销量", "占比显示", "热销标记"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "销售额": st.column_config.NumberColumn(format="¥%.2f"),
        },
    )
