#!/usr/bin/env python3
"""
K线形态自动识别模块。
替代 LLM 肉眼判断K线形态。
"""


def _avg_body(bars):
    """计算平均实体大小"""
    bodies = [abs(b["close"] - b["open"]) for b in bars if b.get("close") and b.get("open")]
    if not bodies:
        return 0
    return sum(bodies) / len(bodies)


def detect_candle_patterns(bars: list) -> list:
    """
    检测常见K线形态。

    bars: [{"date","open","close","high","low","volume"}, ...]
    至少5根。

    返回 str 列表，如 ["十字星", "看涨吞没"]
    """
    if not bars or len(bars) < 3:
        return []

    patterns = []
    avg_body = _avg_body(bars)

    if avg_body == 0:
        avg_body = 1  # 防止除零

    n = len(bars)
    last = bars[-1]

    # ── 十字星 (Doji) ──
    for i, b in enumerate(bars):
        body = abs(b["close"] - b["open"])
        total = b["high"] - b["low"]
        if total > 0 and body < total * 0.1:
            if i == n - 1:
                patterns.append("十字星(最新)")
            else:
                patterns.append(f"十字星({b.get('date', '?')})")

    # ── 锤子线 / 上吊线 ──
    def _hammer_check(b, uptrend):
        body = abs(b["close"] - b["open"])
        lower_shadow = min(b["open"], b["close"]) - b["low"]
        upper_shadow = b["high"] - max(b["open"], b["close"])
        if body > 0 and lower_shadow > body * 2 and upper_shadow < body * 0.5:
            return "上吊线" if uptrend else "锤子线"
        return None

    if n >= 5:
        recent_3 = bars[-3:]
        mid = len(recent_3) // 2
        prev_trend = sum(1 for b in recent_3[:mid] if b["close"] > b["open"])
        uptrend = prev_trend >= mid  # 前面阳线多=上涨趋势

        hammer = _hammer_check(last, uptrend)
        if hammer:
            patterns.append(hammer)

    # ── 看涨/看跌 吞没 ──
    if n >= 2:
        prev = bars[-2]
        if (last["close"] > last["open"] and  # 当前阳线
            prev["close"] < prev["open"] and  # 前根阴线
            last["open"] < prev["close"] and
            last["close"] > prev["open"]):
            patterns.append("看涨吞没")
        elif (last["close"] < last["open"] and  # 当前阴线
              prev["close"] > prev["open"] and  # 前根阳线
              last["open"] > prev["close"] and
              last["close"] < prev["open"]):
            patterns.append("看跌吞没")

    # ── 三连阳 / 三连阴 ──
    if n >= 3:
        last_3 = bars[-3:]
        if all(b["close"] > b["open"] for b in last_3):
            if all(last_3[i]["close"] > last_3[i - 1]["close"] for i in range(1, 3)):
                patterns.append("三连阳")
        if all(b["close"] < b["open"] for b in last_3):
            if all(last_3[i]["close"] < last_3[i - 1]["close"] for i in range(1, 3)):
                patterns.append("三连阴")

    # ── 晨星 / 暮星 ──
    if n >= 3:
        b1, b2, b3 = bars[-3]
        body1 = abs(b1["close"] - b1["open"])
        body2 = abs(b2["close"] - b2["open"])
        body3 = abs(b3["close"] - b3["open"])

        # 晨星: 大阴线 → 小实体 → 大阳线
        if (b1["close"] < b1["open"] and body1 > avg_body * 1.5 and
            body2 < avg_body * 0.5 and
            b3["close"] > b3["open"] and body3 > avg_body * 1.5 and
            b3["close"] > b1["open"] - body1 * 0.5):
            patterns.append("晨星")

        # 暮星: 大阳线 → 小实体 → 大阴线
        if (b1["close"] > b1["open"] and body1 > avg_body * 1.5 and
            body2 < avg_body * 0.5 and
            b3["close"] < b3["open"] and body3 > avg_body * 1.5 and
            b3["close"] < b1["close"] - body1 * 0.5):
            patterns.append("暮星")

    return patterns


def simple_direction(bars: list) -> str:
    """
    简化的短线方向判断（纯K线）。

    基于最近3根K线的实体方向：
    - 3阳 → "连续走强"
    - 2阳1阴（阳包阴）→ "偏强"
    - 3阴 → "连续走弱"
    - 2阴1阳（阴包阳）→ "偏弱"
    - 其他 → "震荡"
    """
    if not bars or len(bars) < 3:
        return "数据不足"

    last_3 = bars[-3:]
    yang = sum(1 for b in last_3 if b["close"] > b["open"])
    yin = 3 - yang

    if yang == 3:
        return "连续走强"
    elif yang == 2:
        # 检查阴线是否被阳线包住（最后阳线收盘 > 阴线开盘）
        # 简单起见：2阳=偏强
        return "偏强"
    elif yin == 3:
        return "连续走弱"
    elif yin == 2:
        return "偏弱"
    else:
        return "震荡"


__all__ = ["detect_candle_patterns", "simple_direction"]
