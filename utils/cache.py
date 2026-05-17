"""
简单内存缓存 — 同一筛选条件下不重复计算
"""

import time
import hashlib
import json
from config import CACHE_TTL


class DataCache:
    def __init__(self, ttl: int = CACHE_TTL):
        self._store = {}
        self._ttl = ttl

    def _make_key(self, data_id: str, params: dict) -> str:
        raw = f"{data_id}:{json.dumps(params, sort_keys=True, default=str)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, data_id: str, params: dict):
        key = self._make_key(data_id, params)
        entry = self._store.get(key)
        if entry and (time.time() - entry["time"]) < self._ttl:
            return entry["value"]
        return None

    def set(self, data_id: str, params: dict, value):
        key = self._make_key(data_id, params)
        self._store[key] = {"value": value, "time": time.time()}

    def clear(self):
        self._store.clear()


cache = DataCache()
