#!/usr/bin/env python3
"""
短线因子评分系统。
替代 LLM 手动累加±1因子的过程。
所有函数仅做纯计算，不依赖外部 API。
"""

# 时间窗口权重修正
TIME_WEIGHTS = {
    "盘前": 1.0,
    "上午盘": 1.0,
    "午间→下午": 0.5,
    "盘后复盘": 0.3,
    "隔夜/周末": 0.5,
}


def score_moving_average(ss: dict) -> int:
    """
    均线系统评分。

    规则：
    - p > ma5 > ma10 > ma20 → +1（多头排列）
    - p < ma5 < ma10 < ma20 → -1（空头排列）
    - 其他情况 → 0（震荡）

    额外：
    - 如果 ma_pos = "多头" 且 p 距离 ma5 < 2% → 偏多但注意乖离小（+1）
    - 如果 ma_pos = "多头" 且 p > ma5 + ma5×5% → 乖离过大，有回调风险 → 0（保守降级）
    """
    if not ss:
        return 0

    p = ss.get("p", 0)
    ma5 = ss.get("ma5", 0)
    ma10 = ss.get("ma10", 0)
    ma20 = ss.get("ma20", 0)

    if p <= 0 or ma5 <= 0:
        return 0

    # 多头排列
    if p > ma5 > ma10 > ma20:
        # 乖离检查
        if p > ma5 * 1.05:
            return 0  # 乖离过大，回调风险
        return 1

    # 空头排列
    if p < ma5 < ma10 < ma20:
        return -1

    return 0


def score_volume(ss: dict) -> int:
    """
    量价关系评分。

    规则：
    - vr > 1.5 且 chg > 0 → +1（放量上涨）
    - vr > 1.5 且 chg < 0 → -1（放量下跌）
    - 其他（缩量或正常量）→ 0
    """
    if not ss:
        return 0

    vr = ss.get("vr", 0)
    chg = ss.get("chg", 0)

    if vr > 1.5 and chg > 0:
        return 1
    elif vr > 1.5 and chg < 0:
        return -1
    else:
        return 0


def score_fund_flow(f_net: float = None) -> int:
    """
    资金面评分。
    f_net: 当日主力净额（万元）。

    规则：
    - f_net > 0 → +1（净流入）
    - f_net < 0 → -1（净流出）
    - None 或 0 → None（不计入）
    """
    if f_net is None or f_net == 0:
        return None
    return 1 if f_net > 0 else -1


def score_events(positive: bool = False, negative: bool = False) -> int:
    """
    事件面评分。

    规则：
    - positive=True → +1
    - negative=True → -1
    - 均False → None（不计入）
    """
    if positive and not negative:
        return 1
    if negative and not positive:
        return -1
    return None


def score_us(us_dir: str, time_window: str) -> int:
    """
    美股传导评分。

    规则：
    - "同向涨" → +1
    - "同向跌" → -1
    - "偏涨" → +0.5
    - "偏跌" → -0.5

    权重修正：结果 × TIME_WEIGHTS[time_window]
    额外规则：
    - "分歧" → 0（美股方向不明，不计入）
    - "数据不可用" → None（不计入）
    """
    weight = TIME_WEIGHTS.get(time_window, 1.0)

    us_map = {
        "同向涨": 1,
        "同向跌": -1,
        "偏涨": 0.5,
        "偏跌": -0.5,
        "分歧": 0,
    }

    raw = us_map.get(us_dir, None)
    if raw is None:
        return None
    if raw == 0:
        return 0

    return raw * weight


def score_trend_amplitude(trend_5d: float) -> int:
    """
    趋势幅度评分（额外因子）。

    规则：
    - trend_5d > 10 → +0.5（强势，注意回调风险）
    - trend_5d < -10 → -0.5（弱势，注意反弹机会）
    - 其他 → 0
    """
    if not trend_5d:
        return 0
    if trend_5d > 10:
        return 0
    elif trend_5d < -10:
        return 0
    return 0


