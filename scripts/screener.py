#!/usr/bin/env python3
"""
批量筛选模块——多只股票对比排序。
从 run_analysis 的基础上，支持批量分析并排序。
"""

from typing import List, Dict, Optional

from .engine import run_analysis
from .data import detect_daily_trend, detect_volatility_regime


def screen_stocks(
    stock_list,
    time_window="盘前",
    use_cache=True,
    max_workers=1,
    min_n_active=3
):
    """
    批量筛选股票，按信号强度排序。

    stock_list: [
        {"code": "002475", "name": "立讯精密", "industry": "消费电子代工",
         "market_change": 0.01, "industry_change": 0.02},
        {"code": "601138", "name": "工业富联", "industry": "消费电子代工"},
        ...
    ]

    对每只股票调用 run_analysis()。

    返回：
    {
        "total": int,                         # 分析总数
        "success": int,                       # 成功数
        "failed": int,                        # 失败数
        "errors": [{"code": str, "error": str}],  # 失败原因
        "ranked": [                           # 按信号强度排序
            {
                "rank": int,
                "code": str,
                "name": str,
                "direction": str,              # "偏多"/"偏空"/"震荡"
                "total_score": float,          # verdict.total
                "n_active": int,               # 有效因子数
                "confidence": float,           # 置信度
                "rsi_signal": str,             # RSI信号
                "atr_regime": str,             # 波动率环境
                "ma_pos": str,                 # 均线排列
                "daily_trend": str,            # 日级别趋势
                "alerts_count": int,           # 触发的预警数
            },
            ...
        ],
        "best": {                              # 最佳信号
            "code": str,
            "name": str,
            "direction": str,
            "total_score": float,
            "reason": str,                     # 一句话原因
        },
        "summary": str,                        # 一句话概括
    }

    排序规则：
    1. 方向优先级：偏多 > 震荡 > 偏空
    2. 同方向：total_score 降序
    3. 同分：n_active 降序（更多有效因子=更可靠）
    4. 同分同n：atr_regime非"高波动"优先
    """
    results = {"total": len(stock_list), "success": 0, "failed": 0,
               "errors": [], "ranked": [], "best": None, "summary": ""}

    for item in stock_list:
        code = item.get("code", "")
        name = item.get("name", code)
        try:
            result = run_analysis(
                code=code,
                name=name,
                time_window=time_window,
                industry_name=item.get("industry", ""),
                market_change=item.get("market_change"),
                industry_change=item.get("industry_change"),
                use_cache=use_cache,
            )

            verdict = result.get("verdict", {})
            ss = result.get("summary", {})
            rsi = result.get("rsi", {})
            atr = result.get("atr", {})
            alerts = result.get("alerts", [])
            daily_trend = result.get("daily_trend", {})

            entry = {
                "code": code,
                "name": name,
                "direction": verdict.get("direction", "震荡"),
                "total_score": verdict.get("total", 0),
                "n_active": verdict.get("n_active", 0),
                "confidence": verdict.get("probability", 0.5) if verdict.get("probability") else 0.5,
                "rsi_signal": rsi.get("signal", "数据不足") if isinstance(rsi, dict) else "数据不足",
                "atr_regime": "数据不足",
                "ma_pos": ss.get("ma_pos", "数据不足"),
                "daily_trend": daily_trend.get("trend", "数据不足") if isinstance(daily_trend, dict) else "数据不足",
                "alerts_count": len(alerts) if alerts else 0,
            }

            # ATR regime
            if isinstance(atr, dict) and not atr.get("error"):
                atr_pct = atr.get("atr_pct", 0)
                entry["atr_regime"] = detect_volatility_regime(atr_pct)

            # 检查n_active >= min_n_active
            if entry["n_active"] >= min_n_active:
                results["ranked"].append(entry)
            results["success"] += 1

        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"code": code, "error": str(e)})

    # 排序
    direction_priority = {"偏多": 0, "震荡": 1, "偏空": 2}
    results["ranked"].sort(key=lambda x: (
        direction_priority.get(x["direction"], 9),
        -x["total_score"],
        -x["n_active"],
        0 if x["atr_regime"] != "高波动" else 1,
    ))

    # 排名
    for i, item in enumerate(results["ranked"]):
        item["rank"] = i + 1

    # 最佳信号
    if results["ranked"]:
        best = results["ranked"][0]
        results["best"] = {
            "code": best["code"],
            "name": best["name"],
            "direction": best["direction"],
            "total_score": best["total_score"],
            "reason": f"{best['direction']}(总分{best['total_score']}), 均线{best['ma_pos']}, RSI{best['rsi_signal']}",
        }

    # 一句话概括
    if results["failed"] > 0:
        results["summary"] = f"分析{results['total']}只, {results['success']}成功{results['failed']}失败"
    elif results["ranked"]:
        best = results["best"]
        results["summary"] = f"{results['total']}只分析完成。最佳:{best['name']}({best['code']}) {best['reason']}"
    else:
        results["summary"] = f"分析{results['total']}只, 无有效信号"

    return results


