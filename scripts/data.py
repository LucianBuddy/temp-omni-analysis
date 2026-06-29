#!/usr/bin/env python3
"""
temp-omni 轻量数据层。
零外部依赖（仅 urllib.request + 可选 requests），完全替代 a-stock-data SKILL.md 的 inline 代码加载。
"""

import urllib.request
import json
import time
from datetime import datetime

_last_req = 0.0

def _rate_limit():
    """请求间隔 ≥1s"""
    global _last_req
    now = time.time()
    if now - _last_req < 1.0:
        time.sleep(1.0 - (now - _last_req))
    _last_req = time.time()

def _tencent_get(codes: list) -> str:
    """腾讯行情API。返回GBK解码文本，失败返回空串"""
    prefixed = []
    for c in codes:
        if c.startswith(("6", "9")):
            prefixed.append(f"sh{c}")
        elif c.startswith("8"):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    _rate_limit()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=10).read().decode("gbk")
    except:
        return ""

def tencent_quote(codes: list) -> dict:
    """
    批量获取实时行情（腾讯）。

    返回 {code: {name, price, last_close, open, high, low, change_pct,
                  amount_wan, turnover_pct, pe_ttm, mcap_yi, pb, vol_ratio}}

    支持指数（sh000001, sz399001 等）、个股、ETF。
    失败返回 {"error": True}
    """
    raw = _tencent_get(codes)
    if not raw:
        return {"error": True}

    result = {}
    for line in raw.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]  # 去掉 sh/sz/bj 前缀
        try:
            result[code] = {
                "name": vals[1],
                "price": float(vals[3]) if vals[3] else 0,
                "last_close": float(vals[4]) if vals[4] else 0,
                "open": float(vals[5]) if vals[5] else 0,
                "high": float(vals[33]) if vals[33] else 0,
                "low": float(vals[34]) if vals[34] else 0,
                "change_pct": float(vals[32]) if vals[32] else 0,
                "amount_wan": float(vals[37]) if vals[37] else 0,
                "turnover_pct": float(vals[38]) if vals[38] else 0,
                "pe_ttm": float(vals[39]) if vals[39] else 0,
                "mcap_yi": float(vals[44]) if vals[44] else 0,
                "pb": float(vals[46]) if vals[46] else 0,
                "limit_up": float(vals[47]) if len(vals) > 47 and vals[47] else 0,
                "limit_down": float(vals[48]) if len(vals) > 48 and vals[48] else 0,
                "vol_ratio": float(vals[49]) if vals[49] else 0,
            }
        except (ValueError, IndexError):
            continue
    return result

def baidu_kline_with_ma(code: str, ktype: str = "1") -> dict:
    """
    获取K线+MA5/10/20（百度股市通）。

    参数：
        code — 股票代码
        ktype — K线周期
               "1" = 日线
               "5" = 5分钟
               "15" = 15分钟
               "30" = 30分钟
               "60" = 60分钟

    返回结构：
    {
        "bars": [{"date": str, "open": float, "close": float, "high": float,
                   "low": float, "volume": float, "amount": float}, ...],
        "ma5": float,   # 最新MA5均价
        "ma10": float,
        "ma20": float,
        "ma5_vol": float,
        "ma10_vol": float,
        "ma20_vol": float,
    }

    失败返回 {"error": True}

    18字段索引：[0]=timestamp [1]=date [2]=open [3]=close [4]=volume
    [5]=high [6]=low [7]=amount [8]=range [9]=ratio [10]=turnoverratio
    [11]=preClose [12]=ma5avgprice [13]=ma5volume [14]=ma10avgprice
    [15]=ma10volume [16]=ma20avgprice [17]=ma20volume
    """
    try:
        import requests
    except ImportError:
        return {"error": True}

    url = "https://finance.pae.baidu.com/selfselect/getstockquotation"
    params = {
        "all": "1", "isIndex": "false", "isBk": "false", "isBlock": "false",
        "isFutures": "false", "isStock": "true", "newFormat": "1",
        "group": "quotation_kline_ab", "finClientType": "pc",
        "code": code, "start_time": "", "ktype": ktype,
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/vnd.finance-web.v1+json",
        "Origin": "https://gushitong.baidu.com",
        "Referer": "https://gushitong.baidu.com/",
    }
    _rate_limit()
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
    except:
        return {"error": True}

    result = data.get("Result", {})
    md = result.get("newMarketData", {})
    raw = md.get("marketData", "")
    if not raw:
        return {"error": True}

    bars = []
    ma5, ma10, ma20 = 0, 0, 0
    ma5v, ma10v, ma20v = 0, 0, 0

    for line in raw.split(";"):
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) < 18:
            continue
        bar = {
            "date": parts[1],
            "open": float(parts[2]),
            "close": float(parts[3]),
            "volume": float(parts[4]),
            "high": float(parts[5]),
            "low": float(parts[6]),
            "amount": float(parts[7]),
        }
        bars.append(bar)
        ma5 = float(parts[12]) if parts[12] != "--" else 0
        ma10 = float(parts[14]) if parts[14] != "--" else 0
        ma20 = float(parts[16]) if parts[16] != "--" else 0
        ma5v = float(parts[13]) if len(parts) > 13 and parts[13] != "--" else 0
        ma10v = float(parts[15]) if len(parts) > 15 and parts[15] != "--" else 0
        ma20v = float(parts[17]) if len(parts) > 17 and parts[17] != "--" else 0

    return {
        "bars": bars,
        "ma5": ma5, "ma10": ma10, "ma20": ma20,
        "ma5_vol": ma5v, "ma10_vol": ma10v, "ma20_vol": ma20v,
    }

