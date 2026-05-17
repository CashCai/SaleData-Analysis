"""
配置文件 — 使用时修改对应值即可
"""

# ============================================================
# 数据库配置
# ============================================================
DB_DIR = "data"
DB_NAME = "sales_data.db"
DB_PATH = f"{DB_DIR}/{DB_NAME}"

# ============================================================
# 国补核销配置
# ============================================================
SUBSIDY_DEADLINE_DAYS = 30  # 销售日期后多少天内需核销
SUBSIDY_WARNING_DAYS = 7    # 提前多少天预警

# ============================================================
# 地理编码（高德地图 API）
# ============================================================
# 申请地址：https://console.amap.com/dev/key/app
AMAP_API_KEY = "9b11d9892739328f6cc42073695eb687"
AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
AMAP_REGEO_URL = "https://restapi.amap.com/v3/geocode/regeo"

# ============================================================
# 应用配置
# ============================================================
APP_TITLE = "家电销售数据可视化看板"
APP_ICON = "🏠"
PAGE_SIZE = 200  # 数据分页每页行数
CACHE_TTL = 30   # 缓存有效期（秒）

# ============================================================
# 筛选器自定义选项（添加后持久保存，重启网页仍生效）
# ============================================================
FILTER_OVERRIDES_PATH = f"{DB_DIR}/filter_overrides.json"

# ============================================================
# Plotly 图表工具栏：仅保留全屏按钮，避免缩放/拖拽等误操作
# ============================================================
PLOTLY_CONFIG = {
    "displayModeBar": True,
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "select2d", "lasso2d",
        "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
        "toImage", "sendDataToCloud",
        "toggleSpikelines", "hoverClosestCartesian", "hoverCompareCartesian",
    ],
    "displaylogo": False,
}