def screen_and_backtest(
    stock_list,
    time_window="盘前",
    top_n=3,
    use_cache=True,
    min_n_active=3
):
    """
    批量筛选后对 Top N 做回测验证。

    流程：
    1. screen_stocks() → 按信号强度排序
    2. 对前 top_n 只调用 backtest_short_term()
    3. 合并结果输出

    返回：
    {
        "screen_result": dict,          # screen_stocks 的原始输出
        "total_screened": int,
        "backtested_top": [
            {
                "code": str,
                "name": str,
                "screen_rank": int,
                "screen_direction": str,
                "screen_score": float,
                "backtest_bullish_accuracy": float,
                "backtest_bearish_accuracy": float,
                "backtest_overall_accuracy": float,
                "backtest_return": float,
                "signals_consistent": bool,   # 筛选方向 vs 回测优势方向一致?
                "final_verdict": str,          # "强推荐" / "弱推荐" / "不推荐"
                "reason": str,
            },
            ...
        ],
        "recommendations": [str],        # 最终推荐列表（"强推荐"的标的）
        "summary": str,
    }

    决策逻辑：
    - 筛选方向="偏多" 且 回测偏多准确率>60% → "强推荐"
    - 筛选方向="偏多" 且 回测偏多准确率>50% → "弱推荐"
    - 筛选方向="偏空" 且 回测偏空准确率>60% → "强推荐"
    - 筛选方向="偏空" 且 回测偏空准确率>50% → "弱推荐"
    - 其他 → "不推荐"
    """
    from .backtest_st import backtest_short_term

    # 1. 先筛选
    screen_result = screen_stocks(
        stock_list=stock_list,
        time_window=time_window,
        use_cache=use_cache,
        min_n_active=min_n_active,
    )

    results = {
        "screen_result": screen_result,
        "total_screened": len(stock_list),
        "backtested_top": [],
        "recommendations": [],
        "summary": "",
    }

    # 2. 对 Top N 回测
    ranked = screen_result.get("ranked", [])
    for item in ranked[:top_n]:
        code = item.get("code", "")
        name = item.get("name", code)
        screen_dir = item.get("direction", "")
        screen_score = item.get("total_score", 0)
        rank = item.get("rank", 0)

        try:
            bt = backtest_short_term(code, lookback=120)

            if bt.get("error"):
                results["backtested_top"].append({
                    "code": code, "name": name, "screen_rank": rank,
                    "screen_direction": screen_dir, "screen_score": screen_score,
                    "backtest_error": bt.get("detail", "回测失败"),
                    "final_verdict": "数据不足", "reason": "回测失败",
                })
                continue

            bullish_acc = bt.get("bullish", {}).get("accuracy", 0)
            bearish_acc = bt.get("bearish", {}).get("accuracy", 0)
            overall_acc = bt.get("overall", {}).get("accuracy", 0)
            bt_return = bt.get("vs_benchmark", {}).get("strategy_return", 0)

            # 方向一致性判断
            if screen_dir == "偏多":
                signals_consistent = bullish_acc >= 0.5
                if bullish_acc > 0.6:
                    final_verdict = "强推荐"
                    reason = f"回测看多准确率{bullish_acc:.0%}"
                elif bullish_acc > 0.5:
                    final_verdict = "弱推荐"
                    reason = f"回测看多准确率{bullish_acc:.0%}"
                else:
                    final_verdict = "不推荐"
                    reason = f"回测看多准确率仅{bullish_acc:.0%}"
            elif screen_dir == "偏空":
                signals_consistent = bearish_acc >= 0.5
                if bearish_acc > 0.6:
                    final_verdict = "强推荐"
                    reason = f"回测看空准确率{bearish_acc:.0%}"
                elif bearish_acc > 0.5:
                    final_verdict = "弱推荐"
                    reason = f"回测看空准确率{bearish_acc:.0%}"
                else:
                    final_verdict = "不推荐"
                    reason = f"回测看空准确率仅{bearish_acc:.0%}"
            else:
                signals_consistent = True
                final_verdict = "不推荐"
                reason = "震荡信号，无明确方向"

            entry = {
                "code": code,
                "name": name,
                "screen_rank": rank,
                "screen_direction": screen_dir,
                "screen_score": screen_score,
                "backtest_bullish_accuracy": round(bullish_acc, 4),
                "backtest_bearish_accuracy": round(bearish_acc, 4),
                "backtest_overall_accuracy": round(overall_acc, 4),
                "backtest_return": round(bt_return, 2),
                "signals_consistent": signals_consistent,
                "final_verdict": final_verdict,
                "reason": reason,
            }
            results["backtested_top"].append(entry)

            if final_verdict == "强推荐":
                results["recommendations"].append(f"{name}({code})")

        except Exception as e:
            results["backtested_top"].append({
                "code": code, "name": name, "screen_rank": rank,
                "screen_direction": screen_dir, "screen_score": screen_score,
                "final_verdict": "回测异常", "reason": str(e),
            })

    # 3. 摘要
    if results["recommendations"]:
        results["summary"] = (f"共筛选{len(stock_list)}只，回测前{top_n}只。"
                             f"强推荐: {', '.join(results['recommendations'])}")
    else:
        results["summary"] = (f"共筛选{len(stock_list)}只，回测前{top_n}只。"
                             f"无强推荐标的")

    return results


