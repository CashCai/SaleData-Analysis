"""
地理编码 — 使用高德地图 API 将地址文字转为经纬度
首次转换后缓存到 SQLite，避免重复调用
"""

import sqlite3
import requests
from config import AMAP_API_KEY, AMAP_GEOCODE_URL, DB_PATH

GEO_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS geo_cache (
    address     TEXT PRIMARY KEY,
    lng         REAL,
    lat         REAL,
    formatted   TEXT
);
"""


def _ensure_cache_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(GEO_CACHE_TABLE)
    conn.commit()
    conn.close()


def _get_from_cache(address: str) -> tuple | None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT lng, lat, formatted FROM geo_cache WHERE address = ?", (address,))
    row = cursor.fetchone()
    conn.close()
    return row if row else None


def _save_to_cache(address: str, lng: float, lat: float, formatted: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO geo_cache (address, lng, lat, formatted) VALUES (?, ?, ?, ?)",
        (address, lng, lat, formatted),
    )
    conn.commit()
    conn.close()


def geocode(address: str) -> dict | None:
    """
    将地址转换为经纬度
    返回: {"lng": float, "lat": float, "formatted": str} 或 None
    """
    if not address or not address.strip():
        return None

    _ensure_cache_table()

    cached = _get_from_cache(address)
    if cached:
        return {"lng": cached[0], "lat": cached[1], "formatted": cached[2]}

    if not AMAP_API_KEY:
        return None

    try:
        resp = requests.get(
            AMAP_GEOCODE_URL,
            params={"key": AMAP_API_KEY, "address": address, "city": ""},
            timeout=5,
        )
        data = resp.json()
        if data["status"] == "1" and data["geocodes"]:
            location = data["geocodes"][0]["location"]
            lng, lat = map(float, location.split(","))
            formatted = data["geocodes"][0].get("formatted_address", address)
            _save_to_cache(address, lng, lat, formatted)
            return {"lng": lng, "lat": lat, "formatted": formatted}
    except Exception:
        pass

    return None
