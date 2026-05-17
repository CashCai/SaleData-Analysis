"""
家电销售数据可视化看板 — 主程序入口
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

from config import APP_TITLE, APP_ICON, PLOTLY_CONFIG, FILTER_OVERRIDES_PATH
from database.db_manager import init_database, read_all_orders, delete_orders_by_field
from modules.data_import import run_import_ui, import_to_db, normalize_columns, clean_data, validate_data
from modules.sales_ranking import render_ranking_ui
from modules.repeat_customers import render_repeat_customers_ui
from modules.subsidy_alert import render_subsidy_alert_ui
from modules.sales_heatmap import render_heatmap_ui
from modules.data_export import render_export_button
from modules.data_viewer import render_data_viewer

# ─── 页面配置 ─────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 样式 ─────────────────────────────────────────────────────────
with open("assets/style.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ─── 初始化 ───────────────────────────────────────────────────────
def init_session_state():
    """初始化 session state"""
    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = False
    if "page" not in st.session_state:
        st.session_state.page = "综合看板"
    if "show_import" not in st.session_state:
        st.session_state.show_import = False


def load_filter_overrides():
    """从 JSON 文件加载自定义品类/品牌到 session state"""
    if os.path.exists(FILTER_OVERRIDES_PATH):
        try:
            with open(FILTER_OVERRIDES_PATH, encoding="utf-8") as f:
                data = json.load(f)
            st.session_state.custom_categories = data.get("custom_categories", [])
            st.session_state.custom_brands = data.get("custom_brands", [])
        except Exception:
            st.session_state.custom_categories = []
            st.session_state.custom_brands = []
    else:
        st.session_state.custom_categories = []
        st.session_state.custom_brands = []


def save_filter_overrides():
    """将 session state 中的自定义品类/品牌写入 JSON 文件"""
    data = {
        "custom_categories": st.session_state.get("custom_categories", []),
        "custom_brands": st.session_state.get("custom_brands", []),
    }
    os.makedirs(os.path.dirname(FILTER_OVERRIDES_PATH), exist_ok=True)
    with open(FILTER_OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_data_from_db():
    """从数据库加载数据到 session state"""
    rows = read_all_orders()
    if rows:
        df = pd.DataFrame(rows)
        df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
        # 确保amount列是数值类型
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        st.session_state.df = df
        st.session_state.data_loaded = True
    else:
        st.session_state.data_loaded = False


init_session_state()
init_database()

# 自动加载已有数据
if not st.session_state.data_loaded:
    load_data_from_db()

# 加载自定义品类/品牌（每次启动都从文件读取，确保持久化）
if "custom_categories" not in st.session_state:
    load_filter_overrides()


# ─── 筛选控件 ─────────────────────────────────────────────────────
def render_filters(df: pd.DataFrame) -> dict:
    """渲染侧边栏筛选控件，返回筛选条件字典"""
    filters = {}

    st.sidebar.markdown("### 筛选条件")

    # 时间范围
    if "sale_date" in df.columns and not df["sale_date"].isna().all():
        min_date = df["sale_date"].min().date()
        max_date = df["sale_date"].max().date()
        date_range = st.sidebar.date_input(
            "销售日期范围",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="filter_date",
        )
        if len(date_range) == 2:
            filters["date_start"] = date_range[0]
            filters["date_end"] = date_range[1]

    # 品类（多选）
    if "category" in df.columns:
        categories = sorted(df["category"].dropna().unique())
        extra_cats = st.session_state.get("custom_categories", [])
        categories = sorted(set(categories + extra_cats))
        if len(categories) > 0:
            selected_cat = st.sidebar.multiselect(
                "品类", categories, default=categories, key="filter_cat",
            )
            if selected_cat:
                filters["categories"] = selected_cat

        # 品类管理
        with st.sidebar.expander("管理品类", expanded=False):
            st.caption("添加或删除品类选项，删除会同时清除对应数据")
            new_cat = st.text_input("添加品类", label_visibility="collapsed", placeholder="输入新品类名称", key="new_cat")
            if st.button("添加", key="add_cat") and new_cat.strip():
                custom = st.session_state.get("custom_categories", [])
                if new_cat.strip() not in custom:
                    st.session_state.custom_categories = custom + [new_cat.strip()]
                    save_filter_overrides()
                    st.rerun()

            current_cats = sorted(df["category"].dropna().unique())
            if current_cats:
                del_cat = st.selectbox("选择要删除的品类", options=[""] + current_cats, key="del_cat")
                if del_cat and st.button("删除该品类及数据", type="secondary", key="del_cat_btn"):
                    delete_orders_by_field("category", del_cat)
                    load_data_from_db()
                    st.rerun()

    # 品牌（联动过滤）
    if "brand" in df.columns:
        brand_df = df
        if "categories" in filters:
            brand_df = brand_df[brand_df["category"].isin(filters["categories"])]
        brands = sorted(brand_df["brand"].dropna().unique())
        extra_brands = st.session_state.get("custom_brands", [])
        brands = sorted(set(brands + extra_brands))
        if len(brands) > 0:
            selected_brands = st.sidebar.multiselect(
                "品牌", brands, default=brands, key="filter_brand",
            )
            if selected_brands:
                filters["brands"] = selected_brands

        # 品牌管理
        with st.sidebar.expander("管理品牌", expanded=False):
            st.caption("添加或删除品牌选项，删除会同时清除对应数据")
            new_brand = st.text_input("添加品牌", label_visibility="collapsed", placeholder="输入新品牌名称", key="new_brand")
            if st.button("添加", key="add_brand") and new_brand.strip():
                custom = st.session_state.get("custom_brands", [])
                if new_brand.strip() not in custom:
                    st.session_state.custom_brands = custom + [new_brand.strip()]
                    save_filter_overrides()
                    st.rerun()

            current_brands = sorted(df["brand"].dropna().unique())
            if current_brands:
                del_brand = st.selectbox("选择要删除的品牌", options=[""] + current_brands, key="del_brand")
                if del_brand and st.button("删除该品牌及数据", type="secondary", key="del_brand_btn"):
                    delete_orders_by_field("brand", del_brand)
                    load_data_from_db()
                    st.rerun()

    # 核销状态
    if "subsidy_status" in df.columns:
        statuses = df["subsidy_status"].dropna().unique()
        status_options = ["全部"] + sorted(s for s in statuses if s) + ["已逾期"]
        selected_status = st.sidebar.radio(
            "核销状态",
            status_options,
            horizontal=True,
            key="filter_status",
        )
        if selected_status and selected_status != "全部":
            filters["subsidy_status"] = selected_status

    # 应用按钮
    st.sidebar.button("应用筛选", type="primary", use_container_width=True, key="apply_filters")

    return filters


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """将筛选条件应用到数据"""
    result = df.copy()

    if "date_start" in filters and "sale_date" in result.columns:
        result = result[result["sale_date"] >= pd.Timestamp(filters["date_start"])]
    if "date_end" in filters and "sale_date" in result.columns:
        result = result[result["sale_date"] <= pd.Timestamp(filters["date_end"])]
    if "categories" in filters and "category" in result.columns:
        result = result[result["category"].isin(filters["categories"]) | result["category"].isna()]
    if "brands" in filters and "brand" in result.columns:
        result = result[result["brand"].isin(filters["brands"]) | result["brand"].isna()]
    if "subsidy_status" in filters and "subsidy_status" in result.columns:
        if filters["subsidy_status"] == "已逾期":
            today = pd.Timestamp.now().normalize()
            result = result[
                (result["subsidy_status"] != "已核销")
                & (result["subsidy_amount"] > 0)
                & ((result["sale_date"] + pd.Timedelta(days=30)) < today)
            ]
        else:
            result = result[result["subsidy_status"] == filters["subsidy_status"]]

    return result


# ─── KPI 卡片 ──────────────────────────────────────────────────────
def render_kpi_cards(df: pd.DataFrame):
    """渲染核心指标卡片"""
    total_sales = df["amount"].sum()
    total_orders = len(df)
    avg_price = total_sales / total_orders if total_orders > 0 else 0

    repeat_count = 0
    repeat_rate = 0
    if "customer_phone" in df.columns:
        customer_counts = df.groupby("customer_phone")["order_id"].count()
        repeat_count = (customer_counts >= 2).sum()
        repeat_rate = repeat_count / len(customer_counts) if len(customer_counts) > 0 else 0

    pending_subsidy = df[df["subsidy_status"] == "未核销"]["subsidy_amount"].sum() if "subsidy_status" in df.columns else 0

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("总销售额", f"¥{total_sales:,.0f}")
    col2.metric("总订单数", f"{total_orders:,}")
    col3.metric("平均客单价", f"¥{avg_price:,.0f}")
    col4.metric("回购客户数", str(repeat_count))
    col5.metric("回购率", f"{repeat_rate:.1%}")
    col6.metric("待核销补贴", f"¥{pending_subsidy:,.0f}")


# ─── 页面渲染 ──────────────────────────────────────────────────────
def render_dashboard(df: pd.DataFrame):
    """综合看板页面"""
    render_kpi_cards(df)

    st.divider()

    import plotly.graph_objects as go
    import numpy as np

    # 销售趋势图（按日聚合，完整日期轴）
    if "sale_date" in df.columns:
        df_daily = df.copy()
        df_daily["日期"] = df_daily["sale_date"].dt.date
        df_daily["amount"] = pd.to_numeric(df_daily["amount"], errors="coerce").fillna(0)
        daily = df_daily.groupby("日期").agg(
            销售额=("amount", "sum"),
            订单数=("order_id", "count"),
        ).reset_index()

        date_range = pd.date_range(
            daily["日期"].min(), daily["日期"].max(), freq="D"
        )
        full_calendar = pd.DataFrame({"日期": date_range.date})
        daily = full_calendar.merge(daily, on="日期", how="left").fillna({"销售额": 0, "订单数": 0})
        daily["销售额"] = pd.to_numeric(daily["销售额"], errors="coerce").fillna(0)

        # 使用 plotly.graph_objects 重写趋势图
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily["日期"].astype(str).tolist(),
            y=daily["销售额"].tolist(),
            mode='lines+markers',
            name='销售额',
            line=dict(shape='spline', color='#1f77b4'),
            marker=dict(color='#1f77b4', size=8)
        ))
        fig.update_layout(
            title='每日销售趋势',
            xaxis_title='日期',
            yaxis_title='销售额',
            height=400,
            xaxis=dict(tickformat='%Y年%m月%d日'),
            template='plotly_white'
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # 两个并排图表
    col_left, col_right = st.columns(2)

    # 品类分析
    cat_data = pd.DataFrame()
    if "category" in df.columns:
        df_amount = df.copy()
        df_amount["amount"] = pd.to_numeric(df_amount["amount"], errors="coerce").fillna(0)
        cat_data = (
            df_amount.dropna(subset=["category"])
            .groupby("category")["amount"]
            .sum()
            .reset_index(name="销售额")
        )
        if not cat_data.empty:
            cat_data["销售额"] = pd.to_numeric(cat_data["销售额"], errors="coerce").fillna(0)
            total = cat_data["销售额"].sum()
            cat_data["占比"] = (cat_data["销售额"] / total * 100).round(1)
            cat_data["占比显示"] = cat_data["占比"].apply(lambda x: f"{x}%")
            cat_data["销售额文本"] = cat_data["销售额"].apply(lambda x: f"¥{x:,.0f}")

    with col_left:
        if cat_data.empty:
            st.caption("暂无品类数据")
        else:
            # 使用 plotly.graph_objects 重写饼图
            fig = go.Figure(data=[go.Pie(
                labels=cat_data["category"].tolist(),
                values=cat_data["销售额"].tolist(),
                textposition='inside',
                textinfo='percent+label',
                hovertext=cat_data["销售额文本"].tolist(),
                hovertemplate='<b>%{label}</b><br>销售额: %{hovertext}<extra></extra>',
                marker=dict(colors=[
                    '#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78', 
                    '#2ca02c', '#98df8a', '#d62728'
                ])
            )])
            fig.update_layout(
                title='品类销售额分布',
                height=400,
                template='plotly_white'
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    with col_right:
        if cat_data.empty:
            st.caption("暂无品类数据")
        else:
            bar_data = cat_data.sort_values("销售额", ascending=True)
            # 使用 plotly.graph_objects 重写条形图
            fig = go.Figure(data=[go.Bar(
                x=bar_data["销售额"].tolist(),
                y=bar_data["category"].tolist(),
                orientation='h',
                text=bar_data["占比显示"].tolist(),
                textposition='outside',
                marker=dict(color='#1f77b4'),
                hovertext=bar_data["销售额文本"].tolist(),
                hovertemplate='<b>%{y}</b><br>销售额: %{hovertext}<br>占比: %{text}<extra></extra>'
            )])
            fig.update_layout(
                title='品类销售额排行',
                xaxis_title='销售额',
                yaxis_title='品类',
                height=400,
                yaxis=dict(categoryorder='array', categoryarray=bar_data["category"].tolist()),
                margin=dict(l=10, r=40, t=40, b=10),
                template='plotly_white'
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    render_export_button(df, key="export_dashboard")


def render_help():
    """帮助页面"""
    st.subheader("使用帮助")

    with st.expander("如何导入数据？", expanded=True):
        st.markdown("""
        1. 点击左侧导航栏上方的 **导入数据** 按钮
        2. 拖拽或选择 Excel 文件（.xlsx / .xls）
        3. 系统自动识别字段，导入完成后显示预览
        4. 导入成功后自动跳转看板
        """)

    with st.expander("需要什么格式的 Excel 文件？"):
        st.markdown("""
        **必填字段：** 销售日期、金额

        **推荐字段：** 订单编号、客户姓名、客户电话、商品名称、品类、品牌

        **可选字段：** 型号、数量、国补金额、核销状态、销售渠道、地址

        表头名称可灵活（如"销售额""成交价"都可识别为金额），系统会自动匹配。
        """)

    with st.expander("数据会丢失吗？"):
        st.markdown("""
        每次导入新数据前会自动备份旧数据库到 `data/backups/` 目录。
        建议定期手动备份 `data/` 目录到 U 盘或其他安全位置。
        """)

    with st.expander("技术支持"):
        st.markdown("""
        - 项目基于 Streamlit + Python 构建
        - 所有数据本地存储，不上传云端
        - 遇到问题请检查 [常见问题 FAQ](#)
        """)


# ─── 导航与主体布局 ──────────────────────────────────────────────
def main():
    # 顶部标题栏
    st.title(f"{APP_ICON} {APP_TITLE}")
    st.divider()

    # ─── 导入数据界面 ──────────────────────────────
    if st.session_state.show_import:
        run_import_ui()
        if st.button("进入销售看板", type="primary"):
            st.session_state.show_import = False
            load_data_from_db()
            st.rerun()
        return

    # ─── 数据检查 ──────────────────────────────────
    if not st.session_state.data_loaded:
        st.info("尚未导入数据，请点击上方「导入数据」按钮上传 Excel 文件。")
        return

    df = st.session_state.df

    # ─── 侧边栏（导入 → 导航 → 筛选） ────────────
    with st.sidebar:
        if st.button("导入数据", use_container_width=True, type="secondary"):
            st.session_state.show_import = not st.session_state.show_import

        st.divider()

        st.markdown("### 导航")
        pages = ["综合看板", "热销品类排行", "回购顾客分析", "国补核销预警", "热门购货区域", "订单明细", "帮助"]
        page = st.radio("", pages, label_visibility="collapsed", key="nav_radio")
        st.session_state.page = page

        st.divider()

        filters = render_filters(df)

    # ─── 应用筛选 ──────────────────────────────────
    filtered_df = apply_filters(df, filters)

    # ─── 页面路由 ──────────────────────────────────
    page = st.session_state.page

    if page == "综合看板":
        render_dashboard(filtered_df)
    elif page == "热销品类排行":
        render_ranking_ui(filtered_df)
        render_export_button(filtered_df, key="export_ranking")
    elif page == "回购顾客分析":
        render_repeat_customers_ui(filtered_df)
        render_export_button(filtered_df, key="export_repeat")
    elif page == "国补核销预警":
        render_subsidy_alert_ui(filtered_df)
        render_export_button(filtered_df, key="export_subsidy")
    elif page == "热门购货区域":
        render_heatmap_ui(filtered_df)
        render_export_button(filtered_df, key="export_heatmap")
    elif page == "订单明细":
        render_data_viewer(filtered_df)
        render_export_button(filtered_df, key="export_viewer")
    elif page == "帮助":
        render_help()


if __name__ == "__main__":
    main()
