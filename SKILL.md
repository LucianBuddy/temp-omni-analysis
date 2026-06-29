---
name: temp-omni-analysis
description: A股短线/日内交易分析（事件驱动+技术面）。当用户请求当日走势、短线研判、结合美股/新闻看今日时触发。
version: 2.1.0
changelog: CHANGELOG.md
---

# temp-omni-analysis — A股短线/日内交易分析 v2.1.0

当用户请求 **当日走势、短线研判、结合美股/新闻看今日** 时触发。

---

## 触发条件

触发关键词："下午/上午走势"、"结合昨晚美股"、"今天/短线怎么看"、"盘后复盘"。排除"长期/基本面/估值/该不该持有"（转 omni-lt-stock-analysis）。非交易日取上一完整交易日数据。

---

## 前置判断 1：时间窗口分类

| 窗口 | 时间 | 侧重 |
|------|------|------|
| **盘前** | 8:30-9:25 | 美股>新闻>竞价 |
| **上午盘** | 9:30-11:30 | 量价>北向>行业 |
| **午间→下午** | 11:30-15:00 | 趋势延续>反转>尾盘 |
| **盘后复盘** | 15:00-17:00 | 全天+龙虎榜+次日 |
| **隔夜/周末** | 非交易日 | 美股+消息+下周 |

---

## scripts/ 模块一览

```
temp-omni-analysis/
├── scripts/
│   ├── data.py         # 轻量数据层 + ATR/RSI/数据校验/市场可交易性/动量/成交量深度
│   ├── cache.py        # 文件缓存系统（TTL自动清除）
│   ├── patterns.py     # K线形态自动识别
│   ├── scoring.py      # 因子评分系统 + 多周期共振 + 相对强度
│   ├── engine.py       # [v1.6.0] 一键分析引擎（run_analysis）
│   ├── screener.py     # [v1.7.0] 批量筛选排序
│   ├── backtest_st.py  # [v2.0.0] 短线信号历史回测
│   └── tracker.py      # 预测记录与复盘模块（含自动回填）
├── cache/              # 缓存目录（自动创建）
├── predictions.json    # 预测记录文件（自动创建）
├── SKILL.md
└── CHANGELOG.md
```

### v2.1.0 新增功能

| 模块 | 新增函数 | 用途 |
|------|---------|------|
| `engine.py` | `summarize_analysis()` | 自动生成一句话分析摘要 |
| `screener.py` | `screen_and_backtest()` | 批量筛选+回测验证闭环 |

### v2.0.0 新增功能

| 模块 | 新增函数 | 用途 |
|------|---------|------|
| `data.py` | `detect_momentum_shift()` | 趋势加速/衰减检测，反转K线识别 |
| `data.py` | `analyze_volume_profile()` | 成交量能深度分析（筹码/吸筹/派发） |
| `engine.py` | — | run_analysis() 集成 L4+L1+L3（尾盘竞价感知） |
| `backtest_st.py` | `backtest_short_term()`, `print_backtest_report()` | 短线信号历史回测模块 |

### v1.9.0 新增功能

| 模块 | 新增函数 | 用途 |
|------|---------|------|
| `data.py` | `check_limit_status()` | 涨跌停板分析（封板/逼近/正常） |
| `scoring.py` | `industry_peer_comparison()` | 行业联动对比（领涨/领跌/跟随/逆势） |
| `engine.py` | — | run_analysis() 集成 K1+K3 |

### v1.8.0 新增功能

| 模块 | 新增函数 | 用途 |
|------|---------|------|
| `tracker.py` | `auto_fill_pending()` | 自动回填3日后的预测结果，完成复盘闭环 |
| `data.py` | `assess_market_tradeability()` | 四大指数评估市场短线交易环境 |
| `engine.py` | — | run_analysis() 集成市场可交易性评估 + 自动交易计划(入场/止损/止盈) |

### v1.7.0 新增功能