def sina_us_quote() -> dict:
    """
    获取美股三大指数隔夜收盘。

    返回 {name: {price, change_pct, change_amt}}
    失败返回 {"error": True}
    """
    url = "https://hq.sinajs.cn/list=gb_dji,gb_ixic,gb_inx"
    _rate_limit()
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn",
        })
        text = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
    except:
        return {"error": True}

    result = {}
    for line in text.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        vals = line.split('"')[1].split(",")
        if len(vals) < 5:
            continue
        name = {"gb_dji": "道指", "gb_ixic": "纳指", "gb_inx": "标普"}.get(
            line.split("=")[0].split("_")[-1], vals[0])
        result[name] = {
            "price": float(vals[1]) if vals[1] else 0,
            "change_pct": float(vals[2]) if vals[2] else 0,
            "change_amt": float(vals[4]) if vals[4] else 0,
        }
    return result


# ══════════════════════════════════════════════
# build_short_summary — 预处理计算所有短线指标
# ══════════════════════════════════════════════

def build_short_summary(quote: dict, kline: dict, us: dict, index: dict = None) -> dict:
    """
    预处理计算所有短线指标，输出结构化 short_summary。

    输入参数：
        quote — tencent_quote([code])[code] 的返回值（单只股票的行情字典）
        kline — baidu_kline_with_ma(code) 的返回值（含 bars + ma5/10/20）
        us — sina_us_quote() 的返回值（美股三大指数）
        index — 可选，tencent_quote(["000001","399001","399006"]) 的返回值

    返回：
    {
        "p": float,           # 当前价
        "o": float,           # 开盘
        "h": float,           # 最高
        "l": float,           # 最低
        "pc": float,          # 昨收
        "chg": float,         # 涨跌幅%
        "turn": float,        # 换手率%
        "vr": float,          # 量比
        "amt": float,         # 成交额(万)
        "ma5": float, "ma10": float, "ma20": float,
        "ma_pos": str,        # 均线排列: "多头"/"空头"/"震荡"（p>ma5>ma10>ma20=多头）
        "avg_vol_5d": float,  # 近5日均量
        "avg_vol_20d": float, # 近20日均量
        "trend_5d": float,    # 近5日累计涨幅%
        "S1": float,          # 日内最低
        "S2": float,          # min(近20日最低×0.98, MA20)
        "R1": float,          # 日内最高
        "R2": float,          # max(MA5, MA10)
        "us_dji": float,      # 道指涨跌幅
        "us_ixic": float,     # 纳指涨跌幅
        "us_inx": float,      # 标普涨跌幅
        "us_dir": str,        # 美股方向: "同向涨"/"同向跌"/"分歧"
        "sh": float,          # 上证涨跌幅(有index时)
        "sz": float,          # 深证涨跌幅
        "cyb": float,         # 创业板涨跌幅
    }
    """
    ss = {}

    # ── 个股行情 ──
    if quote and isinstance(quote, dict):
        ss["p"] = quote.get("price", 0)
        ss["o"] = quote.get("open", 0)
        ss["h"] = quote.get("high", 0)
        ss["l"] = quote.get("low", 0)
        ss["pc"] = quote.get("last_close", 0)
        ss["chg"] = quote.get("change_pct", 0)
        ss["turn"] = quote.get("turnover_pct", 0)
        ss["vr"] = quote.get("vol_ratio", 0)
        ss["amt"] = quote.get("amount_wan", 0)
    else:
        ss.update({"p": 0, "o": 0, "h": 0, "l": 0, "pc": 0, "chg": 0, "turn": 0, "vr": 0, "amt": 0})

    # ── K线均线 ──
    if kline and not kline.get("error"):
        bars = kline.get("bars", [])
        ss["ma5"] = kline.get("ma5", 0)
        ss["ma10"] = kline.get("ma10", 0)
        ss["ma20"] = kline.get("ma20", 0)

        p = ss["p"]
        ma5, ma10, ma20 = ss["ma5"], ss["ma10"], ss["ma20"]
        if ma5 and ma10 and ma20 and p:
            if p > ma5 > ma10 > ma20:
                ss["ma_pos"] = "多头"
            elif p < ma5 < ma10 < ma20:
                ss["ma_pos"] = "空头"
            else:
                ss["ma_pos"] = "震荡"
        else:
            ss["ma_pos"] = "震荡"

        valid_bars = [b for b in bars if isinstance(b, dict) and b.get("volume") is not None]
        if len(valid_bars) >= 5:
            vols = [b["volume"] for b in valid_bars]
            ss["avg_vol_5d"] = sum(vols[-5:]) / 5
            ss["avg_vol_20d"] = sum(vols[-20:]) / min(20, len(vols))
        else:
            ss["avg_vol_5d"] = 0
            ss["avg_vol_20d"] = 0

        closes = [b.get("close", 0) for b in valid_bars]
        if len(closes) >= 6:
            ss["trend_5d"] = (closes[-1] - closes[-6]) / closes[-6] * 100
        else:
            ss["trend_5d"] = 0

        if ss["h"] > 0:
            ss["R1"] = ss["h"]
            ss["S1"] = ss["l"]
        elif len(valid_bars) > 0:
            ss["R1"] = valid_bars[-1].get("high", 0)
            ss["S1"] = valid_bars[-1].get("low", 0)
        else:
            ss["R1"] = 0
            ss["S1"] = 0

        lows = [b["low"] for b in valid_bars[-20:]] if len(valid_bars) >= 20 else [b["low"] for b in valid_bars]
        if lows and ss["ma20"]:
            ss["S2"] = min(min(lows) * 0.98, ss["ma20"])
        else:
            ss["S2"] = 0

        ss["R2"] = max(ss.get("ma5", 0), ss.get("ma10", 0))
    else:
        ss.update({"ma5": 0, "ma10": 0, "ma20": 0, "ma_pos": "数据不足",
                    "avg_vol_5d": 0, "avg_vol_20d": 0, "trend_5d": 0,
                    "R1": 0, "S1": 0, "R2": 0, "S2": 0})

    # ── 美股 ──
    if us and not us.get("error"):
        ss["us_dji"] = us.get("道指", {}).get("change_pct", 0)
        ss["us_ixic"] = us.get("纳指", {}).get("change_pct", 0)
        ss["us_inx"] = us.get("标普", {}).get("change_pct", 0)
        directions = []
        for key in ["us_dji", "us_ixic", "us_inx"]:
            v = ss.get(key, 0)
            if v > 0.1:
                directions.append(1)
            elif v < -0.1:
                directions.append(-1)
        pos = sum(1 for d in directions if d > 0)
        neg = sum(1 for d in directions if d < 0)
        if len(directions) >= 2 and pos == len(directions):
            ss["us_dir"] = "同向涨"
        elif len(directions) >= 2 and neg == len(directions):
            ss["us_dir"] = "同向跌"
        elif pos > neg:
            ss["us_dir"] = "偏涨"
        elif neg > pos:
            ss["us_dir"] = "偏跌"
        else:
            ss["us_dir"] = "分歧"
    else:
        ss.update({"us_dji": 0, "us_ixic": 0, "us_inx": 0, "us_dir": "数据不可用"})

    # ── 大盘指数 ──
    if index and isinstance(index, dict):
        sh = index.get("000001", {})
        sz = index.get("399001", {})
        cyb = index.get("399006", {})
        ss["sh"] = sh.get("change_pct", 0) if isinstance(sh, dict) else 0
        ss["sz"] = sz.get("change_pct", 0) if isinstance(sz, dict) else 0
        ss["cyb"] = cyb.get("change_pct", 0) if isinstance(cyb, dict) else 0
    else:
        ss["sh"] = ss["sz"] = ss["cyb"] = 0

    return ss


