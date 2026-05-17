"""
数据清洗工具函数
"""

import pandas as pd
import numpy as np


FIELD_MAP = {
    '订单编号': 'order_id', '订单号': 'order_id', '单号': 'order_id', '序号': 'order_id',
    '客户姓名': 'customer_name', '顾客姓名': 'customer_name', '姓名': 'customer_name',
    '客户名称': 'customer_name', '顾客名称': 'customer_name',
    '客户电话': 'customer_phone', '电话': 'customer_phone', '手机号': 'customer_phone',
    '联系电话': 'customer_phone', '联系手机': 'customer_phone',
    '商品名称': 'product_name', '产品名称': 'product_name', '商品': 'product_name',
    '商品型号': 'model', '产品型号': 'model',
    '品类': 'category', '类别': 'category', '产品类别': 'category',
    '品牌': 'brand',
    '型号': 'model', '规格型号': 'model',
    '数量': 'quantity', '销量': 'quantity', '商品数量': 'quantity', '产品数量': 'quantity',
    '金额': 'amount', '销售金额': 'amount', '销售额': 'amount', '成交价': 'amount',
    '应付总额': 'amount', '应付金额': 'amount', '总金额': 'amount',
    '实付总额': 'amount', '实付金额': 'amount', '成交总额': 'amount',
    '国补金额': 'subsidy_amount', '补贴金额': 'subsidy_amount', '补贴': 'subsidy_amount',
    '核销状态': 'subsidy_status', '补贴状态': 'subsidy_status',
    '是否核销国补卷': 'subsidy_status', '是否核销国补券': 'subsidy_status',
    '销售日期': 'sale_date', '日期': 'sale_date', '购买日期': 'sale_date',
    '签单日期': 'sale_date',
    '渠道': 'channel', '销售渠道': 'channel',
    '地址': 'address', '客户地址': 'address', '收货地址': 'address',
}

OPTIONAL_FIELDS = ['sale_date', 'amount']

# 销售订单标准字段（用于空行检测等）
SALES_ORDERS_COLS = [
    "order_id", "customer_name", "customer_phone", "product_name",
    "category", "brand", "model", "quantity", "amount", "subsidy_amount",
    "subsidy_status", "sale_date", "channel", "address",
]

# ─── 品牌/品类推断 ─────────────────────────────────────────
KNOWN_BRANDS = sorted([
    '海尔', '美的', '格力', '海信', 'TCL', '长虹', '康佳', '创维',
    '松下', '索尼', '三星', 'LG', '奥克斯', '志高', '格兰仕',
    '方太', '老板', '华帝', '史密斯', '飞利浦', '九阳', '苏泊尔',
    '小熊', '小米', '华为', '荣耀', '夏普', '东芝', '日立',
    '三菱电机', '三菱重工', '大金', '惠而浦', '博世', '西门子',
    '容声', '美菱', '小天鹅', '统帅', '卡萨帝', 'COLMO',
    '万和', '万家乐', '华凌', '新飞', '长虹美菱', '威力',
], key=len, reverse=True)

CATEGORY_PATTERNS = [
    ('空调', ['KFR', 'KF-', 'KFRd', 'KFR-']),
    ('冰箱', ['BCD', 'BC-', 'BD-', 'BC/BD']),
    ('洗衣机', ['XQB', 'XQG', 'XPB', 'XQS', 'XQ']),
    ('热水器', ['JSQ', 'JSW', 'JSG', 'JST']),
    ('油烟机', ['CXW', 'CX']),
    ('燃气灶', ['JZT', 'JZY', 'JZR']),
    ('消毒柜', ['ZTD', 'ZTP']),
    ('净水器', ['RO-', 'RU-']),
]

# 中文品类关键词（匹配模型名中的任意位置）
CATEGORY_KEYWORDS = {
    '空调': '空调', '柜机': '空调', '挂机': '空调', '风管机': '空调', '中央空调': '空调',
    '电视': '电视', 'TV': '电视', '彩电': '电视',
    '冰箱': '冰箱', '冷柜': '冰箱', '冰柜': '冰箱',
    '洗衣机': '洗衣机', '滚筒': '洗衣机', '波轮': '洗衣机', '洗烘': '洗衣机',
    '热水器': '热水器', '电热': '热水器',
    '油烟机': '油烟机', '吸油烟机': '油烟机',
    '燃气灶': '燃气灶', '灶具': '燃气灶',
    '净水器': '净水器',
}


def infer_brand_from_model(model_val) -> str | None:
    """从型号/商品名中推断品牌"""
    if pd.isna(model_val) or str(model_val).strip() == '':
        return None
    text_raw = str(model_val).strip()
    text = text_raw.upper()
    # 先尝试精确匹配原始文本（适用于中文品牌）
    for brand in KNOWN_BRANDS:
        if text_raw.startswith(brand):
            return brand
    # 再尝试大写匹配（适用于 TCL、LG 等英文品牌）
    for brand in KNOWN_BRANDS:
        if text.startswith(brand.upper()):
            return brand
    return None