| 模块 | 新增函数 | 用途 |
|------|---------|------|
| `data.py` | `infer_fund_activity()` | 从成交额+成交量推断资金活跃度（无需东财API） |
| `data.py` | `detect_daily_trend()` | 日线级别趋势判定（为短线提供中线大背景） |
| `screener.py` | `screen_stocks()` | 批量筛选多只股票并对比排序 |
| `screener.py` | `print_screen_results()` | 筛选结果格式化打印 |
| `engine.py` | — | run_analysis() 集成 H4/H5，结果新增 fund_activity + daily_trend |

### v1.6.0 新增功能

| 模块 | 新增函数 | 用途 |
|------|---------|------|
| `data.py` | `compute_atr()`, `detect_volatility_regime()` | ATR波动率止损/止盈计算 |
| `data.py` | `compute_rsi()` | RSI超买超卖信号 |
| `data.py` | `validate_kline()` | K线数据完整性校验 |
| `data.py` | `baidu_kline_with_ma(ktype)` | 多周期K线支持（日线/5/15/30/60分钟） |
| `scoring.py` | `score_multi_timeframe()` | 多周期均线共振评分 |
| `scoring.py` | `relative_strength()`, `score_relative_strength()` | 个股 vs 板块/大盘相对强度 |
| `engine.py` | `run_analysis()` | 一键分析引擎，替代手动9步调用 |

---

## Step 1：数据采集

**调用顺序**：批次1（强制）→ Wiki通道（强制）→ 短线价值判断 → 联网搜索（可选）

### 批次 1 — 自建数据通道（scripts/data.py + scripts/cache.py）

```python
from scripts.data import tencent_quote, baidu_kline_with_ma, sina_us_quote

# 三指数
index_data = tencent_quote(["000001", "399001", "399006"])

# 个股行情
quote = tencent_quote([code])
if code in quote:
    quote = quote[code]
else:
    quote = {}

# K线 + MA5/10/20
kline = baidu_kline_with_ma(code)

# 美股隔夜
us = sina_us_quote()
```

| 数据项 | 优先级 | 函数 | fallback |
|-------|-------|------|---------|
| 三指数当日涨跌 | P0 | `tencent_quote(["000001","399001","399006"])` | 无 |
| 个股价/开/高/低/昨收 | P0 | `tencent_quote([code])[code]` | 无 |
| 换手率/量比/成交额 | P0 | `tencent_quote([code])[code]` | 无 |
| 近60根K线+MA5/10/20 | P0 | `baidu_kline_with_ma(code)` | 标注不可用 |
| 美股隔夜(DJI/IXIC/INX) | P1 | `sina_us_quote()` | 标注数据不可用 |

**自动缓存**：脚本数据会自动通过 scripts/cache.py 缓存。缓存 TTL：K线1小时、行情5分钟、新闻30分钟、市场30分钟。如需强制刷新可调用 `cache_clear(category)`。

### 通道 W — Wiki（强制，批次1后立即执行）

`memory_search("股票名 短线")` + `memory_search("股票代码")` → **必须执行这2次搜索，不得跳过**。输出格式："找到N条匹配" 或 "未找到匹配"（无匹配也必须在报告中标记此结果）。

### 通道 S — 联网搜索（仅 wiki 仍不足时触发）

`web_fetch("股票名 + 事件 + 日期")` 取标题+摘要前200字。触发条件：突发政策/wiki未覆盖/用户明确要求。

### 批次 2 — 东财通道（限流）

| 数据项 | 函数来源 | fallback |
|-------|---------|---------|
| 涨跌家数 | 东财 `clist` | 标注不可用 |
| 行业TOP/BOTTOM5 | 东财 `clist fs=m:90+t:2` | 联网搜索补充 |
| 当日主力净额(万元) | 东财 fund_flow 接口 | 跳过资金因子 |
| 近20日主力累计(万元) | 东财 fund_flow_120d 接口 | 同上 |
| 全球快讯10条 | 东财 np-weblist | 东财不可用→**必须**执行`web_fetch("行业名 最新动态")`取摘要200字 |
| 个股当日新闻 | 东财 search-api | 东财不可用→**必须**执行`web_fetch("股票名 最新公告")`取摘要200字 |