# ══════════════════════════════════════════════
# G1: ATR 波动率止损
# ══════════════════════════════════════════════

def compute_atr(bars: list, period: int = 14) -> dict:
    """
    计算 ATR (Average True Range) 和基于 ATR 的止损/止盈位。

    参数：
        bars — K线列表 [{"open","close","high","low","volume"}, ...]
               至少需要 period+1 根
        period — ATR周期（默认14）

    ATR 计算步骤：
    1. True Range = max(high - low, |high - prev_close|, |low - prev_close|)
    2. ATR = TR 的 period 日指数移动平均（简化：简单平均也可）

    返回：
    {
        "atr": float,                # ATR 值（元）
        "atr_pct": float,            # ATR 占价格百分比
        "stop_loss_aggressive": float,  # 激进止损: close - atr × 2
        "stop_loss_conservative": float, # 保守止损: close - atr × 3
        "take_profit_short": float,     # 短线止盈: close + atr × 1.5
        "take_profit_swing": float,     # 波段止盈: close + atr × 3
    }

    如果 bars 不足 period+1 根，返回 {"error": True, "detail": "K线不足"}
    """
    if not bars or len(bars) < period + 1:
        return {"error": True, "detail": "K线不足"}

    # 取最近 period+1 根
    recent = bars[-(period+1):]

    true_ranges = []
    for i in range(1, len(recent)):
        b = recent[i]
        prev = recent[i-1]
        hl = b.get("high", 0) - b.get("low", 0)
        hpc = abs(b.get("high", 0) - prev.get("close", 0))
        lpc = abs(b.get("low", 0) - prev.get("close", 0))
        tr = max(hl, hpc, lpc)
        true_ranges.append(tr)

    # ATR = 简单平均（简化版）
    atr = sum(true_ranges[-period:]) / period
    last_close = recent[-1].get("close", 0)
    atr_pct = (atr / last_close * 100) if last_close > 0 else 0

    return {
        "atr": round(atr, 4),
        "atr_pct": round(atr_pct, 2),
        "stop_loss_aggressive": round(last_close - atr * 2, 2),
        "stop_loss_conservative": round(last_close - atr * 3, 2),
        "take_profit_short": round(last_close + atr * 1.5, 2),
        "take_profit_swing": round(last_close + atr * 3, 2),
    }


def detect_volatility_regime(atr_pct: float) -> str:
    """
    根据 ATR 百分比判断波动率环境。

    atr_pct < 1% → "低波动"
    atr_pct 1-3% → "正常波动"
    atr_pct > 3% → "高波动"

    高波动时：止损放宽，仓位降低
    低波动时：止损收紧，仓位可正常
    """
    if atr_pct < 1.0:
        return "低波动"
    elif atr_pct <= 3.0:
        return "正常波动"
    else:
        return "高波动"


# ══════════════════════════════════════════════
# G2: RSI 超买超卖
# ══════════════════════════════════════════════

def compute_rsi(closes: list, period: int = 14) -> dict:
    """
    计算 RSI (Relative Strength Index)。

    参数：
        closes — 收盘价列表（至少 period+1 个）
        period — RSI 周期（默认14）

    计算步骤：
    1. 计算每日涨跌
    2. 计算平均涨幅和平均跌幅（period期内）
    3. RS = 平均涨幅 / 平均跌幅
    4. RSI = 100 - 100 / (1 + RS)

    返回：
    {
        "rsi": float,            # RSI 值（0-100）
        "signal": str,           # "超买" / "超卖" / "正常偏强" / "正常偏弱"
        "extreme": bool,         # 是否处于极值（>75或<25，比70/30更严格）
    }

    信号规则：
    RSI > 70 → "超买"（短线可能回调）
    RSI < 30 → "超卖"（短线可能反弹）
    RSI 50-70 → "正常偏强"
    RSI 30-50 → "正常偏弱"
    RSI > 75 或 < 25 → extreme=True

    如果 closes 不足 period+1 个，返回 {"error": True, "detail": "数据不足"}
    """
    if not closes or len(closes) < period + 1:
        return {"error": True, "detail": "数据不足"}

    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))

    # 取最近 period 个
    recent_gains = gains[-period:]
    recent_losses = losses[-period:]

    avg_gain = sum(recent_gains) / period
    avg_loss = sum(recent_losses) / period

    if avg_loss == 0:
        rsi = 100.0  # 无下跌日
    else:
        rs = avg_gain / avg_loss
        rsi = 100.0 - 100.0 / (1.0 + rs)

    # 信号判断
    if rsi > 70:
        signal = "超买"
    elif rsi < 30:
        signal = "超卖"
    elif rsi >= 50:
        signal = "正常偏强"
    else:
        signal = "正常偏弱"

    extreme = rsi > 75 or rsi < 25

    return {
        "rsi": round(rsi, 2),
        "signal": signal,
        "extreme": extreme,
    }


