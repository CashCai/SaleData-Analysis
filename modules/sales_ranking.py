"""
销售排行模块 — 按品类/品牌/型号查看 Top N
"""

import pandas as pd
import streamlit as st
import plotly.express as px


def generate_ranking(df: pd.DataFrame, group_by: str = "brand",
                     sort_by: str = "amount", top_n: int = 20) -> pd.DataFrame:
    """
    生成销售排行
    group_by: 'category' / 'brand' / 'model'
    sort_by: 'amount'（销售额）/ 'quantity'（销量）
    """
    if group_by not in df.columns:
        return pd.DataFrame()

    agg_dict = {"amount": "sum", "order_id": "count"}
    if "quantity" in df.columns:
        agg_dict["quantity"] = "sum"

    ranking = df.groupby(group_by).agg(agg_dict).sort_values(sort_by, ascending=False)
    ranking = ranking.head(top_n).reset_index()

    col_map = {group_by: "维度", "amount": "销售额", "order_id": "订单数", "quantity": "销量"}
    ranking = ranking.rename(columns=col_map)
    ranking["销售额占比"] = (ranking["销售额"] / ranking["销售额"].sum() * 100).round(1)
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
    fig = px.bar(
        ranking,
        x="销售额",
        y="维度",
        orientation="h",
        text="销售额占比",
        color="销售额",
        color_continuous_scale="Blues",
        title=f"{['品类', '品牌', '型号'][['category', 'brand', 'model'].index(group_by)]} 销售排行 Top {top_n}",
        custom_data=["排名", "订单数", "销量", "热销标记"],
    )

    fig.update_traces(
        texttemplate="%{text}%",
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "销售额: ¥%{x:,.0f}<br>"
            "排名: #%{customdata[0]}<br>"
            "订单数: %{customdata[1]}<br>"
            "销量: %{customdata[2]}<br>"
            "%{customdata[3]}"
        ),
    )
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        height=500,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        ranking[["排名", "维度", "销售额", "订单数", "销量", "销售额占比", "热销标记"]],
        use_container_width=True,
        hide_index=True,
    )
