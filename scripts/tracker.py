#!/usr/bin/env python3
"""
短线预测记录与复盘模块。
让 temp-omni 从"用完即弃"变为"可追溯"。
"""

import json
import os
import time
from datetime import datetime, timedelta

RECORDS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "predictions.json"
)


def _load_records() -> list:
    """加载预测记录文件"""
    try:
        if os.path.exists(RECORDS_FILE):
            with open(RECORDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return []


def _save_records(records: list):
    """保存预测记录到文件"""
    try:
        os.makedirs(os.path.dirname(RECORDS_FILE), exist_ok=True)
        with open(RECORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except (IOError, OSError):
        pass


def record_prediction(code: str, name: str, direction: str,
                      confidence: float, price: float,
                      factor_detail: str = "", source: str = "temp-omni") -> dict:
    """
    记录一次短线预测。

    参数：
        code — 股票代码
        name — 股票名称
        direction — "偏多"/"偏空"/"震荡"
        confidence — 置信度（0~1）
        price — 当前价
        factor_detail — 因子详情字符串
        source — 来源（默认temp-omni）

    记录格式：
    {
        "date": "2026-06-26",
        "code": "002475",
        "name": "立讯精密",
        "direction": "偏多",
        "confidence": 0.6,
        "price": 74.42,
        "factor_detail": "均线+1,量价0,美股-1",
        "source": "temp-omni",
        "result": null,        # 3日后回填
        "result_price": null,  # 3日后价格
        "result_chg": null,    # 3日涨跌幅
    }

    返回刚插入的记录 dict。
    """
    records = _load_records()
    record = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "code": code,
        "name": name,
        "direction": direction,
        "confidence": confidence if isinstance(confidence, (int, float)) else 0.5,
        "price": price,
        "factor_detail": factor_detail,
        "source": source,
        "result": None,
        "result_price": None,
        "result_chg": None,
    }
    records.append(record)
    _save_records(records)
    return record


def fill_result(code: str, date: str, current_price: float):
    """
    回填预测结果（3日后调用）。

    查找 code + date 匹配的未完成记录，计算涨跌幅。
    """
    records = _load_records()
    for r in records:
        if r["code"] == code and r["date"] == date and r["result"] is None:
            entry_price = r["price"]
            if entry_price and entry_price > 0:
                chg = (current_price - entry_price) / entry_price
                r["result"] = "正确" if (chg > 0.01 and r["direction"] == "偏多") or \
                                        (chg < -0.01 and r["direction"] == "偏空") else "错误"
                r["result_price"] = current_price
                r["result_chg"] = round(chg, 4)
    _save_records(records)


def review_accuracy(days: int = 30) -> dict:
    """
    统计最近 days 天的预测准确率。

    返回：
    {
        "total": int,
        "filled": int,          # 已有结果的记录数
        "pending": int,         # 等待结果的记录数
        "correct": int,
        "accuracy": float,      # 准确率
        "by_direction": {       # 按方向分拆
            "偏多": {"total": int, "correct": int, "accuracy": float},
            "偏空": {"total": int, "correct": int, "accuracy": float},
            "震荡": {"total": int, "correct": int, "accuracy": float},
        },
        "avg_confidence": float,  # 平均置信度
        "confidence_accuracy": {  # 置信度 vs 准确率
            "高": {"total": int, "accuracy": float},
            "中": {"total": int, "accuracy": float},
            "低": {"total": int, "accuracy": float},
        },
        "period": str,
    }
    """
    cutoff = datetime.now() - timedelta(days=days)
    records = _load_records()
    filtered = [r for r in records if datetime.strptime(r["date"], "%Y-%m-%d") >= cutoff]

    if not filtered:
        return {
            "total": 0, "filled": 0, "pending": 0, "correct": 0,
            "accuracy": 0.0,
            "by_direction": {},
            "avg_confidence": 0.0,
            "confidence_accuracy": {"高": {"total": 0, "accuracy": 0.0},
                                    "中": {"total": 0, "accuracy": 0.0},
                                    "低": {"total": 0, "accuracy": 0.0}},
            "period": f"最近{days}天",
        }

    total = len(filtered)
    filled = [r for r in filtered if r["result"] is not None]
    pending = total - len(filled)
    correct = sum(1 for r in filled if r["result"] == "正确")
    accuracy = correct / len(filled) * 100 if filled else 0.0

    # 按方向
    by_dir = {}
    for d in ["偏多", "偏空", "震荡"]:
        subset = [r for r in filled if r["direction"] == d]
        by_dir[d] = {
            "total": len(subset),
            "correct": sum(1 for r in subset if r["result"] == "正确"),
        }
        by_dir[d]["accuracy"] = by_dir[d]["correct"] / by_dir[d]["total"] * 100 \
            if by_dir[d]["total"] > 0 else 0.0

    # 平均置信度
    confs = [r.get("confidence", 0.5) for r in filtered if r.get("confidence") is not None]
    avg_conf = sum(confs) / len(confs) if confs else 0.0

    # 置信度分拆
    conf_acc = {"高": {"total": 0, "accuracy": 0.0},
                "中": {"total": 0, "accuracy": 0.0},
                "低": {"total": 0, "accuracy": 0.0}}
    for label, thresh in [("高", 0.7), ("中", 0.4), ("低", 0.0)]:
        subset = [r for r in filled if r.get("confidence", 0) >= thresh]
        if label == "高":
            pass  # >=0.7
        elif label == "中":
            subset = [r for r in filled if 0.4 <= r.get("confidence", 0) < 0.7]
        elif label == "低":
            subset = [r for r in filled if r.get("confidence", 0) < 0.4]
        c = sum(1 for r in subset if r["result"] == "正确")
        conf_acc[label] = {
            "total": len(subset),
            "accuracy": c / len(subset) * 100 if subset else 0.0,
        }

    return {
        "total": total, "filled": len(filled), "pending": pending,
        "correct": correct, "accuracy": accuracy,
        "by_direction": by_dir,
        "avg_confidence": avg_conf,
        "confidence_accuracy": conf_acc,
        "period": f"最近{days}天",
    }


def report_bias(result: dict) -> str:
    """
    分析系统偏差。

    检查：
    - 偏多 vs 偏空比例（偏多>偏空*2=有看多倾向）
    - 高置信度方向的准确率 vs 低置信度
    """
    lines = []
    by_dir = result.get("by_direction", {})
    duokong = by_dir.get("偏多", {}).get("total", 0)
    kong = by_dir.get("偏空", {}).get("total", 0)

    if duokong > kong * 2 and kong > 0:
        lines.append(f"偏多预测({duokong}次) 远多于 偏空预测({kong}次) → 有看多倾向")
    elif duokong > kong:
        lines.append(f"偏多预测({duokong}次) 多于 偏空预测({kong}次) → 略有看多倾向")
    elif kong > duokong:
        lines.append(f"偏空预测({kong}次) 多于 偏多预测({duokong}次) → 有看空倾向")
    else:
        lines.append("偏多/偏空预测数量基本平衡")

    # 高置信度 vs 低置信度
    conf = result.get("confidence_accuracy", {})
    high = conf.get("高", {})
    low = conf.get("低", {})
    if high.get("total", 0) >= 3 and low.get("total", 0) >= 3:
        if high.get("accuracy", 0) > low.get("accuracy", 0) + 10:
            lines.append("高置信度预测准确率显著高于低置信度 → 置信度校准良好")
        elif high.get("accuracy", 0) < low.get("accuracy", 0):
            lines.append("高置信度预测准确率低于低置信度 → 置信度校准异常，需要检查")

    return "系统偏差分析:\n" + "\n".join(f"  {l}" for l in lines) if lines else "系统偏差分析: 数据不足以判断"


def print_review(days: int = 30) -> str:
    """
    输出可读复盘报告。
    """
    result = review_accuracy(days)
    lines = []
    lines.append(f"=== temp-omni 预测复盘 (最近{days}天) ===")
    lines.append(f"总计预测: {result['total']}次 | "
                 f"已出结果: {result['filled']}次 | "
                 f"等待中: {result['pending']}次")
    if result['total'] > 0:
        lines.append(f"正确: {result['correct']}次 | "
                     f"准确率: {result['accuracy']:.1f}%")

    lines.append("")
    lines.append("按方向:")
    for d in ["偏多", "偏空", "震荡"]:
        info = result["by_direction"].get(d, {"total": 0, "correct": 0, "accuracy": 0.0})
        if info["total"] > 0:
            lines.append(f"  {d}: {info['total']}次 | "
                         f"正确{info['correct']}次 | {info['accuracy']:.1f}%")

    lines.append("")
    lines.append("置信度分拆:")
    for label, thresh_str in [("高", "≥0.7"), ("中", "0.4-0.7"), ("低", "<0.4")]:
        info = result["confidence_accuracy"].get(label, {"total": 0, "accuracy": 0.0})
        if info["total"] > 0:
            lines.append(f"  {label}置信度({thresh_str}): {info['total']}次 | "
                         f"准确率{info['accuracy']:.1f}%")

    bias = report_bias(result)
    lines.append("")
    lines.append(bias)

    return "\n".join(lines)


def auto_fill_pending(quote_fn=None) -> dict:
    """
    自动回填所有待定预测（result=None 的记录）。

    遍历 predictions.json 中尚未回填的记录，
    获取最新行情价格，计算涨跌幅，回填结果。

    参数：
        quote_fn — 可选的行情获取函数（默认 None 时用内部实现）
                   签名: quote_fn(code) -> float（返回当前价）
                   允许外部注入方便测试和不依赖 data.py

    返回：
    {
        "filled": int,       # 成功回填的记录数
        "skipped": int,      # 跳过（不足3天）的记录数
        "errors": int,       # 失败数
        "details": [str],    # 操作详情列表
    }

    回填规则：
    1. 读取 predictions.json 中 result=None 的记录
    2. 计算当前日期与记录日期的天数差
    3. 天数差 >= 3 → 获取最新价格，计算涨跌幅，回填
    4. 天数差 < 3 → 跳过
    5. 结果判定：
       偏多→涨>1% → "正确"
       偏多→涨<-1% → "错误"
       偏空→跌<-1% → "正确"
       偏空→跌>1% → "错误"
       震荡→±2%以内 → "正确"
       其他 → "错误"
    """
    records = _load_records()

    result = {"filled": 0, "skipped": 0, "errors": 0, "details": []}
    now = datetime.now()

    for r in records:
        if r.get("result") is not None:
            continue  # 已回填

        # 计算天数差
        try:
            record_date = datetime.strptime(r["date"], "%Y-%m-%d")
            days_passed = (now - record_date).days
        except:
            result["errors"] += 1
            continue

        if days_passed < 3:
            result["skipped"] += 1
            continue

        # 获取最新价格
        code = r.get("code", "")
        current_price = None

        if quote_fn is not None:
            try:
                current_price = quote_fn(code)
            except:
                pass

        if current_price is None:
            # 内部实现：直接调用腾讯API
            try:
                import urllib.request
                prefixed = f"sz{code}" if not code.startswith(("6", "9")) else f"sh{code}"
                url = f"https://qt.gtimg.cn/q={prefixed}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                resp = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
                if "~" in resp:
                    vals = resp.split('"')[1].split("~")
                    current_price = float(vals[3]) if vals[3] else None
            except:
                pass

        if current_price is None or current_price <= 0:
            result["errors"] += 1
            continue

        # 计算涨跌幅
        entry_price = r.get("price", 0)
        if entry_price and entry_price > 0:
            chg = (current_price - entry_price) / entry_price
            direction = r.get("direction", "")

            # 判定结果
            if direction == "偏多":
                is_correct = chg > 0.01
            elif direction == "偏空":
                is_correct = chg < -0.01
            else:  # 震荡
                is_correct = abs(chg) < 0.02

            r["result"] = "正确" if is_correct else "错误"
            r["result_price"] = round(current_price, 2)
            r["result_chg"] = round(chg, 4)
            result["filled"] += 1
            result["details"].append(f"{code} {r['date']} {r['direction']}→{'正确' if is_correct else '错误'}({chg*100:+.1f}%)")
        else:
            result["errors"] += 1

    _save_records(records)
    return result


__all__ = [
    "record_prediction", "fill_result", "review_accuracy",
    "print_review", "report_bias", "auto_fill_pending",
]