# ══════════════════════════════════════════════
# G3: 数据完整性检查
# ══════════════════════════════════════════════

def validate_kline(bars: list, min_required: int = 20) -> dict:
    """
    K线数据完整性检查。

    检查项：
    1. 根数是否满足最低要求
    2. 是否存在连续重复的收盘价（停牌标记）
    3. 是否存在交易日连续跳跃 > 5 个自然日（节假日）
    4. 是否存在空字段（NaN 或零值）

    参数：
        bars — K线列表
        min_required — 最低K线根数要求

    返回：
    {
        "valid": bool,              # True=数据可用, False=数据不可用
        "warnings": [str],          # 警告列表
        "n_bars": int,
        "n_trading_halt": int,      # 疑似停牌天数
        "n_gaps": int,              # 交易日跳跃次数
    }

    规则：
    - bars 为空或不足 min_required 根 → valid=False
    - 连续 >3 根相同收盘价 → 警告"疑似停牌"
    - 相邻K线日期间隔 >5 天 → 警告"交易日跳跃"
    """
    if not bars:
        return {"valid": False, "warnings": ["K线为空"], "n_bars": 0,
                "n_trading_halt": 0, "n_gaps": 0}

    n = len(bars)
    warnings = []
    trading_halt_days = 0
    gap_days = 0

    # 检查根数
    if n < min_required:
        warnings.append(f"K线根数不足({n}<{min_required})")

    # 检查连续相同收盘价（停牌）
    if n >= 3:
        halt_count = 0
        for i in range(1, n):
            if bars[i].get("close") == bars[i-1].get("close"):
                halt_count += 1
            else:
                if halt_count >= 3:
                    trading_halt_days += halt_count
                halt_count = 0
        if halt_count >= 3:
            trading_halt_days += halt_count
        if trading_halt_days > 0:
            warnings.append(f"疑似停牌{int(trading_halt_days)}天")

    # 检查日期跳跃
    try:
        for i in range(1, n):
            date_str = bars[i].get("date", "")
            prev_date_str = bars[i-1].get("date", "")
            if date_str and prev_date_str:
                parts_cur = date_str.split("-")
                parts_prev = prev_date_str.split("-")
                if len(parts_cur) == 3 and len(parts_prev) == 3:
                    d_cur = datetime(int(parts_cur[0]), int(parts_cur[1]), int(parts_cur[2]))
                    d_prev = datetime(int(parts_prev[0]), int(parts_prev[1]), int(parts_prev[2]))
                    delta = (d_cur - d_prev).days
                    if delta > 5:
                        gap_days += 1
                        if gap_days <= 2:
                            warnings.append(f"交易日跳跃({delta}天)于{prev_date_str}")
        if gap_days > 0:
            warnings.append(f"共{int(gap_days)}次交易日跳跃")
    except:
        pass  # 日期解析失败不阻断

    # 检查空字段
    empty_fields = 0
    for b in bars:
        for key in ["close", "high", "low", "volume"]:
            val = b.get(key, 0)
            if val is None or val == 0:
                empty_fields += 1
    if empty_fields > 0:
        warnings.append(f"存在{int(empty_fields)}个空数据字段")

    valid = n >= min_required and trading_halt_days < n * 0.3

    return {
        "valid": valid,
        "warnings": warnings,
        "n_bars": n,
        "n_trading_halt": trading_halt_days,
        "n_gaps": gap_days,
    }


# ══════════════════════════════════════════════
# H4: 资金流自动推断（无需东财API）
# ══════════════════════════════════════════════

def infer_fund_activity(quote: dict, kline: dict) -> dict:
    """
    通过成交额和成交量推断资金活跃度。

    不需要东财API，纯用腾讯行情+百度K线的已有数据。

    参数：
        quote — tencent_quote 返回的个股行情 dict
        kline — baidu_kline_with_ma 返回的K线 dict（含 bars + ma5/10/20）

    逻辑：
    1. 当日成交额 vs 近20日均成交额 → 放量/正常/缩量
    2. 结合涨跌幅推断资金方向

    返回：
    {
        "amount_vs_avg": float,       # 当日成交额 / 近20日均成交额
        "volume_vs_avg": float,       # 当日成交量 / 近20日均成交量
        "activity_label": str,        # "放量" / "正常" / "缩量"
        "inferred_direction": str,    # "放量上涨" / "放量下跌" / "缩量上涨" / "缩量下跌" / "正常"
        "net_direction": int or None, # 1=净流入推断, -1=净流出推断, 0=中性, None=数据不足
    }

    规则：
    - 放量：amount_vs_avg > 1.5
    - 缩量：amount_vs_avg < 0.5
    - 正常：0.5 ~ 1.5

    inferred_direction:
    - 放量 + 涨 → "放量上涨"
    - 放量 + 跌 → "放量下跌"
    - 缩量 + 涨 → "缩量上涨"
    - 缩量 + 跌 → "缩量下跌"
    - 正常量 → "正常"

    net_direction（用于 scoring.score_fund_flow）：
    - 放量上涨 → 1
    - 放量下跌 → -1
    - 其他 → 0
    """
    if not quote or not isinstance(quote, dict) or quote.get("error"):
        return {"amount_vs_avg": 0, "volume_vs_avg": 0, "activity_label": "数据不足",
                "inferred_direction": "数据不足", "net_direction": None}

    amount = quote.get("amount_wan", 0) or 0
    chg = quote.get("change_pct", 0) or 0

    # 从K线算近20日均成交额（万元）
    bars = kline.get("bars", []) if kline and not kline.get("error") else []
    valid_bars = [b for b in bars if isinstance(b, dict) and b.get("amount")]

    avg_amount_20d = 0
    avg_volume_20d = 0
    if len(valid_bars) >= 5:
        recent = valid_bars[-20:] if len(valid_bars) >= 20 else valid_bars
        amounts = [b["amount"] for b in recent]
        volumes = [b["volume"] for b in recent]
        avg_amount_20d = sum(amounts) / len(amounts)
        avg_volume_20d = sum(volumes) / len(volumes)

    amount_vs_avg = (amount / avg_amount_20d) if avg_amount_20d > 0 else 1.0
    volume_vs_avg = 0
    if avg_volume_20d > 0 and len(valid_bars) > 0:
        last_vol = valid_bars[-1].get("volume", 0) or 0
        volume_vs_avg = last_vol / avg_volume_20d

    # 活动标签
    if amount_vs_avg > 1.5:
        activity_label = "放量"
    elif amount_vs_avg < 0.5:
        activity_label = "缩量"
    else:
        activity_label = "正常"

    # 方向推断
    if activity_label == "放量" and chg > 0:
        inferred_direction = "放量上涨"
        net_direction = 1
    elif activity_label == "放量" and chg < 0:
        inferred_direction = "放量下跌"
        net_direction = -1
    elif activity_label == "缩量":
        inferred_direction = "缩量上涨" if chg > 0 else "缩量下跌"
        net_direction = 0
    else:
        inferred_direction = "正常"
        net_direction = 0

    return {
        "amount_vs_avg": round(amount_vs_avg, 2),
        "volume_vs_avg": round(volume_vs_avg, 2),
        "activity_label": activity_label,
        "inferred_direction": inferred_direction,
        "net_direction": net_direction,
    }


