"""
销售热力图模块 — 地理分布展示
使用 Plotly 中国地图（需要联网加载底图资源）
"""

import pandas as pd
import streamlit as st
import plotly.express as px


def create_heatmap(df: pd.DataFrame, geo_level: str = "province",
                   metric: str = "amount"):
    """
    创建销售热力图
    geo_level: 'province' / 'city' / 'district'
    metric: 'amount'/'quantity'
    """
    if geo_level not in df.columns:
        return None

    value_col = "销售额" if metric == "amount" else "销售量"
    agg_col = "amount" if metric == "amount" else ("quantity" if "quantity" in df.columns else "order_id")

    geo_data = df.groupby(geo_level).agg(
        **{value_col: (agg_col, "sum")}
    ).reset_index()

    fig = px.choropleth(
        geo_data,
        locations=geo_level,
        locationmode="country names",
        color=value_col,
        hover_name=geo_level,
        hover_data={value_col: ":,.0f", geo_level: False},
        color_continuous_scale="OrRd",
        title=f"{value_col} 地理分布",
        labels={value_col: value_col},
    )

    fig.update_geos(
        visible=False,
        projection_type="natural earth",
        showcountries=True,
        countrycolor="rgba(200,200,200,0.5)",
        fitbounds="locations",
        lonaxis_range=[73, 135],
        lataxis_range=[18, 53],
    )

    fig.update_layout(
        height=600,
        margin=dict(l=10, r=10, t=40, b=10),
        coloraxis_colorbar=dict(
            title=value_col,
            len=0.6,
        ),
    )

    return fig


def render_heatmap_ui(df: pd.DataFrame):
    """热力图页面"""
    st.subheader("销售热力图")

    geo_options = [c for c in ["province", "city", "district"] if c in df.columns]

    if not geo_options:
        st.info("数据中不含地址层级字段（province/city/district），无法生成热力图。"
                "请在 Excel 中添加省/市/区字段。")
        return

    col1, col2 = st.columns(2)
    with col1:
        geo_level = st.selectbox(
            "地理层级",
            options=geo_options,
            format_func=lambda x: {"province": "省", "city": "市", "district": "县/区"}.get(x, x),
        )
    with col2:
        metric = st.selectbox(
            "指标",
            options=["amount", "quantity"],
            format_func=lambda x: "销售额" if x == "amount" else "销售量",
        )

    fig = create_heatmap(df, geo_level, metric)
    if fig:
        st.plotly_chart(fig, use_container_width=True)

        # 显示聚合数据表
        agg_col = "amount" if metric == "amount" else ("quantity" if "quantity" in df.columns else "order_id")
        value_label = "销售额" if metric == "amount" else "销售量"
        summary = df.groupby(geo_level).agg(
            **{value_label: (agg_col, "sum"), "订单数": ("order_id", "count")}
        ).reset_index().sort_values(value_label, ascending=False)

        st.write(f"**{['省', '市', '县/区'][geo_options.index(geo_level)]}级销售数据：**")
        st.dataframe(summary, use_container_width=True, hide_index=True)
