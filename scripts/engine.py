#!/usr/bin/env python3
"""
分析引擎——一键运行短线分析全流程。
将 9 个手动调用步骤整合为单个函数调用。
"""

from datetime import datetime

from .data import tencent_quote, baidu_kline_with_ma, sina_us_quote, build_short_summary
from .data import compute_atr, compute_rsi, validate_kline, infer_fund_activity, detect_daily_trend
from .data import detect_volatility_regime, assess_market_tradeability, check_limit_status
from .data import detect_momentum_shift, analyze_volume_profile
from .scoring import industry_peer_comparison
from .patterns import detect_candle_patterns, simple_direction
from .scoring import (score_moving_average, score_volume, score_fund_flow,
                      score_events, score_us, score_trend_amplitude,
                      compute_total_score, score_multi_timeframe,
                      relative_strength, score_relative_strength)
from .tracker import record_prediction
from .cache import cache_get, cache_set


def run_analysis(
    code: str,
    name: str = "",
    time_window: str = "盘前",
    fund_flow_net: float = None,
    has_positive_news: bool = False,
    has_negative_news: bool = False,
    industry_name: str = "",
    market_change: float = None,
    industry_change: float = None,
    peer_quotes: dict = None,
    use_cache: bool = True
) -> dict:
    """
    一键运行短线分析全流程。

    步骤：
    1. 获取三指数行情（带缓存）
    2. 获取个股行情（带缓存）
    3. 获取K线+均线（带缓存）
    4. 获取美股（带缓存）
    5. build_short_summary 预处理
    6. validate_kline 数据检查
    7. 检测K线形态
    8. compute_atr 波动率
    9. compute_rsi
    10. 计算6个因子分数
    11. compute_total_score 综合判断
    12. relative_strength 相对强度（有行业数据时）
    13. record_prediction 记录预测
    14. 返回全部结果

    参数说明：
        code — 股票代码（如 "002475"）
        name — 股票名称（如 "立讯精密"）
        time_window — 时间窗口："盘前" / "上午盘" / "午间→下午" / "盘后复盘" / "隔夜/周末"
        fund_flow_net — 资金流向净额（万元，可选）
        has_positive_news — 是否有正面新闻
        has_negative_news — 是否有负面新闻
        industry_name — 行业名（用于相对强度）
        market_change — 大盘涨跌幅（可选）
        industry_change — 板块涨跌幅（可选）
        use_cache — 是否使用缓存（默认True）

    返回：
    {
        "code": str,
        "name": str,
        "time_window": str,
        "summary": {str},                     # build_short_summary 输出
        "kline_valid": dict,                  # validate_kline 输出
        "patterns": [str],                    # detect_candle_patterns 输出
        "simple_direction": str,              # simple_direction 输出
        "atr": dict,                          # compute_atr 输出
        "rsi": dict,                          # compute_rsi 输出
        "factor_scores": {str: int or None},  # 各因子评分
        "verdict": dict,                      # compute_total_score 输出
        "relative_strength": dict or None,     # 相对强度（有数据时）
        "prediction_recorded": bool,          # 是否已记录预测
        "warnings": [str],                    # 所有警告汇总
    }
    """
    # L3: 交易时段感知
    _now = datetime.now()
    _hour = _now.hour
    _minute = _now.minute
    _session_phase = time_window  # 沿用传入的time_window
    if "尾盘" not in _session_phase and _hour == 14 and _minute >= 57:
        _session_phase = "尾盘集合竞价"

    results = {"code": code, "name": name, "time_window": time_window, "session_phase": _session_phase}
    all_warnings = []

    # 1. 获取三指数（缓存）
    index_data = None
    index_cache_key = "index_quotes"
    if use_cache:
        index_data = cache_get(index_cache_key, "market")
    if index_data is None:
        index_raw = tencent_quote(["000001", "399001", "399006"])
        if not index_raw.get("error"):
            index_data = index_raw
            if use_cache:
                cache_set(index_cache_key, index_data, "market")

    # 2. 个股行情（缓存）
    quote = None
    quote_cache_key = f"quote_{code}"
    if use_cache:
        quote = cache_get(quote_cache_key, "quote")
    if quote is None:
        quote_raw = tencent_quote([code])
        if not quote_raw.get("error") and code in quote_raw:
            quote = quote_raw[code]
            if use_cache:
                cache_set(quote_cache_key, quote, "quote")

    # 3. K线（缓存）
    kline = None
    kline_cache_key = f"kline_{code}"
    if use_cache:
        kline = cache_get(kline_cache_key, "kline")
    if kline is None:
        kline = baidu_kline_with_ma(code)
        if not kline.get("error"):
            if use_cache:
                cache_set(kline_cache_key, kline, "kline")

    results["raw_data_available"] = {
        "quote": quote is not None and not (isinstance(quote, dict) and quote.get("error")),
        "kline": kline is not None and not kline.get("error"),
        "index": index_data is not None and not index_data.get("error"),
    }

    # 4. 美股
    us = sina_us_quote()

    # 5. build_short_summary
    ss = build_short_summary(quote, kline, us, index_data)
    results["summary"] = ss

    # 6. validate_kline
    bars = kline.get("bars", []) if kline and not kline.get("error") else []
    kline_valid = validate_kline(bars)
    results["kline_valid"] = kline_valid
    all_warnings.extend(kline_valid.get("warnings", []))

    # 7. K线形态
    patterns = detect_candle_patterns(bars) if bars else []
    results["patterns"] = patterns
    results["simple_direction"] = simple_direction(bars) if bars else "数据不足"

    # 8. ATR
    closes = [b.get("close", 0) for b in bars if b.get("close")] if bars else []
    atr = compute_atr(bars) if bars and len(bars) >= 15 else {"error": True, "detail": "K线不足"}
    results["atr"] = atr

    # 9. RSI
    rsi = compute_rsi(closes) if len(closes) >= 15 else {"error": True, "detail": "数据不足"}
    results["rsi"] = rsi

    # H4: 自动推断资金流（如果未手动传入）
    if fund_flow_net is None:
        fund_info = infer_fund_activity(quote, kline)
        results["fund_activity"] = fund_info
        inferred_fund_score = fund_info.get("net_direction")
    else:
        results["fund_activity"] = None
        inferred_fund_score = fund_flow_net

    # 10. 因子评分
    scores = {
        "ma": score_moving_average(ss),
        "volume": score_volume(ss),
        "fund_flow": score_fund_flow(inferred_fund_score),
        "events": score_events(has_positive_news, has_negative_news),
        "us": score_us(ss.get("us_dir", ""), time_window),
        "trend": score_trend_amplitude(ss.get("trend_5d", 0)),
    }
    results["factor_scores"] = scores

    # 11. 综合判断
    verdict = compute_total_score(scores, time_window)
    results["verdict"] = verdict

    # 12. 相对强度
    if industry_name or market_change is not None:
        rs = relative_strength(
            ss.get("chg", 0) / 100 if ss.get("chg") else 0,
            {industry_name: industry_change} if industry_name and industry_change is not None else None,
            market_change
        )
        results["relative_strength"] = rs
        # 如果相对强度可用，加入因子
        if rs and rs.get("strength_score") is not None:
            rs_score = score_relative_strength(rs)
            if rs_score != 0:
                scores["relative_strength"] = rs_score
                # 重新计算综合判断
                verdict = compute_total_score(scores, time_window)
                results["verdict"] = verdict
    else:
        results["relative_strength"] = None

    # H5: 日级别趋势
    bars_for_trend = kline.get("bars", []) if kline and not kline.get("error") else []
    daily_trend = detect_daily_trend(bars_for_trend)
    results["daily_trend"] = daily_trend

    # K1: 涨跌停板分析
    if quote and isinstance(quote, dict) and not quote.get("error"):
        limit_info = check_limit_status(quote)
        results["limit_status"] = limit_info
    else:
        results["limit_status"] = {"limit_status": "数据不足", "locked_up": False, "locked_down": False}

    # K3: 行业联动分析
    industry_comp = None
    if industry_name and peer_quotes:
        industry_comp = industry_peer_comparison(
            code=code,
            industry=industry_name,
            peer_quotes=peer_quotes,
            stock_change=ss.get("chg", 0) / 100 if ss.get("chg") else 0,
        )
    results["industry_comparison"] = industry_comp

    # L4: 趋势加速/衰减
    _bars = kline.get("bars", []) if kline and not kline.get("error") else []
    if _bars and len(_bars) >= 10:
        momentum = detect_momentum_shift(_bars)
        results["momentum"] = momentum
    else:
        results["momentum"] = {"momentum": "数据不足", "detail": "K线不足"}

    # L1: 成交量能深度分析
    if _bars and len(_bars) >= 10:
        vp = analyze_volume_profile(_bars, ss.get("vr", None))
        results["volume_profile"] = vp
    else:
        results["volume_profile"] = {"volume_pattern": "数据不足", "detail": "K线不足"}

    # J3: 市场可交易性
    market = assess_market_tradeability(index_data)
    results["market_tradeability"] = market

    # J4: 自动交易计划
    trade_plan = {}
    verdict_dir = verdict.get("direction", "震荡")
    p = ss.get("p", 0)
    atr = results.get("atr", {})

    if isinstance(atr, dict) and not atr.get("error") and p > 0:
        atr_pct = atr.get("atr_pct", 0)

        if verdict_dir == "偏多":
            entry_area = f"{ss.get('S2', 0):.2f}~{ss.get('S1', 0):.2f}"
            sl = atr.get("stop_loss_aggressive", 0)
            sl_pct = ((p - sl) / p * 100) if p > 0 and sl > 0 and sl < p else atr_pct * 2
            tp = atr.get("take_profit_short", 0)

            trade_plan = {
                "方向": "做多",
                "入场参考": entry_area,
                "止损价": f"{sl:.2f}",
                "止损幅度": f"{sl_pct:.1f}%",
                "止盈价(短线)": f"{tp:.2f}",
                "止盈幅度": f"{(tp-p)/p*100:.1f}%" if tp > p else "-",
                "波动率环境": detect_volatility_regime(atr_pct),
                "市场环境": market.get("sentiment", "中性"),
            }
        elif verdict_dir == "偏空":
            sl = p + atr.get("atr", 0) * 2  # 做空止损=价格+ATR×2
            sl_pct = ((sl - p) / p * 100) if p > 0 else 0
            tp = p - atr.get("atr", 0) * 1.5  # 做空止盈

            trade_plan = {
                "方向": "做空",
                "入场参考": f"{p:.2f}",
                "止损价": f"{sl:.2f}",
                "止损幅度": f"{sl_pct:.1f}%",
                "止盈价(短线)": f"{max(tp, 0):.2f}",
                "波动率环境": detect_volatility_regime(atr_pct),
                "市场环境": market.get("sentiment", "中性"),
            }
        else:
            trade_plan = {"方向": "观望", "reason": "信号不足", "市场环境": market.get("sentiment", "中性")}

    # 高波动时降级交易计划
    if not market.get("tradeable", True):
        if trade_plan.get("方向") in ("做多", "做空"):
            trade_plan["方向"] = "观望(高波动)"
            trade_plan["reason"] = market.get("detail", "高波动不适合短线")

    # 尾盘竞价提示
    if _session_phase == "尾盘集合竞价":
        trade_plan["⚠️ 尾盘竞价提醒"] = "当前处于尾盘集合竞价阶段(14:57-15:00)，最终收盘价可能偏离当前价"

    results["trade_plan"] = trade_plan

    # 13. 记录预测
    try:
        record_prediction(
            code=code,
            name=name or code,
            direction=verdict.get("direction", "震荡"),
            confidence=verdict.get("probability", 0.5) if verdict.get("probability") else 0.5,
            price=ss.get("p", 0),
            factor_detail=verdict.get("factor_detail", ""),
            source="temp-omni-engine"
        )
        results["prediction_recorded"] = True
    except:
        results["prediction_recorded"] = False

    # 14. 警告汇总
    if not results["raw_data_available"]["quote"]:
        all_warnings.append("行情数据不可用")
    if not results["raw_data_available"]["kline"]:
        all_warnings.append("K线数据不可用")
    if verdict.get("n_active", 0) < 3:
        all_warnings.append(f"仅{verdict.get('n_active',0)}个有效因子，数据不足")
    results["warnings"] = all_warnings

    return results