# ══════════════════════════════════════════════
# H5: 日级别趋势跟踪
# ══════════════════════════════════════════════

def detect_daily_trend(bars: list) -> dict:
    """
    检测日线级别趋势（中线辅助，为短线提供大背景）。

    参数：
        bars — 日线K线列表（>=30根最佳，>=60更准确）
               [{"date","open","close","high","low","volume"}, ...]

    逻辑：
    1. 计算 MA5/MA20/MA60 的排列关系
    2. 检查最近20日高低点：逐步抬升=上升，逐步降低=下降
    3. 检查价格围绕 MA60 的位置

    返回：
    {
        "trend": str,                  # "上升趋势" / "下降趋势" / "横盘"
        "strength": str,               # "强" / "中" / "弱"
        "ma_60_position": str,         # 价格 vs MA60: "之上"/"之下"/"附近"
        "higher_highs": bool,          # 最近20日高点在抬高
        "lower_lows": bool,            # 最近20日低点在降低
        "duration_days": int,          # 当前趋势持续的大致天数
        "detail": str,                 # 一句话描述
    }

    判断规则（优先级递减）：
    1. MA5 > MA20 > MA60 且 最近20日低点逐步抬升 → "上升趋势"
       - 如果最近5日涨幅>8% → strength="强"
       - 如果最近5日涨幅2-8% → strength="中"
       - 如果最近5日涨幅<2% → strength="弱"（可能转震荡）
    2. MA5 < MA20 < MA60 且 最近20日高点逐步降低 → "下降趋势"
       - 同样按跌幅分强弱
    3. 其他 → "横盘"
    """
    if not bars or len(bars) < 20:
        return {"trend": "数据不足", "strength": "弱", "ma_60_position": "未知",
                "higher_highs": False, "lower_lows": False, "duration_days": 0,
                "detail": f"需要至少20根K线，当前{len(bars) if bars else 0}根"}

    n = len(bars)
    closes = [b.get("close", 0) for b in bars if b.get("close")]
    highs = [b.get("high", 0) for b in bars if b.get("high")]
    lows = [b.get("low", 0) for b in bars if b.get("low")]
    last_close = closes[-1] if closes else 0

    # 计算MA
    def ma(data, period):
        if len(data) < period:
            return sum(data) / len(data) if data else 0
        return sum(data[-period:]) / period

    ma5 = ma(closes, 5)
    ma20 = ma(closes, 20)
    ma60 = ma(closes, min(60, len(closes)))

    if last_close == 0 or ma5 == 0 or ma20 == 0:
        return {"trend": "数据不足", "strength": "弱", "ma_60_position": "未知",
                "higher_highs": False, "lower_lows": False, "duration_days": 0,
                "detail": "价格数据为空"}

    # MA60位置
    if ma60 > 0:
        if last_close > ma60 * 1.05:
            ma_60_pos = "之上"
        elif last_close < ma60 * 0.95:
            ma_60_pos = "之下"
        else:
            ma_60_pos = "附近"
    else:
        ma_60_pos = "未知"

    # 最近20日高低点趋势
    recent_highs = highs[-20:] if len(highs) >= 20 else highs
    recent_lows = lows[-20:] if len(lows) >= 20 else lows

    # 分段比较（前10日 vs 后10日）
    mid = len(recent_highs) // 2
    if mid > 0:
        high_first_half = max(recent_highs[:mid])
        high_second_half = max(recent_highs[mid:])
        low_first_half = min(recent_lows[:mid])
        low_second_half = min(recent_lows[mid:])
        higher_highs = high_second_half > high_first_half * 1.01
        lower_lows = low_second_half < low_first_half * 0.99
    else:
        higher_highs = False
        lower_lows = False

    # 趋势判断
    ma_bullish = ma5 > ma20 > ma60 if ma60 > 0 else ma5 > ma20
    ma_bearish = ma5 < ma20 < ma60 if ma60 > 0 else ma5 < ma20

    # 近5日涨跌
    trend_5d = ((closes[-1] / closes[-6]) - 1) * 100 if len(closes) >= 6 else 0

    if ma_bullish and higher_highs and not lower_lows:
        trend = "上升趋势"
        if abs(trend_5d) > 8:
            strength = "强"
        elif abs(trend_5d) > 2:
            strength = "中"
        else:
            strength = "弱"
    elif ma_bearish and lower_lows and not higher_highs:
        trend = "下降趋势"
        if abs(trend_5d) > 8:
            strength = "强"
        elif abs(trend_5d) > 2:
            strength = "中"
        else:
            strength = "弱"
    else:
        trend = "横盘"
        strength = "中"

    # 大致持续天数（粗略估算）
    duration = 0
    if trend == "上升趋势":
        for i in range(min(60, len(closes) - 1), 0, -1):
            if closes[i] < ma(closes[:i+1], 5) and closes[i] < ma(closes[:i+1], 20):
                break
            duration = min(60, len(closes) - i)
    elif trend == "下降趋势":
        for i in range(min(60, len(closes) - 1), 0, -1):
            if closes[i] > ma(closes[:i+1], 5) and closes[i] > ma(closes[:i+1], 20):
                break
            duration = min(60, len(closes) - i)

    return {
        "trend": trend,
        "strength": strength,
        "ma_60_position": ma_60_pos,
        "higher_highs": higher_highs,
        "lower_lows": lower_lows,
        "duration_days": duration,
        "detail": f"{trend}({strength}), 价格在MA60{ma_60_pos}, 近5日{'涨' if trend_5d>0 else '跌'}{abs(trend_5d):.1f}%"
    }


