"""
数据导出模块 — 导出为 Excel
"""

import streamlit as st
import pandas as pd
from io import BytesIO


def export_to_excel(df: pd.DataFrame, filename: str = "分析结果") -> BytesIO:
    """将 DataFrame 导出为 Excel 字节流"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="数据", index=False)
    output.seek(0)
    return output


def render_export_button(df: pd.DataFrame, key: str = "export"):
    """导出按钮"""
    if df.empty:
        st.caption("当前没有可导出的数据")
        return

    buf = export_to_excel(df)
    st.download_button(
        label="导出当前数据为 Excel",
        data=buf,
        file_name=f"销售分析导出_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=key,
    )
