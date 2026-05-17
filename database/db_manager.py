"""
数据库管理 — 连接、初始化、备份
"""

import sqlite3
import os
import shutil
from datetime import datetime
from config import DB_DIR, DB_PATH
from database.models import ALL_TABLES, CREATE_INDEXES


def ensure_db_dir():
    """确保数据库目录存在"""
    os.makedirs(DB_DIR, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """初始化数据库：建表 + 索引 + 迁移"""
    ensure_db_dir()
    conn = get_connection()
    cursor = conn.cursor()
    for table_sql in ALL_TABLES:
        cursor.execute(table_sql)
    migrate_schema(cursor)
    for index_sql in CREATE_INDEXES:
        try:
            cursor.execute(index_sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


def migrate_schema(cursor: sqlite3.Cursor):
    """迁移旧数据库 schema，确保标准列存在"""
    expected_cols = [
        "order_id", "customer_name", "customer_phone", "product_name",
        "category", "brand", "model", "quantity", "amount", "subsidy_amount",
        "subsidy_status", "sale_date", "channel", "address", "geo_code",
        "latitude", "longitude",
    ]
    try:
        existing = {
            row[1]
            for row in cursor.execute("PRAGMA table_info(sales_orders)").fetchall()
        }
        missing = [c for c in expected_cols if c not in existing]
        if missing:
            # 逐列添加，不破坏已有数据
            col_types = {
                "latitude": "REAL", "longitude": "REAL",
                "quantity": "INTEGER", "amount": "REAL",
                "subsidy_amount": "REAL",
            }
            for col in missing:
                col_type = col_types.get(col, "TEXT")
                try:
                    cursor.execute(f"ALTER TABLE sales_orders ADD COLUMN {col} {col_type}")
                except sqlite3.OperationalError:
                    pass
    except sqlite3.OperationalError:
        pass


def backup_database():
    """导入新数据前备份旧数据库"""
    if not os.path.exists(DB_PATH):
        return

    backup_dir = os.path.join(DB_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"sales_data_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_path)


def read_all_orders() -> list[dict]:
    """读取所有销售订单"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sales_orders ORDER BY sale_date DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def delete_orders_by_field(field: str, value: str):
    """删除指定字段匹配的所有订单行（用于品类/品牌管理）"""
    allowed = {"category", "brand"}
    if field not in allowed:
        raise ValueError(f"field must be one of {allowed}")
    conn = get_connection()
    conn.execute(f"DELETE FROM sales_orders WHERE {field} = ?", (value,))
    conn.commit()
    conn.close()


def get_table_info() -> dict:
    """获取数据量统计"""
    conn = get_connection()
    cursor = conn.cursor()
    info = {}
    for table in ["sales_orders", "customers", "products"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        info[table] = cursor.fetchone()[0]
    conn.close()
    return info