# ── __all__ ──
def check_limit_status(quote: dict) -> dict:
    """
    检查A股涨跌停状态。

    参数：
        quote — tencent_quote 返回的单股行情 dict
                需要字段：price, limit_up, limit_down

    返回：
    {
        "limit_up_price": float,           # 涨停价
        "limit_down_price": float,          # 跌停价
        "distance_to_limit_up_pct": float,   # 距涨停还有百分之几（负值=已涨停）
        "distance_to_limit_down_pct": float, # 距跌停还有百分之几（负值=已跌停）
        "locked_up": bool,                 # 是否封死涨停
        "locked_down": bool,               # 是否封死跌停
        "approaching_limit_up": bool,      # 距涨停<3%但未封
        "approaching_limit_down": bool,    # 距跌停<3%但未封
        "limit_status": str,               # "涨停封板"/"跌停封板"/"逼近涨停"/"逼近跌停"/"正常"
    }
    """
    limit_up = quote.get("limit_up", 0)
    limit_down = quote.get("limit_down", 0)
    price = quote.get("price", 0)

    if not price or price <= 0:
        return {
            "limit_up_price": limit_up,
            "limit_down_price": limit_down,
            "distance_to_limit_up_pct": 0,
            "distance_to_limit_down_pct": 0,
            "locked_up": False,
            "locked_down": False,
            "approaching_limit_up": False,
            "approaching_limit_down": False,
            "limit_status": "数据不足",
        }

    # 距涨停%（负值=已涨停）
    if limit_up > 0:
        dist_up = (limit_up - price) / price * 100
    else:
        dist_up = 999  # 无涨停价

    # 距跌停%（负值=已跌停）
    if limit_down > 0:
        dist_down = (price - limit_down) / price * 100
    else:
        dist_down = 999  # 无跌停价

    locked_up = price >= limit_up if limit_up > 0 else False
    locked_down = price <= limit_down if limit_down > 0 else False
    approaching_up = (not locked_up) and (limit_up > 0) and (dist_up < 3.0)
    approaching_down = (not locked_down) and (limit_down > 0) and (dist_down < 3.0)

    if locked_up:
        status = "涨停封板"
    elif locked_down:
        status = "跌停封板"
    elif approaching_up:
        status = "逼近涨停"
    elif approaching_down:
        status = "逼近跌停"
    else:
        status = "正常"

    return {
        "limit_up_price": limit_up,
        "limit_down_price": limit_down,
        "distance_to_limit_up_pct": round(dist_up, 2) if limit_up > 0 else None,
        "distance_to_limit_down_pct": round(dist_down, 2) if limit_down > 0 else None,
        "locked_up": locked_up,
        "locked_down": locked_down,
        "approaching_limit_up": approaching_up,
        "approaching_limit_down": approaching_down,
        "limit_status": status,
    }


def assess_market_tradeability(index_data: dict = None) -> dict:
    """
    评估当前市场是否适合短线交易。

    仅使用四大指数数据，零外部依赖。

    参数：
        index_data — tencent_quote(["000001","399001","399006","000688"]) 的返回值
                     如果为 None，自动获取

    返回：
    {
        "tradeable": bool,              # True=适合交易, False=不适合
        "sentiment": str,               # "乐观" / "中性" / "悲观" / "分化"
        "detail": str,                  # 一句话描述
        "index_agreement": str,         # "一致上涨" / "一致下跌" / "分化"
        "volatility_warning": bool,     # 是否有指数波动>2%（宽幅震荡）
        "volume_confirmation": bool,    # 量能是否配合（需要平均成交额数据，暂用True）
        "n_positive": int,              # 上涨指数数量
        "n_negative": int,              # 下跌指数数量
    }

    规则：
    1. 获取四大指数涨跌幅：上证000001、深成399001、创业板399006、科创50000688
    2. 统计上涨/下跌数量
    3. 一致性判断：
       - 4个全涨 → "一致上涨"
       - 4个全跌 → "一致下跌"
       - 其他 → "分化"
    4. 波动率判断：任一指数涨跌>2% → volatility_warning=True
    5. 综合：
       - "一致上涨"+非高波动 → tradeable=True, sentiment="乐观"
       - "一致下跌"+非高波动 → tradeable=True, sentiment="悲观"
       - "分化" → tradeable=True, sentiment="分化"（轻仓操作）
       - 高波动 → tradeable=False, sentiment="高波动"（不适合短线）
    """
    if index_data is None or (isinstance(index_data, dict) and index_data.get("error")):
        return {"tradeable": True, "sentiment": "数据不足", "detail": "指数数据不可用",
                "index_agreement": "未知", "volatility_warning": False,
                "volume_confirmation": True, "n_positive": 0, "n_negative": 0}

    # 需要获取的指数
    idx_keys = ["000001", "399001", "399006", "000688"]
    idx_names = {"000001": "上证", "399001": "深成指", "399006": "创业板", "000688": "科创50"}

    changes = []
    n_pos, n_neg = 0, 0
    max_abs_chg = 0

    for k in idx_keys:
        idx = index_data.get(k, {})
        if isinstance(idx, dict):
            chg = idx.get("change_pct", 0) or 0
            changes.append(chg)
            if chg > 0:
                n_pos += 1
            elif chg < 0:
                n_neg += 1
            max_abs_chg = max(max_abs_chg, abs(chg))
        else:
            n_neg += 1  # 数据缺失视为不利

    # 一致性判断
    if n_pos == 4:
        agreement = "一致上涨"
    elif n_neg == 4:
        agreement = "一致下跌"
    else:
        agreement = "分化"

    # 波动率
    vol_warning = max_abs_chg > 2.0
    volume_conf = True  # 暂不判断量能

    # 综合
    if vol_warning:
        tradeable = False
        sentiment = "高波动"
        detail = f"高波动(最大{max_abs_chg:.1f}%)，不适合短线交易"
    elif agreement == "一致上涨":
        tradeable = True
        sentiment = "乐观"
        detail = "四大指数一致上涨，短线环境良好"
    elif agreement == "一致下跌":
        tradeable = True
        sentiment = "悲观"
        detail = "四大指数一致下跌，适合做空/观望"
    else:
        tradeable = True
        sentiment = "分化"
        detail = f"指数分化(涨{n_pos}/跌{n_neg})，轻仓短线为主"

    return {
        "tradeable": tradeable,
        "sentiment": sentiment,
        "detail": detail,
        "index_agreement": agreement,
        "volatility_warning": vol_warning,
        "volume_confirmation": volume_conf,
        "n_positive": n_pos,
        "n_negative": n_neg,
    }


