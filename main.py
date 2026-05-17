"""
家电销售数据可视化看板 — 主程序入口
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from config import APP_TITLE, APP_ICON
from database.db_manager import init_database, read_all_orders
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


def load_data_from_db():
    """从数据库加载数据到 session state"""
    rows = read_all_orders()
    if rows:
        df = pd.DataFrame(rows)
        df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
        st.session_state.df = df
        st.session_state.data_loaded = True
    else:
        st.session_state.data_loaded = False


init_session_state()
init_database()

# 自动加载已有数据
if not st.session_state.data_loaded:
    load_data_from_db()


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
        if len(categories) > 0:
            selected_cat = st.sidebar.multiselect(
                "品类", categories, default=categories, key="filter_cat",
            )
            if selected_cat:
                filters["categories"] = selected_cat

    # 品牌（联动过滤）
    if "brand" in df.columns:
        brand_df = df
        if "categories" in filters:
            brand_df = brand_df[brand_df["category"].isin(filters["categories"])]
        brands = sorted(brand_df["brand"].dropna().unique())
        if len(brands) > 0:
            selected_brands = st.sidebar.multiselect(
                "品牌", brands, default=brands, key="filter_brand",
            )
            if selected_brands:
                filters["brands"] = selected_brands

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
        result = result[result["category"].isin(filters["categories"])]
    if "brands" in filters and "brand" in result.columns:
        result = result[result["brand"].isin(filters["brands"])]
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

    # 销售趋势图（按月聚合）
    if "sale_date" in df.columns:
        df_month = df.copy()
        df_month["月份"] = df_month["sale_date"].dt.to_period("M").astype(str)
        monthly = df_month.groupby("月份").agg(
            销售额=("amount", "sum"),
            订单数=("order_id", "count"),
        ).reset_index().sort_values("月份")

        import plotly.express as px
        fig = px.line(
            monthly, x="月份", y="销售额",
            title="月度销售趋势",
            markers=True,
            line_shape="spline",
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    # 两个并排图表
    col_left, col_right = st.columns(2)

    with col_left:
        # 品类分布饼图
        if "category" in df.columns:
            cat_data = df.groupby("category").agg(销售额=("amount", "sum")).reset_index()
            import plotly.express as px
            fig = px.pie(cat_data, names="category", values="销售额", title="品类销售额分布")
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        # 品牌 Top 10 柱状图
        if "brand" in df.columns:
            brand_data = df.groupby("brand").agg(销售额=("amount", "sum")).reset_index()
            brand_top = brand_data.sort_values("销售额", ascending=False).head(10)
            import plotly.express as px
            fig = px.bar(
                brand_top, x="销售额", y="brand", orientation="h",
                title="品牌销售额 Top 10", color="销售额",
                color_continuous_scale="Viridis",
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=400)
            st.plotly_chart(fig, use_container_width=True)

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
        if st.button("返回看板", type="primary"):
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
        pages = ["综合看板", "销售排行", "回购顾客分析", "国补核销预警", "销售热力图", "数据查看", "帮助"]
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
    elif page == "销售排行":
        render_ranking_ui(filtered_df)
        render_export_button(filtered_df, key="export_ranking")
    elif page == "回购顾客分析":
        render_repeat_customers_ui(filtered_df)
        render_export_button(filtered_df, key="export_repeat")
    elif page == "国补核销预警":
        render_subsidy_alert_ui(filtered_df)
        render_export_button(filtered_df, key="export_subsidy")
    elif page == "销售热力图":
        render_heatmap_ui(filtered_df)
        render_export_button(filtered_df, key="export_heatmap")
    elif page == "数据查看":
        render_data_viewer(filtered_df)
        render_export_button(filtered_df, key="export_viewer")
    elif page == "帮助":
        render_help()


if __name__ == "__main__":
    main()
