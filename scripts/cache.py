#!/usr/bin/env python3
"""
简易文件缓存系统。
按分类缓存数据，TTL过期自动清除。
"""

import os
import json
import time
import hashlib

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")

# 默认TTL（秒）
TTL_CONFIG = {
    "kline": 3600,     # K线: 1小时
    "quote": 300,      # 行情: 5分钟
    "news": 1800,      # 新闻: 30分钟
    "market": 1800,    # 市场: 30分钟
}


def _cache_path(key, category):
    """生成缓存文件路径"""
    h = hashlib.md5(key.encode()).hexdigest()
    cat_dir = os.path.join(CACHE_DIR, category)
    os.makedirs(cat_dir, exist_ok=True)
    return os.path.join(cat_dir, f"{h}.json")


def cache_get(key, category="default", ttl=None):
    """
    读取缓存。

    参数：
        key — 缓存键
        category — 缓存分类（kline/quote/news/market）
        ttl — 过期时间（秒），不传则用TTL_CONFIG默认值

    返回 dict 或 None（未命中/过期）
    """
    if ttl is None:
        ttl = TTL_CONFIG.get(category, 600)
    path = _cache_path(key, category)
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data.get("ts", 0) > ttl:
            return None
        return data.get("data")
    except (json.JSONDecodeError, IOError, OSError):
        return None


def cache_set(key, data, category="default"):
    """
    写入缓存。

    参数：
        key — 缓存键
        data — 任意 JSON 可序列化的数据
        category — 缓存分类
    """
    path = _cache_path(key, category)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "data": data}, f, ensure_ascii=False)
    except (IOError, OSError):
        pass


def cache_clear(category=None):
    """
    清除缓存。

    参数：
        category — 指定分类（None=清除全部）
    """
    if category:
        cat_dir = os.path.join(CACHE_DIR, category)
        try:
            for f in os.listdir(cat_dir):
                os.remove(os.path.join(cat_dir, f))
        except (IOError, OSError):
            pass
    else:
        try:
            for root, dirs, files in os.walk(CACHE_DIR):
                for f in files:
                    os.remove(os.path.join(root, f))
        except (IOError, OSError):
            pass


__all__ = ["cache_get", "cache_set", "cache_clear"]