### 批次 3 — 北向+同花顺

| 数据项 | 函数来源 | fallback |
|-------|---------|---------|
| 北向当日净流入 | `hsgt_realtime()` 末行 | 盘中/盘后确认 |
| 题材归因 | `ths_hot_reason()` 当该股在名单中 | 跳过 |

**东财全不可用** → 降级输出概率，标注"基于腾讯/新浪数据"。

### 数据摘要 + 数据校验（Step 1.5）

使用 `build_short_summary` 将原始数据预处理为结构化摘要：

```python
from scripts.data import build_short_summary, validate_kline, infer_fund_activity

ss = build_short_summary(quote, kline, us, index_data)

# v1.6.0: K线数据完整性校验
kline_valid = validate_kline(kline.get("bars", []))
if not kline_valid["valid"]:
    warnings.extend(kline_valid["warnings"])
    # 注意 kline_valid["valid"]=False 表示数据不可靠，降级输出

# v1.7.0: 资金流自动推断（无需东财API）
fund_info = infer_fund_activity(quote, kline)
# fund_info.activity_label: "放量" / "正常" / "缩量"
# fund_info.inferred_direction: "放量上涨" / "放量下跌" / "缩量上涨" / "缩量下跌" / "正常"
# fund_info.net_direction: 1=净流入推断, -1=净流出推断, 0=中性
```

LLM 直接从 `ss` 中读取各指标值。`ss` 包含：
- 个股行情：`p`/`o`/`h`/`l`/`pc`/`chg`/`turn`/`vr`/`amt`
- 均线排列：`ma5`/`ma10`/`ma20`/`ma_pos`（"多头"/"空头"/"震荡"）
- 量能趋势：`avg_vol_5d`/`avg_vol_20d`/`trend_5d`（近5日累计涨幅%）
- 支撑阻力：`S1`（日内最低）/`S2`（min(近20日最低×0.98, MA20)）/`R1`（日内最高）/`R2`（max(MA5, MA10)）
- 美股传导：`us_dji`/`us_ixic`/`us_inx`/`us_dir`（"同向涨"/"同向跌"/"分歧"）
- 大盘指数：`sh`/`sz`/`cyb`（有index数据时）

`validate_kline()` 返回包含 `valid`、`warnings`、`n_trading_halt`（疑似停牌天数）和 `n_gaps`（交易日跳跃次数）。

`infer_fund_activity()` 通过当天成交额 vs 近20日均成交额 自动推断资金方向，无需东财API：
- 放量上涨 → 推断资金净流入
- 放量下跌 → 推断资金净流出
- 缩量/正常量 → 中性
- 该推断会自动传递到 Step 5 的 fund_flow 因子评分

---

## ⏱ 短线价值判断（批次1+wiki后执行）

**快速通过（任一即可）**：近5日累计±>10% / 换手率>3% / 有重大公告 / wiki查匹配。否则执行完整5条件检查（≥2通过）：换手率>阈值(按市值分档) / 涨跌±>3%或5日>8% / 板块TOP/BOTTOM / 龙虎榜 / 有新闻。

---

## Step 2-4：技术分析 + 事件归因 + 美股传导

### 技术分析（scripts/data.py + patterns.py）

**v2.0.0 新增动量趋势检测：**

```python
from scripts.data import detect_momentum_shift

# 检测趋势加速/衰减
momentum = detect_momentum_shift(bars)
# momentum 输出:
#   "momentum" — "加速上涨"/"加速下跌"/"衰减上涨"/"衰减下跌"/"无趋势"
#   "size_trend" — "扩大"/"收缩"/"稳定"（实体大小趋势）
#   "consecutive_direction" — 连续同向K线数（+连涨/-连跌）
#   "reversal_candle_detected" — 是否出现潜在反转K线
#   "reversal_detail" — 十字星/长下影/长上影描述
#   "detail" — 一句话描述
```