# ══════════════════════════════════════════════
# L4: 趋势加速/衰减检测
# ══════════════════════════════════════════════

def detect_momentum_shift(bars: list, lookback: int = 10) -> dict:
    """
    检测趋势的加速/衰减。

    通过比较近期每根K线的实体长度和成交量判断趋势强度变化。

    参数：
        bars — K线列表 [{"open","close","high","low","volume"}, ...]
        lookback — 回看K线根数（默认10）

    返回：
    {
        "momentum": str,                    # "加速上涨"/"加速下跌"/"衰减上涨"/"衰减下跌"/"无趋势"
        "recent_candle_sizes": [float],     # 近N根K线实体绝对值列表
        "size_trend": str,                  # "扩大"/"收缩"/"稳定"
        "consecutive_direction": int,       # 连续同向K线数（正值=连涨，负值=连跌）
        "reversal_candle_detected": bool,   # 是否出现潜在反转K线
        "reversal_detail": str,             # 反转K线描述
        "detail": str,
    }
    """
    if not bars or len(bars) < lookback:
        return {"momentum": "数据不足", "size_trend": "数据不足",
                "consecutive_direction": 0, "reversal_candle_detected": False,
                "detail": f"需要至少{lookback}根K线"}

    recent = bars[-lookback:]
    n = len(recent)

    # 1. 计算实体大小
    sizes = []
    directions = []  # 1=阳, -1=阴
    for b in recent:
        o, c = b.get("open", 0), b.get("close", 0)
        body = abs(c - o)
        sizes.append(body)
        if c >= o:
            directions.append(1)
        else:
            directions.append(-1)

    # 2. 连续同向K线数
    consecutive = 0
    if n >= 3:
        last_dir = directions[-1]
        for d in reversed(directions):
            if d == last_dir:
                consecutive += last_dir
            else:
                break

    # 3. 实体大小趋势
    if n >= 6:
        first_3 = sum(sizes[:3]) / 3
        last_3 = sum(sizes[-3:]) / 3
        if first_3 > 0:
            ratio = last_3 / first_3
            if ratio > 1.3:
                size_trend = "扩大"
            elif ratio < 0.7:
                size_trend = "收缩"
            else:
                size_trend = "稳定"
        else:
            size_trend = "稳定"
    else:
        size_trend = "数据不足"

    # 4. 方向
    if directions[-1] > 0:
        direction_label = "上涨"
    else:
        direction_label = "下跌"

    # 5. 综合 momentum
    if size_trend == "扩大":
        momentum = f"加速{direction_label}"
    elif size_trend == "收缩":
        momentum = f"衰减{direction_label}"
    else:
        momentum = "无趋势"

    # 6. 反转K线检测（只看最近一根）
    reversal_detected = False
    reversal_detail = ""
    last = recent[-1]
    lo, lc, lh, ll = last.get("open", 0), last.get("close", 0), last.get("high", 0), last.get("low", 0)
    body = abs(lc - lo)
    upper_shadow = lh - max(lc, lo)
    lower_shadow = min(lc, lo) - ll
    total_range = lh - ll

    if total_range > 0:
        # 十字星
        if body < total_range * 0.1:
            reversal_detected = True
            reversal_detail = "十字星，可能变盘"
        # 长下影（底部反转信号，出现在下跌中）
        elif lower_shadow > body * 2 and upper_shadow < body * 0.5:
            reversal_detected = True
            reversal_detail = "长下影线，可能出现底部反转"
        # 长上影（顶部反转信号，出现在上涨中）
        elif upper_shadow > body * 2 and lower_shadow < body * 0.5:
            reversal_detected = True
            reversal_detail = "长上影线，可能出现顶部反转"

    detail = f"{momentum}，连{'涨' if consecutive>0 else '跌'}{abs(consecutive)}根，实体{size_trend}"
    if reversal_detected:
        detail += f"，{reversal_detail}"

    return {
        "momentum": momentum,
        "recent_candle_sizes": [round(s, 4) for s in sizes],
        "size_trend": size_trend,
        "consecutive_direction": consecutive,
        "reversal_candle_detected": reversal_detected,
        "reversal_detail": reversal_detail,
        "detail": detail,
    }


