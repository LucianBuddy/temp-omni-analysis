#!/usr/bin/env python3
"""
短线信号历史回测模块。
验证 temp-omni 评分系统在历史上的预测准确率。

注意：回测是简化的——因为回放时无法获取真实的历史美股行情和新闻数据，
所以只用了技术面因子（均线）。这是一个"技术面因子单独回测"，
结果会略低于完整方案的准确率。
"""

from .data import baidu_kline_with_ma, build_short_summary, sina_us_quote
from .data import compute_atr, compute_rsi, detect_daily_trend, check_limit_status
from .scoring import (score_moving_average, score_volume, score_fund_flow,
                      score_events, score_us, score_trend_amplitude,
                      compute_total_score)


def backtest_short_term(code: str, lookback: int = 120) -> dict:
    """
    短线信号历史回测。

    在历史数据中逐日回放评分逻辑：
    1. 每日用当天可用数据计算因子分数
    2. 记录 verdict（偏多/偏空/震荡）
    3. 对比次日实际涨跌

    参数：
        code — 股票代码
        lookback — 回测使用的K线天数（默认120个交易日）

    返回：
    {
        "code": str,
        "total_days": int,                  # 总回测天数
        "signals_issued": int,              # 发出信号（非震荡）的天数
        "bullish": {                        # 偏多信号表现
            "count": int,
            "correct": int,
            "accuracy": float,
            "avg_following_return": float,  # 信号后次日均收益
        },
        "bearish": {                        # 偏空信号表现
            "count": int,
            "correct": int,
            "accuracy": float,
            "avg_following_return": float,
        },
        "neutral": {                        # 震荡信号表现
            "count": int,
            "correct": int,
            "accuracy": float,
        },
        "overall": {
            "accuracy": float,
            "avg_return": float,
            "max_consecutive_losses": int,
            "profit_factor": float,          # 盈利总和/亏损总和
        },
        "monthly": [                         # 按月分拆
            {"month": "2026-01", "signals": int, "accuracy": float}, ...
        ],
        "vs_benchmark": {                   # 与买入持有对比
            "strategy_return": float,       # 信号驱动策略收益
            "buy_hold_return": float,       # 买入持有收益
            "excess_return": float,
        },
        "detail": str,
    }

    实现要点：
    - 数据来源：baidu_kline_with_ma（已有）
    - 每日滚动：索引第 day 天，用前 up_to_day 天数据
    - 评分逻辑：直接复用 scoring.py 的纯计算函数
    - 仅基于技术面因子（均线），回放无法获取实时美股/新闻数据
    """
    # 获取K线数据
    kline = baidu_kline_with_ma(code)
    if kline.get("error") or not kline.get("bars"):
        return {"error": True, "detail": "K线数据不可用"}

    bars = kline.get("bars", [])
    if len(bars) < lookback:
        lookback = len(bars)

    if lookback < 20:
        return {"error": True, "detail": f"K线不足(需要20，实际{lookback})"}

    # 从K线中提前提取 closes
    all_closes = [b.get("close", 0) for b in bars if b.get("close")]

    results = {
        "code": code, "total_days": 0, "signals_issued": 0,
        "bullish": {"count": 0, "correct": 0, "accuracy": 0, "avg_following_return": 0},
        "bearish": {"count": 0, "correct": 0, "accuracy": 0, "avg_following_return": 0},
        "neutral": {"count": 0, "correct": 0, "accuracy": 0},
        "overall": {"accuracy": 0, "avg_return": 0, "max_consecutive_losses": 0, "profit_factor": 0},
        "monthly": [],
        "vs_benchmark": {"strategy_return": 0, "buy_hold_return": 0, "excess_return": 0},
    }

    # 逐日回放（从第20天开始，确保有足够历史数据）
    daily_records = []

    for day in range(20, lookback - 1):  # -1 因为最后一天需要下一日数据验证
        # 当天数据
        up_to_bars = bars[:day+1]
        current_bar = bars[day]
        next_bar = bars[day+1]

        current_close = current_bar.get("close", 0)
        next_close = next_bar.get("close", 0)

        if current_close <= 0 or next_close <= 0:
            continue

        # 模拟build_short_summary的部分计算
        # 简化版：只用可用的K线数据
        day_closes = [b.get("close", 0) for b in up_to_bars if b.get("close")]

        # 计算简单的技术指标（不依赖外部API）
        if len(day_closes) >= 5:
            ma5 = sum(day_closes[-5:]) / 5
        else:
            ma5 = current_close

        if len(day_closes) >= 10:
            ma10 = sum(day_closes[-10:]) / 10
        else:
            ma10 = current_close

        if len(day_closes) >= 20:
            ma20 = sum(day_closes[-20:]) / 20
        else:
            ma20 = current_close

        # 模拟ss字典
        ss = {
            "p": current_close,
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "chg": 0,  # 回测中无法获取当日涨跌幅
            "vr": 1.0,
            "us_dir": "数据不可用",  # 回测无法获取历史美股
        }

        # 计算因子分数
        scores = {
            "ma": score_moving_average(ss),
            "volume": 0,
            "fund_flow": None,
            "events": None,
            "us": None,
            "trend": 0,
        }

        verdict = compute_total_score(scores, "盘前")

        # 计算次日实际涨跌幅
        next_day_return = (next_close - current_close) / current_close

        # 判断信号是否正确
        direction = verdict.get("direction", "震荡")
        is_correct = False
        if direction == "偏多" and next_day_return > 0.01:
            is_correct = True
        elif direction == "偏空" and next_day_return < -0.01:
            is_correct = True
        elif direction == "震荡" and abs(next_day_return) < 0.02:
            is_correct = True

        daily_records.append({
            "date": current_bar.get("date", ""),
            "direction": direction,
            "score": verdict.get("total", 0),
            "next_return": round(next_day_return * 100, 2),
            "correct": is_correct,
        })

    # 汇总统计
    if not daily_records:
        return {"error": True, "detail": "无有效回测记录"}

    total = len(daily_records)
    results["total_days"] = total

    by_dir = {"偏多": [], "偏空": [], "震荡": []}
    for r in daily_records:
        by_dir[r["direction"]].append(r)

    for dir_name, records in by_dir.items():
        if dir_name == "偏多":
            key = "bullish"
        elif dir_name == "偏空":
            key = "bearish"
        else:
            key = "neutral"

        n = len(records)
        correct = sum(1 for r in records if r["correct"])
        acc = correct / n if n > 0 else 0
        avg_ret = sum(r["next_return"] for r in records) / n if n > 0 else 0

        results[key] = {
            "count": n,
            "correct": correct,
            "accuracy": round(acc, 4),
            "avg_following_return": round(avg_ret, 4),
        }
        results["signals_issued"] += n

    # 总体
    total_correct = sum(r["correct"] for r in daily_records)
    total_return = sum(r["next_return"] for r in daily_records)
    results["overall"] = {
        "accuracy": round(total_correct / total, 4),
        "avg_return": round(total_return / total, 4),
        "max_consecutive_losses": 0,
        "profit_factor": 0,
    }

    # 最大连续错误
    max_loss_streak = 0
    current_streak = 0
    for r in daily_records:
        if not r["correct"]:
            current_streak += 1
            max_loss_streak = max(max_loss_streak, current_streak)
        else:
            current_streak = 0
    results["overall"]["max_consecutive_losses"] = max_loss_streak

    # 盈亏比
    gains = sum(r["next_return"] for r in daily_records if r["next_return"] > 0)
    losses = abs(sum(r["next_return"] for r in daily_records if r["next_return"] < 0))
    results["overall"]["profit_factor"] = round(gains / losses, 2) if losses > 0 else 0

    # 按月分拆
    monthly_data = {}
    for r in daily_records:
        month = r["date"][:7] if r["date"] else "unknown"
        if month not in monthly_data:
            monthly_data[month] = {"signals": 0, "correct": 0}
        monthly_data[month]["signals"] += 1
        if r["correct"]:
            monthly_data[month]["correct"] += 1

    results["monthly"] = [
        {"month": m, "signals": d["signals"],
         "accuracy": round(d["correct"]/d["signals"], 2)}
        for m, d in sorted(monthly_data.items())
    ]

    # vs 买入持有
    buy_hold_return = (all_closes[lookback-1] - all_closes[19]) / all_closes[19] * 100 \
        if all_closes[lookback-1] > 0 and all_closes[19] > 0 else 0
    results["vs_benchmark"]["buy_hold_return"] = round(buy_hold_return, 2)
    results["vs_benchmark"]["strategy_return"] = round(total_return, 2)
    results["vs_benchmark"]["excess_return"] = round(total_return - buy_hold_return, 2)

    results["detail"] = (f"回测{total}天，发出{results['signals_issued']}次信号。"
                         f"偏多准确率{results['bullish']['accuracy']:.0%}"
                         f"({results['bullish']['correct']}/{results['bullish']['count']}) | "
                         f"偏空准确率{results['bearish']['accuracy']:.0%}"
                         f"({results['bearish']['correct']}/{results['bearish']['count']}) | "
                         f"总准确率{results['overall']['accuracy']:.0%}"
                         f"（仅基于技术面因子）")

    return results