**v2.0.0 新增成交量能深度分析：**

```python
from scripts.data import analyze_volume_profile

# 成交量能深度分析
vp = analyze_volume_profile(bars, current_vol_ratio=ss.get("vr", None))
# vp 输出:
#   "volume_pattern" — "放量上涨"/"放量下跌"/"缩量企稳"/"缩量阴跌"/"正常"
#   "abnormal_volume" — 是否有异常放量（最大量>均值×2.5）
#   "accumulation_signal" — 是否检测到吸筹信号（缩量+企稳）
#   "distribution_signal" — 是否检测到派发信号（放量+连跌）
#   "volatility_shrink" — 波动率收缩（缩量+振幅缩小，变盘前兆）
#   "max_volume_position" — 最大量在价格区间的位置（顶部/底部/中部）
#   "detail" — 一句话描述
```

**v1.8.0 新增市场可交易性评估：**

```python
from scripts.data import assess_market_tradeability

# 评估四大指数（上证/深成/创业板/科创50）是否适合短线交易
market = assess_market_tradeability(index_data)
# market 输出:
#   "tradeable" — True=适合交易, False=不适合
#   "sentiment" — "乐观"/"中立"/"悲观"/"分化"
#   "index_agreement" — "一致上涨"/"一致下跌"/"分化"
#   "volatility_warning" — 是否有指数波动>2%
#   "detail" — 一句话描述
```

市场可交易性为短线提供大盘环境评估：一致上涨时可积极操作，分化时轻仓操作，高波动时暂停短线。

**新增 ATR 波动率分析：**

```python
from scripts.data import compute_atr, detect_volatility_regime

atr = compute_atr(kline["bars"], period=14)
regime = detect_volatility_regime(atr["atr_pct"])  # "低波动"/"正常波动"/"高波动"
# atr 输出:
#   "atr" — ATR值(元)
#   "atr_pct" — ATR占价格百分比
#   "stop_loss_aggressive" — 激进止损位 (close - atr×2)
#   "stop_loss_conservative" — 保守止损位 (close - atr×3)
#   "take_profit_short" — 短线止盈位 (close + atr×1.5)
#   "take_profit_swing" — 波段止盈位 (close + atr×3)
```

**新增 RSI 超买超卖分析：**

```python
from scripts.data import compute_rsi

closes = [b["close"] for b in kline["bars"] if b.get("close")]
rsi = compute_rsi(closes, period=14)
# rsi 输出:
#   "rsi" — RSI值(0-100)
#   "signal" — "超买"/"超卖"/"正常偏强"/"正常偏弱"
#   "extreme" — 是否极值(>75或<25)
```

**v1.7.0 新增日级别趋势定位：**

```python
from scripts.data import detect_daily_trend

bars = kline.get("bars", [])
trend = detect_daily_trend(bars)
# trend 输出:
#   "trend" — "上升趋势"/"下降趋势"/"横盘"
#   "strength" — "强"/"中"/"弱"
#   "ma_60_position" — 价格 vs MA60: "之上"/"之下"/"附近"
#   "duration_days" — 当前趋势持续天数（估算）
#   "detail" — 一句话描述
```

日级别趋势为短线提供中线大背景：上升趋势中做多可放宽止损，下降趋势中抢反弹需更谨慎。

### K线形态（scripts/patterns.py）

```python
from scripts.patterns import detect_candle_patterns, simple_direction

patterns = detect_candle_patterns(kline["bars"])
dir_signal = simple_direction(kline["bars"])
```

- `detect_candle_patterns(bars)` → 自动检测十字星/锤子线/上吊线/看涨吞没/看跌吞没/三连阳/三连阴/晨星/暮星
- `simple_direction(bars)` → 基于最近3根K线实体方向输出"连续走强"/"偏强"/"连续走弱"/"偏弱"/"震荡"