# ══════════════════════════════════════════════
# L1: 成交量能深度分析
# ══════════════════════════════════════════════

def analyze_volume_profile(bars: list, current_vol_ratio: float = None) -> dict:
    """
    成交量能深度分析。

    用纯K线数据推断筹码状态和资金意图。

    参数：
        bars — K线列表 [{"open","close","high","low","volume"}, ...]
        current_vol_ratio — 当日量比（可选）

    返回：
    {
        "volume_pattern": str,         # "放量上涨"/"放量下跌"/"缩量企稳"/"缩量阴跌"/"正常"
        "abnormal_volume": bool,       # 异常放量（最大量 > 均值×2.5）
        "accumulation_signal": bool,   # 吸筹信号（缩量+价格企稳）
        "distribution_signal": bool,   # 派发信号（放量+滞涨/下跌）
        "volatility_shrink": bool,     # 波动率收缩（缩量+振幅缩小，变盘前兆）
        "max_volume_position": str,    # 最大成交量在价格区间的位置: "顶部"/"底部"/"中部"
        "detail": str,
    }
    """
    if not bars or len(bars) < 10:
        return {"volume_pattern": "数据不足", "abnormal_volume": False,
                "accumulation_signal": False, "distribution_signal": False,
                "volatility_shrink": False, "detail": "K线不足"}

    recent = bars[-20:] if len(bars) >= 20 else bars
    n = len(recent)

    # 成交量统计
    vols = [b.get("volume", 0) or 0 for b in recent]
    avg_vol = sum(vols) / n
    max_vol = max(vols)
    abnormal = max_vol > avg_vol * 2.5

    # 价格是否企稳（最近5日与之前5日比较）
    closes = [b.get("close", 0) for b in recent if b.get("close")]
    if len(closes) >= 10:
        first5_min = min(closes[:5])
        last5_min = min(closes[-5:])
        first5_max = max(closes[:5])
        last5_max = max(closes[-5:])
        price_stable = last5_min >= first5_min * 0.98 and last5_max <= first5_max * 1.02
    else:
        price_stable = False

    # 最近5根K线方向
    last5_close_dir = []
    for i in range(max(0, len(closes)-5), len(closes)-1):
        if closes[i+1] > closes[i]:
            last5_close_dir.append(1)
        else:
            last5_close_dir.append(-1)

    # 连跌判断
    if len(last5_close_dir) >= 3:
        consecutive_down = all(d < 0 for d in last5_close_dir[-3:])
        consecutive_up = all(d > 0 for d in last5_close_dir[-3:])
    else:
        consecutive_down = False
        consecutive_up = False

    # 最近5日成交量变化
    vol_slowing = False
    if len(vols) >= 8:
        last3_vol = sum(vols[-3:]) / 3
        prev3_vol = sum(vols[-6:-3]) / 3
        if prev3_vol > 0 and last3_vol < prev3_vol * 0.6:
            vol_slowing = True

    # 振幅缩小
    amp_shrink = False
    if len(recent) >= 6:
        amps = [(b.get("high",0)-b.get("low",0)) for b in recent if b.get("high") and b.get("low")]
        if len(amps) >= 6:
            if sum(amps[-3:])/3 < sum(amps[-6:-3])/3 * 0.7:
                amp_shrink = True

    # 最大成交量位置
    max_vol_idx = vols.index(max_vol)
    max_bar = recent[max_vol_idx]
    max_close = max_bar.get("close", 0)
    all_highs = [b.get("high",0) for b in recent if b.get("high")]
    all_lows = [b.get("low",0) for b in recent if b.get("low")]
    if all_highs and all_lows:
        price_range = max(all_highs) - min(all_lows)
        if price_range > 0:
            pos = (max_close - min(all_lows)) / price_range
            if pos > 0.66:
                max_vol_pos = "顶部"
            elif pos < 0.33:
                max_vol_pos = "底部"
            else:
                max_vol_pos = "中部"
        else:
            max_vol_pos = "未知"
    else:
        max_vol_pos = "未知"

    # 综合判断
    vol_ratio = current_vol_ratio if current_vol_ratio is not None else (vols[-1] / avg_vol if avg_vol > 0 else 1.0)

    if vol_ratio > 1.5 and consecutive_down:
        volume_pattern = "放量下跌"
        distribution_signal = True
        accumulation_signal = False
    elif vol_ratio > 1.5 and consecutive_up:
        volume_pattern = "放量上涨"
        distribution_signal = False
        accumulation_signal = False
    elif vol_slowing and price_stable:
        volume_pattern = "缩量企稳"
        accumulation_signal = True
        distribution_signal = False
    elif vol_slowing and consecutive_down:
        volume_pattern = "缩量阴跌"
        accumulation_signal = False
        distribution_signal = False
    else:
        volume_pattern = "正常"
        accumulation_signal = False
        distribution_signal = False

    volatility_shrink = amp_shrink and vol_slowing

    detail_parts = [volume_pattern]
    if abnormal:
        detail_parts.append("异常放量")
    if distribution_signal:
        detail_parts.append("主力派发")
    if accumulation_signal:
        detail_parts.append("吸筹信号")
    if volatility_shrink:
        detail_parts.append("变盘前兆")
    detail_parts.append(f"最大量在{max_vol_pos}")

    return {
        "volume_pattern": volume_pattern,
        "abnormal_volume": abnormal,
        "accumulation_signal": accumulation_signal,
        "distribution_signal": distribution_signal,
        "volatility_shrink": volatility_shrink,
        "max_volume_position": max_vol_pos,
        "detail": "，".join(detail_parts),
    }


__all__ = ["tencent_quote", "baidu_kline_with_ma", "sina_us_quote", "build_short_summary",
           "compute_atr", "detect_volatility_regime", "compute_rsi", "validate_kline",
           "infer_fund_activity", "detect_daily_trend", "assess_market_tradeability",
           "check_limit_status", "detect_momentum_shift", "analyze_volume_profile"]