def summarize_analysis(result: dict) -> str:
    """
    从 run_analysis 的输出中自动生成一句话分析摘要。

    参数 result: run_analysis() 返回的完整 dict
    返回: 一句话摘要字符串

    模板：
    "{name}({code}) 当前{price}({chg:+.2f}%)，均线{ma_pos}，{momentum}，{volume_pattern}。
     市场{market_sentiment}，{limit_status}。综合判断{verdict_direction}，
     入场{entry}止损{sl}止盈{tp}"
    """
    parts = []

    # 标的 + 价格
    code = result.get("code", "")
    name = result.get("name", code)
    ss = result.get("summary", {})
    price = ss.get("p", 0)
    chg = ss.get("chg", 0)
    parts.append(f"{name}({code}) 当前{price}({chg:+.2f}%)")

    # 技术面
    ma_pos = ss.get("ma_pos", "")
    if ma_pos:
        parts.append(f"均线{ma_pos}")

    momentum = result.get("momentum", {})
    if isinstance(momentum, dict):
        m = momentum.get("momentum", "")
        if m and "数据不足" not in m:
            parts.append(m)

    vp = result.get("volume_profile", {})
    if isinstance(vp, dict):
        vp_pat = vp.get("volume_pattern", "")
        if vp_pat and "数据不足" not in vp_pat:
            parts.append(vp_pat)

    limit = result.get("limit_status", {})
    if isinstance(limit, dict):
        ls = limit.get("limit_status", "")
        if ls and ls != "正常" and "数据不足" not in ls:
            parts.append(f"⚠{ls}")

    # 市场环境
    market = result.get("market_tradeability", {})
    if isinstance(market, dict):
        ms = market.get("sentiment", "")
        if ms and ms != "数据不足":
            parts.append(f"市场{ms}")

    # 综合判断
    verdict = result.get("verdict", {})
    direction = verdict.get("direction", "")
    prob = verdict.get("probability", "")
    if direction:
        prob_str = f"({prob})" if prob else ""
        parts.append(f"判断{direction}{prob_str}")

    # 交易计划
    plan = result.get("trade_plan", {})
    if isinstance(plan, dict):
        entry = plan.get("入场参考", "")
        sl = plan.get("止损价", "")
        tp = plan.get("止盈价(短线)", "")
        if entry:
            parts.append(f"入场{entry}")
        if sl:
            parts.append(f"止损{sl}")
        if tp and tp != "-":
            parts.append(f"止盈{tp}")

    return "，".join(parts) + "。"