LLM 将 patterns 和 dir_signal 结合 `ss` 中的均线/量比/资金进行分析。补充人工判断：
- 均线：全上方=多头 / 全下方=空头 / 交错=震荡
- 量比：>1.5放量 / 0.5-1.5正常 / <0.5缩量
- 资金：f_ok=True时才判断，正=偏多负=偏空
- 支撑：S1(日内最低) / S2=min(近20日最低×0.98, MA20)
- 阻力：R1(日内最高) / R2=max(MA5, MA10)
- 趋势幅度：近5日累计±>10%=超涨/超卖区间，反转概率增加；急跌后缩量反弹=企稳信号(空头衰竭，不确认反转)；急跌后放量反弹=反转信号增强(资金主动承接，偏强)；急涨后放量滞涨=短期见顶

### 事件归因（仅n_ok=True时）

全局快讯匹配 → 个股新闻 → 题材标签。

### 美股传导

```
盘前=高 → 上午盘=中高 → 下午盘=低(权重0.5)
盘后=标注盘中数据 → 周末=标注周末间隔
三指数同向=方向一致；跟跌>跟涨经验
```

---

## Step 5：综合判断（scripts/scoring.py v1.6.0）

### 5-A 方向概率（带权重因子累加）

```python
from scripts.scoring import (
    compute_total_score, score_moving_average, score_volume,
    score_fund_flow, score_events, score_us, score_trend_amplitude,
    score_multi_timeframe, relative_strength, score_relative_strength,
)

scores = {
    "ma": score_moving_average(ss),
    "volume": score_volume(ss),
    "fund_flow": score_fund_flow(f_net),     # f_net 来自东财接口
    "events": score_events(has_pos_news, has_neg_news),
    "us": score_us(ss.get("us_dir", ""), time_window),
    "trend": score_trend_amplitude(ss.get("trend_5d", 0)),
}
result = compute_total_score(scores, time_window)

# v1.6.0: 多周期均线共振（可选，需60分/15分K线数据）
multi = score_multi_timeframe(
    ma_daily=ss.get("ma_pos", ""),
    ma_60min=ma_60min,   # 从 baidu_kline_with_ma(code, "60") 获取
    ma_15min=ma_15min,   # 从 baidu_kline_with_ma(code, "15") 获取
)
# multi: {"resonance", "score"(1/-1/0), "detail"}

# v1.6.0: 相对强度（需大盘/板块数据）
if market_change is not None or industry_change is not None:
    rs = relative_strength(
        stock_change=ss.get("chg", 0) / 100,
        industry_index_changes={"半导体": industry_change} if industry_change else None,
        market_change=market_change,
    )
    rs_score = score_relative_strength(rs)
    if rs_score != 0:
        scores["relative_strength"] = rs_score
        # 重新计算
        result = compute_total_score(scores, time_window)
```

`compute_total_score` 返回：
- `total` — 总分（各因子×权重求和）
- `n_active` — 有效因子数
- `direction` — "偏多"/"偏空"/"震荡"
- `probability` — "70%+"/"60%+"/None（n<3时不输出概率）
- `confidence` — "高"/"中"/"低"
- `factor_detail` — 各因子得分详情字符串

评分规则：
| 因子 | 计算方式 | 权重 |
|------|---------|------|
| 均线系统 | `score_moving_average(ss)` | 1.0 |
| 量价关系 | `score_volume(ss)` | 1.0 |
| 资金面 | `score_fund_flow(f_net)` | f_ok=False不计 |
| 事件面 | `score_events(pos, neg)` | n_ok=False不计 |
| 美股传导 | `score_us(us_dir, time_window)` | 时间窗口修正 |
| 趋势幅度 | `score_trend_amplitude(trend_5d)` | 1.0 |
| 相对强度 | `score_relative_strength(rs)` | 仅strength_score≥1或≤-1时生效 |