def compute_total_score(scores: dict, time_window: str) -> dict:
    """
    综合所有因子分数，输出方向概率。

    参数 scores: {
        "ma": int,        # 均线
        "volume": int,    # 量价
        "fund_flow": int or None,  # 资金
        "events": int or None,     # 事件
        "us": int or None,         # 美股
        "trend": int,    # 趋势幅度
    }

    计算：
    1. 跳过值为 None 的因子
    2. 总分 = Σ(分数 × 权重)
    3. 有效因子数 n = 非None因子数
    4. n < 3 → 不输出概率，改输出"方向倾向"

    返回：
    {
        "total": float,
        "n_active": int,
        "direction": "偏多" / "偏空" / "震荡",
        "probability": "70%+" / "60%+" / None,
        "confidence": "高" / "中" / "低",
        "factor_detail": str,
    }
    """
    _ = time_window  # 权重已在各因子自身应用中处理

    # 过滤有效因子
    factor_names = {
        "ma": "均线", "volume": "量价", "fund_flow": "资金",
        "events": "事件", "us": "美股", "trend": "趋势",
    }
    active = []
    details = []
    for k, label in factor_names.items():
        v = scores.get(k)
        if v is not None:
            active.append(v)
            details.append(f"{label}{v:+g}")
        else:
            details.append(f"{label}不计")

    n_active = len(active)
    total = sum(active)

    # 构建基础返回
    result = {
        "total": total,
        "n_active": n_active,
        "factor_detail": " | ".join(details),
    }

    if n_active < 3:
        # 数据不足，只输出方向倾向
        if total >= 1.0:
            result["direction"] = "偏多"
        elif total <= -1.0:
            result["direction"] = "偏空"
        else:
            result["direction"] = "震荡"
        result["probability"] = None
        result["confidence"] = "低"
        result["factor_note"] = f"数据不足，仅{n_active}个有效因子"
        return result

    # 概率判断
    if total >= 2.0:
        result["direction"] = "偏多"
        result["probability"] = "70%+"
        result["confidence"] = "高"
    elif total >= 1.0:
        result["direction"] = "偏多"
        result["probability"] = "60%+"
        result["confidence"] = "中"
    elif total <= -2.0:
        result["direction"] = "偏空"
        result["probability"] = "70%+"
        result["confidence"] = "高"
    elif total <= -1.0:
        result["direction"] = "偏空"
        result["probability"] = "60%+"
        result["confidence"] = "中"
    else:
        result["direction"] = "震荡"
        result["probability"] = None
        result["confidence"] = "中"

    return result


# ══════════════════════════════════════════════
# G4: 多周期均线共振评分
# ══════════════════════════════════════════════

def score_multi_timeframe(ma_daily: str, ma_60min: str = None, ma_15min: str = None) -> dict:
    """
    多周期均线共振评分。

    比较日线/60分钟/15分钟的均线排列方向一致性。

    参数：
        ma_daily — ss 中的 ma_pos 值（"多头"/"空头"/"震荡"）
        ma_60min — 60分钟K线的 ma_pos
        ma_15min — 15分钟K线的 ma_pos

    返回：
    {
        "resonance": str,       # "共振向上"/"共振向下"/"方向矛盾"
        "score": int,           # 1=共振向上, -1=共振向下, 0=矛盾
        "detail": str,          # 可读描述
    }

    规则：
    所有周期同向（多头或空头）→ 共振
    如日线多头+60分多头+15分多头 → "共振向上" → +1
    如日线空头+60分空头+15分空头 → "共振向下" → -1
    其他情况 → "方向矛盾" → 0
    """
    positions = []
    labels = []

    if ma_daily:
        positions.append(ma_daily)
        labels.append("日线")
    if ma_60min:
        positions.append(ma_60min)
        labels.append("60分")
    if ma_15min:
        positions.append(ma_15min)
        labels.append("15分")

    if len(positions) < 2:
        return {"resonance": "数据不足", "score": 0, "detail": "需要至少两个周期数据"}

    all_bull = all(p == "多头" for p in positions)
    all_bear = all(p == "空头" for p in positions)

    if all_bull:
        return {"resonance": "共振向上", "score": 1,
                "detail": f"{'/'.join(labels)}均线全部多头排列"}
    elif all_bear:
        return {"resonance": "共振向下", "score": -1,
                "detail": f"{'/'.join(labels)}均线全部空头排列"}
    else:
        return {"resonance": "方向矛盾", "score": 0,
                "detail": f"{'/'.join(labels)}均线方向不一致"}