def print_screen_results(screen_result: dict) -> str:
    """
    将筛选结果格式化为可读文本。

    返回字符串格式：

    === 批量筛选结果 ===
    共分析5只股票，5只成功

    排名 代码   名称       方向  总分 因子 均线  RSI      ATR
    ───────────────────────────────────────────────
    1    002475 立讯精密  偏多  2.0  4    多头  正常偏弱 正常波动
    2    601138 工业富联  震荡  0.0  3    震荡  正常偏弱 正常波动
    3    600406 国电南瑞  偏空  -1.0 3    空头  正常偏弱 低波动

    最佳信号: 002475 立讯精密 — 偏多(总分2.0)
    """
    if not screen_result:
        return "无结果"

    lines = []
    lines.append("=== 批量筛选结果 ===")
    lines.append(f"共分析{screen_result['total']}只股票，{screen_result['success']}只成功"
                 f"{'，'+str(screen_result['failed'])+'只失败' if screen_result['failed'] else ''}")
    lines.append("")

    ranked = screen_result.get("ranked", [])
    if ranked:
        # 表头
        header = f"{'排名':<4} {'代码':<7} {'名称':<10} {'方向':<4} {'总分':<5} {'因子':<4} {'均线':<6} {'RSI':<10} {'ATR':<8}"
        lines.append(header)
        lines.append("─" * len(header))

        for item in ranked:
            lines.append(
                f"{item['rank']:<4} {item['code']:<7} {item['name']:<10} "
                f"{item['direction']:<4} {item['total_score']:<5} {item['n_active']:<4} "
                f"{item['ma_pos']:<6} {item['rsi_signal']:<10} {item['atr_regime']:<8}"
            )
        lines.append("")

    best = screen_result.get("best")
    if best:
        lines.append(f"最佳信号: {best['code']} {best['name']} — {best['reason']}")

    if screen_result.get("errors"):
        lines.append("")
        lines.append("失败明细:")
        for err in screen_result["errors"]:
            lines.append(f"  {err['code']}: {err['error']}")

    return "\n".join(lines)