概率规则：
- total ≥ 2.0 → 偏多70%+   |   total ≤ -2.0 → 偏空70%+
- total ≥ 1.0 → 偏多60%+   |   total ≤ -1.0 → 偏空60%+
- 其他 → 震荡
- 有效因子 < 3 → 不输出概率，改输出方向倾向

### 5-B/5-C/5-D

关键价位：R1/R2/S1/S2。时段预判按前置判断1输出。
止损（v1.6.0 ATR动态止损）：激进=close - ATR×2, 保守=close - ATR×3。
止盈（v1.6.0 ATR动态止盈）：短线=close + ATR×1.5, 波段=close + ATR×3。
市场波动率判断：`detect_volatility_regime(atr_pct)` — 高波动/正常/低波动。

### 5-E 自动交易计划（v1.8.0 新增）

**v1.8.0 新增：run_analysis() 自动生成交易计划**

在综合判断和日级别趋势完成后，引擎自动生成包含入场参考、止损价、止盈价、止损幅度的完整交易计划：

- **偏多**方向：入场参考 S1~S2 区间，激进止损 = close - ATR×2，短线止盈 = close + ATR×1.5
- **偏空**方向：入场参考当前价，做空止损 = 价格 + ATR×2，做空止盈 = 价格 - ATR×1.5
- **震荡**方向：信号不足，不生成交易计划
- **高波动市场**：自动降级为"观望(高波动)"，不生成具体计划

**v2.0.0 尾盘竞价提醒：** 当系统时间处于 14:57-15:00 时，引擎自动标注尾盘集合竞价阶段，并在 trade_plan 中增加尾盘竞价提醒："当前处于尾盘集合竞价阶段(14:57-15:00)，最终收盘价可能偏离当前价"。

交易计划位于 `results["trade_plan"]`，包含方向、入场参考、止损价/幅度、止盈价/幅度、波动率环境、市场环境。

### 5-F 多周期验证（v1.6.0 新增）

当获取到60分钟和15分钟K线时，调用 `score_multi_timeframe()` 验证日线趋势的持续性：
- 共振向上：日线/60分/15分均线全部多头 → 趋势可靠性高
- 共振向下：全部空头 → 下跌趋势确认
- 方向矛盾：大周期与小周期方向不一致 → 谨慎操作，可能变盘

---

## Step 6：分析引擎与批量筛选（v1.6.0/v1.7.0/v2.0.0）

### 6-A 一键分析引擎 (v1.6.0)

`run_analysis()` 替代上述手动调用流程，一次性完成全部分析并返回结构化结果：

```python
from scripts.engine import run_analysis

result = run_analysis(
    code="002475",
    name="立讯精密",
    time_window="盘前",
    fund_flow_net=None,          # 不传则自动用 infer_fund_activity() 推断
    has_positive_news=True,      # 正面新闻
    has_negative_news=False,
    industry_name="消费电子",    # 行业名（相对强度用）
    market_change=0.01,          # 大盘涨跌幅（小数）
    industry_change=0.02,        # 板块涨跌幅（小数）
    use_cache=True,              # 启用缓存
)
```

返回结构（简化，v2.0.0 新增字段）：
```json
{
  "code": "002475",
  "name": "立讯精密",
  "time_window": "盘前",
  "session_phase": "盘前",                                              # v2.0.0 尾盘竞价时自动切换
  "summary": { /* build_short_summary 完整输出 */ },
  "kline_valid": { "valid": true, "warnings": [] },
  "patterns": ["三连阳"],
  "simple_direction": "偏强",
  "atr": { "atr": 1.2, "atr_pct": 1.5, "stop_loss_aggressive": 78.6, ... },
  "rsi": { "rsi": 65.3, "signal": "正常偏强", "extreme": false },
  "fund_activity": { "activity_label": "放量", "inferred_direction": "放量上涨", ... },  # v1.7.0
  "daily_trend": { "trend": "上升趋势", "strength": "中", ... },                         # v1.7.0
  "momentum": { "momentum": "加速上涨", "size_trend": "扩大", ... },                     # v2.0.0 L4
  "volume_profile": { "volume_pattern": "放量上涨", "accumulation_signal": false, ... },  # v2.0.0 L1
  "factor_scores": { "ma": 1, "volume": 0, "fund_flow": 1, ... },
  "verdict": { "direction": "偏多", "probability": "70%+", ... },
  "limit_status": { "limit_status": "正常", "locked_up": false, ... },                    # v1.9.0
  "industry_comparison": { "relative_position": "领跌", "peers_analyzed": 4, ... },          # v1.9.0
  "relative_strength": { "label_vs_market": "领涨", ... },
  "trade_plan": { "方向": "做多", "入场参考": "78.50~79.80", ... },                       # v1.8.0
  "prediction_recorded": true,
  "warnings": []
}
```