# ══════════════════════════════════════════════
# G5: 相对强度
# ══════════════════════════════════════════════

# 常用板块指数映射（腾讯行情代码）
# 格式: {行业名: 腾讯代码}
INDUSTRY_INDEX_MAP = {
    "消费电子": "sz399807",
    "半导体": "sz399808",
    "芯片": "sz399812",
    "AI": "sz399815",
    "电力": "sz399815",
    "白酒": "sz399817",
    "医药": "sz399818",
    "新能源": "sz399819",
    "汽车": "sz399820",
    "银行": "sz399821",
    "证券": "sz399822",
    "军工": "sz399823",
    "光伏": "sz399824",
    "机器人": "sz399825",
    # 通用兜底用大盘
}


def relative_strength(
    stock_change: float,
    industry_index_changes: dict = None,
    market_change: float = None
) -> dict:
    """
    个股 vs 板块/大盘的相对强度。

    纯计算函数，数据由调用者传入。

    参数：
        stock_change — 个股涨跌幅（小数，如0.05=+5%）
        industry_index_changes — {板块名: 涨跌幅}（可选）
        market_change — 大盘涨跌幅（可选）

    返回：
    {
        "excess_vs_market": float,     # 超额收益 vs 大盘
        "excess_vs_industry": float,   # 超额收益 vs 板块
        "label_vs_market": str,        # "领涨" / "领跌" / "同步" / "数据不足"
        "label_vs_industry": str,
        "strength_score": int,         # -2~2
    }

    规则：
    excess > 2% → "领涨"
    excess < -2% → "领跌"
    其他 → "同步"

    strength_score = (label_vs_market得分 + label_vs_industry得分)
    领涨=+1, 同步=0, 领跌=-1
    """
    result = {}
    strength = 0

    # vs 大盘
    if market_change is not None:
        excess_market = stock_change - market_change
        if excess_market > 0.02:
            result["label_vs_market"] = "领涨"
            strength += 1
        elif excess_market < -0.02:
            result["label_vs_market"] = "领跌"
            strength -= 1
        else:
            result["label_vs_market"] = "同步"
        result["excess_vs_market"] = round(excess_market * 100, 2)
    else:
        result["excess_vs_market"] = None
        result["label_vs_market"] = "数据不足"

    # vs 板块
    if industry_index_changes:
        # 取第一个板块的涨跌幅
        ind_chg = next(iter(industry_index_changes.values()))
        if ind_chg is not None:
            excess_ind = stock_change - ind_chg
            if excess_ind > 0.02:
                result["label_vs_industry"] = "领涨"
                strength += 1
            elif excess_ind < -0.02:
                result["label_vs_industry"] = "领跌"
                strength -= 1
            else:
                result["label_vs_industry"] = "同步"
            result["excess_vs_industry"] = round(excess_ind * 100, 2)
        else:
            result["excess_vs_industry"] = None
            result["label_vs_industry"] = "数据不足"
    else:
        result["excess_vs_industry"] = None
        result["label_vs_industry"] = "数据不足"

    result["strength_score"] = strength
    return result


def score_relative_strength(rs: dict) -> int:
    """
    将相对强度转为因子分。

    strength_score >= 1 → +1（相对强势）
    strength_score <= -1 → -1（相对弱势）
    其他 → 0
    """
    ss = rs.get("strength_score", 0)
    if ss >= 1:
        return 1
    elif ss <= -1:
        return -1
    return 0


