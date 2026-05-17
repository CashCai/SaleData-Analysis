"""
销售热力图模块 — 坐标点地图 + 区域分布备选
优先使用经纬度散点图，缺少坐标时降级为区域聚合
"""

import json
import pandas as pd
import streamlit as st
import plotly.express as px
from config import PLOTLY_CONFIG
from modules.data_viewer import CN_COLUMN_MAP, DISPLAY_COLUMNS

# 中国省份 GeoJSON（公开 CDN，由 DataV 提供）
CHINA_GEOJSON_URL = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"


def create_point_map(df: pd.DataFrame, metric: str, map_style: str = "clean"):
    """生成坐标点散点地图"""
    value_label = "销售额" if metric == "amount" else "销售量"
    agg_col = "amount" if metric == "amount" else "quantity"

    plot_df = df.dropna(subset=["latitude", "longitude", agg_col]).copy()
    if plot_df.empty:
        return None

    # 缩放点大小：销售额越大点越大，避免极端值过大
    max_val = plot_df[agg_col].max()
    if max_val is None or max_val == 0:
        size_norm = 15  # 全零数据，统一大小
    else:
        size_norm = plot_df[agg_col] / max_val * 30 + 5  # 5~35 范围

    # 使用 plotly.scatter_mapbox + 底图样式
    if map_style in ("carto-positron", "carto-darkmatter", "open-street-map", "stamen-terrain"):
        fig = px.scatter_mapbox(
            plot_df,
            lat="latitude",
            lon="longitude",
            size=size_norm,
            color=agg_col,
            color_continuous_scale="OrRd",
            hover_name="address",
            hover_data={
                "customer_name": True,
                "brand": True,
                "category": True,
                agg_col: ":,.0f",
                "latitude": False,
                "longitude": False,
            },
            title=f"{value_label} 地理分布",
            labels={agg_col: value_label},
            zoom=5,
            height=600,
        )

        fig.update_layout(mapbox_style=map_style)

        fig.update_layout(
            margin=dict(l=0, r=0, t=40, b=0),
            coloraxis_colorbar=dict(title=value_label, len=0.6),
        )

        # 默认聚焦云梦县（订单集中区域）
        fig.update_layout(
            mapbox=dict(center=dict(lat=31.02, lon=113.75), zoom=11),
        )

    else:
        # 纯坐标散点图：无瓦片依赖，100% 可用
        fig = px.scatter(
            plot_df,
            x="longitude",
            y="latitude",
            size=size_norm,
            color=agg_col,
            color_continuous_scale="OrRd",
            hover_name="address",
            hover_data={
                "customer_name": True,
                "brand": True,
                "category": True,
                agg_col: ":,.0f",
            },
            title=f"{value_label} 地理分布",
            labels={agg_col: value_label, "longitude": "经度", "latitude": "纬度"},
            height=600,
        )
        fig.update_traces(marker=dict(line=dict(width=1, color="white")))
        fig.update_layout(
            xaxis=dict(
                showgrid=True, gridcolor="lightgray", zeroline=False,
                title=dict(text="经度"),
            ),
            yaxis=dict(
                showgrid=True, gridcolor="lightgray", zeroline=False,
                title=dict(text="纬度"),
                scaleanchor="x",
            ),
            margin=dict(l=10, r=10, t=40, b=10),
            coloraxis_colorbar=dict(title=value_label, len=0.6),
            plot_bgcolor="white",
        )

    return fig


def _render_amap_leaflet(df: pd.DataFrame, metric: str):
    """用 Leaflet.js + 高德地图瓦片渲染坐标点散点图

    Leaflet 使用 <img> 标签加载瓦片，不受浏览器 CORS 策略限制，
    因此高德瓦片可在 localhost 开发环境中正常显示。
    """
    import streamlit.components.v1 as components

    value_label = "销售额" if metric == "amount" else "销售量"
    agg_col = "amount" if metric == "amount" else "quantity"

    plot_df = df.dropna(subset=["latitude", "longitude", agg_col]).copy()
    if plot_df.empty:
        st.info("筛选后的数据中没有有效坐标点")
        return

    # 构建 GeoJSON FeatureCollection
    features = []
    for _, row in plot_df.iterrows():
        val = row[agg_col]
        if pd.isna(val):
            continue
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(row["longitude"]), float(row["latitude"])],
            },
            "properties": {
                "customer_name": str(row.get("customer_name", "") or ""),
                "address": str(row.get("address", "") or ""),
                "brand": str(row.get("brand", "") or ""),
                "category": str(row.get("category", "") or ""),
                "value": float(val),
            },
        })

    geojson_str = json.dumps(
        {"type": "FeatureCollection", "features": features},
        ensure_ascii=False,
    )

    # 统计信息
    max_val = plot_df[agg_col].max()
    min_val = plot_df[agg_col].min()
    # 默认聚焦云梦县（订单集中区域）
    lat_center = 31.02
    lon_center = 113.75
    zoom = 12

    # 点半径 JS 表达式（全零数据时固定大小）
    radius_js = "Math.sqrt(f.properties.value/maxVal)*18+5" if max_val > 0 else "8"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  #map {{ height:600px; width:100%; }}
  .legend {{ background:rgba(255,255,255,.9); padding:8px 12px; border-radius:4px; box-shadow:0 1px 5px rgba(0,0,0,.2); line-height:20px; font-size:13px; }}
  .legend i {{ width:16px; height:16px; float:left; margin-right:6px; opacity:.8; }}