内部执行流程（v2.0.0 完整版）：
```
三指数(缓存) → 个股行情(缓存) → K线(缓存) → 美股
   → build_short_summary → validate_kline → infer_fund_activity
   → detect_candle_patterns → simple_direction
   → compute_atr → compute_rsi
   → detect_momentum_shift (v2.0.0 L4) + analyze_volume_profile (v2.0.0 L1)
   → 6因子评分 → compute_total_score
   → relative_strength → check_limit_status (v1.9.0) → industry_peer_comparison (v1.9.0)
   → detect_daily_trend (v1.7.0) → record_prediction
```

### 6-B 短线信号历史回测（v2.0.0 新增）

对指定股票在历史数据中逐日回放评分逻辑，验证预测准确率：

```python
from scripts.backtest_st import backtest_short_term, print_backtest_report

# 回测最近120个交易日
backtest = backtest_short_term("002475", lookback=120)
print(print_backtest_report(backtest))
```

输出示例：
```
=== 短线信号回测报告: 002475 ===
回测周期: 99个交易日
（注意：仅基于技术面因子，不含美股/新闻数据，结果低于完整方案）

信号准确率:
  偏多: 65.3% (32/49) 均收益:+0.85%
  偏空: 55.6% (10/18) 均收益:-0.62%
  震荡: 40.6% (13/32)
  总体: 55.6%

策略收益: +12.34% vs 买入持有:+8.21%
超额收益: +4.13%
最大连败: 5次 | 盈亏比:1.52
```

注意：`backtest_short_term` 的回测是简化的——因为回放时无法获取真实的历史美股行情和新闻数据，所以只用了技术面因子（均线）。这是一个"技术面因子单独回测"，结果会略低于完整方案的准确率。

### 6-C 批量筛选排序 (v1.7.0 新增)

对多只股票统一调用 `run_analysis()`，按信号强度排序输出，适合板块轮动/自选股池筛选：

```python
from scripts.screener import screen_stocks, print_screen_results

stock_list = [
    {"code": "002475", "name": "立讯精密", "industry": "消费电子代工"},
    {"code": "601138", "name": "工业富联", "industry": "消费电子代工"},
    {"code": "300750", "name": "宁德时代", "industry": "电池"},
]

result = screen_stocks(stock_list, time_window="盘前", min_n_active=3)
print(print_screen_results(result))
```

输出示例：
```
=== 批量筛选结果 ===
共分析3只股票，3只成功

排名 代码   名称       方向  总分 因子 均线  RSI      ATR
───────────────────────────────────────────────
1    002475 立讯精密  偏多  2.0  4    多头  正常偏弱 正常波动
2    300750 宁德时代  震荡  0.0  3    震荡  正常偏弱 低波动
3    601138 工业富联  偏空  -1.0 3    空头  正常偏弱 正常波动

最佳信号: 002475 立讯精密 — 偏多(总分2.0), 均线多头, RSI正常偏弱
```

排序规则：偏多 > 震荡 > 偏空；同方向总分降序；同分有效因子数降序；同分同因子非高波动优先。

### 6-D 自动分析摘要 (v2.1.0 新增)

对 `run_analysis()` 返回的完整结果自动生成一句话分析摘要，适合报告开头快速呈现核心结论：