def infer_category_from_model(model_val) -> str | None:
    """从型号中推断品类"""
    if pd.isna(model_val):
        return None
    text = str(model_val).strip().upper()
    # 先尝试型号前缀代码匹配
    for cat, prefixes in CATEGORY_PATTERNS:
        for prefix in prefixes:
            if text.startswith(prefix) or text.startswith(prefix.upper()):
                return cat
    # 再尝试中文关键词匹配（品牌名后的品类词）
    text_raw = str(model_val).strip()
    for keyword, cat in CATEGORY_KEYWORDS.items():
        if keyword in text_raw:
            return cat
    return None


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """将 Excel 表头映射为标准列名（自动去除括号后缀）"""
    # 清理列名：去空格、全角括号转半角、去除 (元) 等后缀
    cleaned_map = {}
    for col in df.columns:
        c = str(col).strip()
        c = c.replace('（', '(').replace('）', ')')
        c = c.replace('＿', '_')
        # 去掉括号后缀，如 应付总额(元) → 应付总额
        if '(' in c:
            base = c.split('(')[0].strip()
            cleaned_map[col] = base
        else:
            cleaned_map[col] = c

    df = df.rename(columns=cleaned_map)
    # 再用 FIELD_MAP 做标准映射
    df = df.rename(columns=FIELD_MAP)
    # 若多列映射到同一英文名，只保留第一个（避免后面 .str 等操作报错）
    df = df.loc[:, ~df.columns.duplicated(keep='first')]
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """数据清洗：类型转换、空值处理"""
    df = df.dropna(how='all')

    if 'sale_date' in df.columns:
        df['sale_date'] = pd.to_datetime(df['sale_date'], errors='coerce')

    for col in ['amount', 'subsidy_amount']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'[^\d.]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'quantity' in df.columns:
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')

    # 在填充默认值之前，移除所有关键字段均为空的无效行
    essential = [c for c in ['sale_date', 'amount', 'customer_name', 'model'] if c in df.columns]
    if essential:
        df = df.dropna(subset=essential, how='all')

    # 填充默认值
    for col in ['amount', 'subsidy_amount']:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    if 'quantity' in df.columns:
        df['quantity'] = df['quantity'].fillna(1).astype(int)
    else:
        df['quantity'] = 1

    if 'subsidy_status' not in df.columns:
        df['subsidy_status'] = '未核销'
    if 'channel' not in df.columns:
        df['channel'] = '门店'
    if 'sale_date' not in df.columns:
        df['sale_date'] = pd.Timestamp.now().normalize()
    if 'amount' not in df.columns:
        df['amount'] = 0

    # 从型号推断缺失的品牌/品类
    df = _infer_missing_fields(df)

    # 若 product_name 缺失但 model 存在，用 model 填充
    if 'product_name' not in df.columns and 'model' in df.columns:
        df['product_name'] = df['model']

    # 移除所有标准字段均为空的无效行
    std_cols = [c for c in SALES_ORDERS_COLS if c in df.columns]
    if std_cols:
        before = len(df)
        df = df.dropna(subset=std_cols, how='all')
        if len(df) < before:
            pass  # 静默移除全空行

    # 优化数据类型以减少内存
    for col in ['category', 'brand', 'subsidy_status', 'channel']:
        if col in df.columns:
            df[col] = df[col].astype('category')

    for col in ['amount', 'subsidy_amount']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], downcast='float')

    if 'quantity' in df.columns:
        df['quantity'] = pd.to_numeric(df['quantity'], downcast='integer')

    return df


def validate_data(df: pd.DataFrame) -> list[str]:
    """校验数据，返回警告列表（不阻止导入）"""
    warnings = []
    for field in OPTIONAL_FIELDS:
        if field not in df.columns:
            warnings.append(f"缺少字段「{field}」，已使用默认值")
        else:
            missing = df[field].isna().sum()
            if missing > 0:
                warnings.append(f"字段「{field}」有 {missing} 行数据为空，已使用默认值")
    return warnings


def _infer_missing_fields(df: pd.DataFrame) -> pd.DataFrame:
    """从型号推断缺失的品牌和品类"""
    if "model" not in df.columns:
        return df

    # 确保 brand/category 列存在（即使原数据没有）
    if "brand" not in df.columns:
        df["brand"] = None
    if "category" not in df.columns:
        df["category"] = None

    # 对品牌缺失的行推断
    missing_brand = df["brand"].isna() | (df["brand"].astype(str).str.strip() == "")
    if missing_brand.any():
        df.loc[missing_brand, "brand"] = df.loc[missing_brand, "model"].apply(infer_brand_from_model)

    # 对品类缺失的行推断
    missing_cat = df["category"].isna() | (df["category"].astype(str).str.strip() == "")
    if missing_cat.any():
        df.loc[missing_cat, "category"] = df.loc[missing_cat, "model"].apply(infer_category_from_model)

    return df