def industry_peer_comparison(
    code: str,
    industry: str,
    peer_quotes: dict = None,
    stock_change: float = None
) -> dict:
    """
    行业/板块内对比——个股 vs 同行的联动分析。

    参数：
        code — 分析标的代码
        industry — 行业名（如 "消费电子代工"）
        peer_quotes — 可选，同行行情 dict {code: {change_pct, name}, ...}
                      如果为空，返回空结果（调用者负责获取数据）
        stock_change — 个股涨跌幅（小数，如-0.083=-8.3%）

    返回：
    {
        "peers_analyzed": int,           # 分析的同行业股票数
        "peer_names": [str],             # 同行名称列表
        "peer_avg_change": float,        # 同行平均涨跌幅
        "peer_max_change": float,        # 同行最大涨幅
        "peer_min_change": float,        # 同行最大跌幅（最小）
        "stock_change": float,           # 个股涨跌幅
        "stock_excess_vs_peers": float,  # 个股超额（个股 - 同行均值）
        "relative_position": str,        # "领涨" / "领跌" / "跟随" / "逆势"
        "top_mover": dict or None,       # {code, name, change} 板块内最强股
        "bottom_mover": dict or None,    # {code, name, change} 板块内最弱股
        "all_negative": bool,            # 是否同行全部下跌
        "all_positive": bool,            # 是否同行全部上涨
        "detail": str,                   # 一句话描述
    }
    """
    if not peer_quotes or not isinstance(peer_quotes, dict):
        return {
            "peers_analyzed": 0, "peer_avg_change": 0,
            "stock_excess_vs_peers": 0, "relative_position": "数据不足",
            "detail": "无同行数据"
        }

    # 过滤有效数据
    valid = {}
    for pk, pv in peer_quotes.items():
        if isinstance(pv, dict) and not pv.get("error") and pv.get("change_pct") is not None:
            if pk != code:  # 去掉自身
                valid[pk] = pv

    if not valid:
        return {
            "peers_analyzed": 0, "peer_avg_change": 0,
            "stock_excess_vs_peers": 0, "relative_position": "数据不足",
            "detail": "无有效同行数据"
        }

    changes = [(c, v.get("change_pct", 0) or 0) for c, v in valid.items()]
    names = [v.get("name", c) for c, v in valid.items()]
    avg_chg = sum(chg for _, chg in changes) / len(changes)
    max_chg = max(chg for _, chg in changes)
    min_chg = min(chg for _, chg in changes)
    top = max(changes, key=lambda x: x[1])
    bottom = min(changes, key=lambda x: x[1])

    sc = stock_change or 0
    excess = sc - avg_chg

    # 相对位置判断
    if abs(excess) < 1.0:
        rel = "跟随"
    elif excess > 3.0:
        rel = "领涨"
    elif excess < -3.0:
        rel = "领跌"
    elif (sc > 0 and avg_chg < 0) or (sc < 0 and avg_chg > 0):
        rel = "逆势"
    else:
        rel = "跟随"

    all_neg = all(chg < 0 for _, chg in changes)
    all_pos = all(chg > 0 for _, chg in changes)

    detail = "板块"
    if all_neg:
        detail += f"普跌(均值{avg_chg:.1f}%)"
    elif all_pos:
        detail += f"普涨(均值{avg_chg:.1f}%)"
    else:
        detail += f"分化(均值{avg_chg:.1f}%)"
    detail += f"，{code}{rel}，偏离{excess:+.1f}%"

    return {
        "peers_analyzed": len(valid),
        "peer_names": names,
        "peer_avg_change": round(avg_chg, 2),
        "peer_max_change": round(max_chg, 2),
        "peer_min_change": round(min_chg, 2),
        "stock_change": sc,
        "stock_excess_vs_peers": round(excess, 2),
        "relative_position": rel,
        "top_mover": {"code": top[0], "name": valid[top[0]].get("name", top[0]), "change": top[1]},
        "bottom_mover": {"code": bottom[0], "name": valid[bottom[0]].get("name", bottom[0]), "change": bottom[1]},
        "all_negative": all_neg,
        "all_positive": all_pos,
        "detail": detail,
    }


__all__ = [
    "score_moving_average", "score_volume", "score_fund_flow",
    "score_events", "score_us", "score_trend_amplitude",
    "compute_total_score", "TIME_WEIGHTS",
    "score_multi_timeframe", "relative_strength", "score_relative_strength",
    "INDUSTRY_INDEX_MAP",
    "industry_peer_comparison",
]