```python
from scripts.engine import summarize_analysis

result = run_analysis(code="002475", name="立讯精密", time_window="盘前")
summary = summarize_analysis(result)
print(summary)
# 输出示例：
# 立讯精密(002475) 当前68.24(-8.30%)，均线震荡，加速下跌，放量下跌，市场高波动，判断偏空(60%+)，入场68.24止损63.30止盈72.50。
```

`summarize_analysis()` 从结果中自动提取：标的名称、当前价、涨跌幅、均线排列、动量方向、量价模式、异常状态（涨跌停/逼近等）、市场情绪、综合判断方向及概率、交易计划（入场/止损/止盈），拼接为一段完整的中文分析摘要。

### 6-E 批量回测验证 (v2.1.0 新增)

`screen_and_backtest()` 将批量筛选与回测验证结合，先筛选出信号最强的股票，再对 Top N 做历史回测，最终给出强推荐/弱推荐/不推荐：

```python
from scripts.screener import screen_and_backtest

stock_list = [
    {"code": "002475", "name": "立讯精密", "industry": "消费电子代工"},
    {"code": "601138", "name": "工业富联", "industry": "消费电子代工"},
    {"code": "300750", "name": "宁德时代", "industry": "电池"},
]

result = screen_and_backtest(stock_list, time_window="盘前", top_n=3)
print(result["summary"])
# 输出示例：共筛选3只，回测前3只。强推荐: 立讯精密(002475)

# 查看详细回测结果
for item in result["backtested_top"]:
    print(f"{item['name']}: {item['final_verdict']} ({item['reason']})")
```

决策逻辑：
- **强推荐**：筛选方向与回测方向一致，且回测准确率 > 60%
- **弱推荐**：筛选方向与回测方向一致，且回测准确率 > 50%
- **不推荐**：回测准确率不足或方向不一致

返回结构包含 `screen_result`（原始筛选输出）、`backtested_top`（回测详情列表）、`recommendations`（强推荐标的）、`summary`（一句话概括）。

---

## Step 7：输出报告

顺序：
1. **市场环境**（三大指数+涨跌+行业+美股+北向）
2. **技术面**（均线→量→支撑阻力→K线形态→资金→动量趋势→成交量深度）
3. **事件驱动**（新闻相关度+题材）
4. **综合判断**（方向概率或方向倾向+价位+时段+止损）
5. **风险声明**（数据来源+时间+缺失项列表）

---

## Step 8：记录预测（复盘用）

输出报告后，将本次预测记录到复盘系统：

```python
from scripts.tracker import record_prediction

record_prediction(
    code=code,
    name=name,
    direction=result["direction"],
    confidence=result.get("probability", "60%+"),
    price=ss["p"],
    factor_detail=result.get("factor_detail", ""),
)
```

### 自动回填（v1.8.0 新增）

`auto_fill_pending()` 自动遍历 predictions.json 中尚未回填（result=None）的记录，对 >=3 日的预测获取最新价格并判定结果：

```python
from scripts.tracker import auto_fill_pending

result = auto_fill_pending()
# result: {"filled": 3, "skipped": 1, "errors": 0, "details": ["002475 2026-06-23 偏多→正确(+2.3%)", ...]}
```

也可注入自定义行情函数：
```python
def my_quote(code):
    return custom_api(code)
auto_fill_pending(quote_fn=my_quote)
```

### 复盘命令

用户可随时查询预测准确率：

```
from scripts.tracker import print_review, review_accuracy

# 输出可读复盘报告
print_review(days=30)

# 或获取统计数据
stats = review_accuracy(days=30)
```

---

## 相关

- [[scripts/data.py]] — 自建轻量数据通道
- [[scripts/cache.py]] — 文件缓存
- [[scripts/patterns.py]] — K线形态识别
- [[scripts/scoring.py]] — 因子评分系统
- [[scripts/backtest_st.py]] — 短线信号历史回测
- [[scripts/tracker.py]] — 预测记录与复盘