</style>
</head>
<body>
<div id="map"></div>
<script>
(function(){{
  var map = L.map('map').setView([{lat_center}, {lon_center}], {zoom});
  L.tileLayer('https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={{x}}&y={{y}}&z={{z}}', {{
    attribution: '&copy; 高德地图',
    maxZoom: 18, minZoom: 3,
  }}).addTo(map);

  var data = {geojson_str};
  var maxVal = {max_val};

  function color(t) {{
    if (t !== t) t = 0;
    t = Math.min(1, Math.max(0, t));
    var r = Math.round(255 - t * 15);
    var g = Math.round(237 - t * 178);
    var b = Math.round(160 - t * 128);
    return 'rgb('+r+','+g+','+b+')';
  }}

  var pts = L.geoJSON(data, {{
    pointToLayer: function(f, ll) {{
      var r = {radius_js};
      return L.circleMarker(ll, {{
        radius: r, fillColor: color(f.properties.value / (maxVal || 1)),
        color: '#fff', weight: 1, fillOpacity: .75,
      }});
    }},
    onEachFeature: function(f, layer) {{
      var p = f.properties;
      layer.bindTooltip(
        '<b>'+p.customer_name+'</b>'+(p.address?'<br>'+p.address:'')+
        '<br>{value_label}: ¥'+Number(p.value).toLocaleString(),
        {{direction:'top', offset:[0,-8]}}
      );
    }}
  }}).addTo(map);

  if (data.features.length) map.fitBounds(pts.getBounds(), {{padding:[30,30], maxZoom:14}});

  var legend = L.control({{position:'bottomright'}});
  legend.onAdd = function() {{
    var div = L.DomUtil.create('div','legend');
    div.innerHTML = '<b>{value_label}</b><br>';
    [0,.25,.5,.75,1].forEach(function(t) {{
      var v = {min_val} + t*({max_val}-{min_val});
      div.innerHTML += '<i style="background:'+color(t)+'"></i> ¥'+Math.round(v).toLocaleString()+'<br>';
    }});
    return div;
  }};
  legend.addTo(map);
}})();
</script>
</body>
</html>"""

    components.html(html, height=620)


def render_heatmap_ui(df: pd.DataFrame):
    """热力图页面"""
    st.subheader("销售热力图")

    # 判断可用数据源
    has_coords = (
        "latitude" in df.columns
        and "longitude" in df.columns
        and df["latitude"].notna().any()
    )
    geo_cols = [c for c in ["province", "city", "district"] if c in df.columns]

    if not has_coords and not geo_cols:
        st.info(
            "数据中不含地址信息，无法生成热力图。\n\n"
            "两种方式启用：\n"
            "1. **配置高德地图 Key**：在 `config.py` 中设置 `AMAP_API_KEY`，"
            "下次导入时会自动从地址解析经纬度\n"
            "2. **手动添加字段**：在 Excel 中添加 `省`/`市`/`区` 列"
        )
        return

    # ── 筛选项 ──────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric = st.selectbox(
            "指标", options=["amount", "quantity"],
            format_func=lambda x: "销售额" if x == "amount" else "销售量",
            key="heatmap_metric",
        )

    with col2:
        map_style = st.selectbox(
            "地图样式",
            options=["amap", "clean", "open-street-map"],
            format_func=lambda x: {
                "amap": "高德地图",
                "clean": "纯净模式（无底图）",
                "open-street-map": "OpenStreetMap",
            }.get(x, x),
            key="heatmap_style",
        )

    with col3:
        all_cats = ["全部"] + sorted(df["category"].dropna().unique().tolist()) if "category" in df.columns else ["全部"]
        sel_cat = st.selectbox("品类", options=all_cats, key="heatmap_cat")

    with col4:
        brand_df = df[df["category"] == sel_cat] if sel_cat != "全部" and "category" in df.columns else df
        all_brands = ["全部"] + sorted(brand_df["brand"].dropna().unique().tolist()) if "brand" in brand_df.columns else ["全部"]
        sel_brand = st.selectbox("品牌", options=all_brands, key="heatmap_brand")

    # ── 筛选数据 ────────────────────────────────────────
    filtered = df.copy()
    if sel_cat != "全部" and "category" in filtered.columns:
        filtered = filtered[filtered["category"] == sel_cat]
    if sel_brand != "全部" and "brand" in filtered.columns:
        filtered = filtered[filtered["brand"] == sel_brand]

    # ── 坐标点地图（主模式） ────────────────────────────
    if has_coords:
        if map_style == "clean":
            # 纯净模式：使用 st.map() 渲染，稳定可靠
            agg_col = "amount" if metric == "amount" else "quantity"
            map_df = filtered.dropna(subset=["latitude", "longitude", agg_col]).rename(
                columns={"latitude": "lat", "longitude": "lon"}
            )
            if not map_df.empty:
                st.map(map_df)
            else:
                st.info("筛选后的数据中没有有效坐标点")

        elif map_style == "amap":
            # 高德地图：使用 Leaflet.js（<img> 加载瓦片，无 CORS 问题）
            _render_amap_leaflet(filtered, metric)

        else:
            fig = create_point_map(filtered, metric, map_style)
            if fig:
                st.plotly_chart(
                    fig, use_container_width=True, config=PLOTLY_CONFIG,
                    key=f"heatmap_point_{sel_cat}_{sel_brand}_{metric}_{map_style}",
                )

    # ── 区域聚合（备选） ────────────────────────────────
    elif geo_cols:
        with col1:
            geo_level = st.selectbox(
                "地理层级", options=geo_cols,
                format_func=lambda x: {"province": "省", "city": "市", "district": "县/区"}.get(x, x),
                key="heatmap_geo",
            )

        fig = _create_region_map(filtered, geo_level, metric)
        if fig:
            st.plotly_chart(
                fig, use_container_width=True, config=PLOTLY_CONFIG,
                key=f"heatmap_region_{geo_level}_{metric}",
            )

        # 聚合数据表
        value_label = "销售额" if metric == "amount" else "销售量"
        agg_col = "amount" if metric == "amount" else "quantity"
        summary = (
            filtered.groupby(geo_level)
            .agg(**{value_label: (agg_col, "sum"), "订单数": ("order_id", "count")})
            .reset_index()
            .sort_values(value_label, ascending=False)
        )
        st.write(f"**{['省', '市', '县/区'][geo_cols.index(geo_level)]}级销售数据：**")
        st.dataframe(summary, use_container_width=True, hide_index=True)

    # ── 数据表格（默认收起，随筛选和指标更新） ─────────────
    with st.expander("查看数据表格", expanded=False):
        available_cols = [c for c in DISPLAY_COLUMNS if c in filtered.columns]
        if not filtered.empty:
            display_df = filtered[available_cols].rename(columns=CN_COLUMN_MAP)
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
        else:
            st.info("当前筛选条件下无数据")


def _create_region_map(df: pd.DataFrame, geo_level: str, metric: str):
    """区域聚合地图（省/市/区备选，与原有逻辑一致）"""
    value_label = "销售额" if metric == "amount" else "销售量"
    agg_col = "amount" if metric == "amount" else ("quantity" if "quantity" in df.columns else "order_id")

    if geo_level not in df.columns:
        return None

    geo_data = df.groupby(geo_level).agg(
        **{value_label: (agg_col, "sum")}
    ).reset_index()

    if geo_level == "province":
        fig = px.choropleth(
            geo_data,
            geojson=CHINA_GEOJSON_URL,
            locations=geo_level,
            featureidkey="properties.name",
            color=value_label,
            hover_name=geo_level,
            hover_data={value_label: ":,.0f", geo_level: False},
            color_continuous_scale="OrRd",
            title=f"{value_label} 地理分布",
            labels={value_label: value_label},
        )
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(
            height=600,
            margin=dict(l=10, r=10, t=40, b=10),
            coloraxis_colorbar=dict(title=value_label, len=0.6),
        )
    else:
        top_n = geo_data.sort_values(value_label, ascending=False).head(30)
        fig = px.bar(
            top_n, x=value_label, y=geo_level, orientation="h",
            title=f"{value_label} 地理分布（{geo_level}级 Top 30）",
            labels={value_label: value_label, geo_level: geo_level},
        )
        fig.update_traces(
            marker_color="#1f77b4",
            hovertemplate="<b>%{y}</b><br>" + value_label + ": %{x:,.0f}<extra></extra>",
        )
        fig.update_layout(
            yaxis={"categoryorder": "total descending"},
            xaxis_title=value_label,
            height=600, margin=dict(l=10, r=40, t=40, b=10),
        )

    return fig