def print_backtest_report(result: dict) -> str:
    """
    格式化输出回测报告。
    """
    if result.get("error"):
        return f"回测失败: {result.get('detail', '')}"

    lines = []
    lines.append(f"=== 短线信号回测报告: {result['code']} ===")
    lines.append(f"回测周期: {result['total_days']}个交易日")
    lines.append(f"（注意：仅基于技术面因子，不含美股/新闻数据，结果低于完整方案）")
    lines.append(f"")
    lines.append(f"信号准确率:")
    lines.append(f"  偏多: {result['bullish']['accuracy']:.1%} "
                 f"({result['bullish']['correct']}/{result['bullish']['count']}) "
                 f"均收益:{result['bullish']['avg_following_return']:+.2f}%")
    lines.append(f"  偏空: {result['bearish']['accuracy']:.1%} "
                 f"({result['bearish']['correct']}/{result['bearish']['count']}) "
                 f"均收益:{result['bearish']['avg_following_return']:+.2f}%")
    lines.append(f"  震荡: {result['neutral']['accuracy']:.1%} "
                 f"({result['neutral']['correct']}/{result['neutral']['count']})")
    lines.append(f"  总体: {result['overall']['accuracy']:.1%}")
    lines.append(f"")
    lines.append(f"策略收益: {result['vs_benchmark']['strategy_return']:+.2f}% "
                 f"vs 买入持有:{result['vs_benchmark']['buy_hold_return']:+.2f}%")
    lines.append(f"超额收益: {result['vs_benchmark']['excess_return']:+.2f}%")
    lines.append(f"最大连败: {result['overall']['max_consecutive_losses']}次 | "
                 f"盈亏比:{result['overall']['profit_factor']}")

    return "\n".join(lines)
