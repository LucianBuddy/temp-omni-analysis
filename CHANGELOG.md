# 变更记录

格式：`v主版本.次版本.修订号`，规则：
- **主版本**（x.0.0）：架构优化或重构
- **次版本**（0.x.0）：功能模块增减
- **修订号**（0.0.x）：Bug修复或模块内部优化

---

## v2.1.0 (2026-06-26)

两项增强：自动分析摘要 + 批量回测验证。

### M2: 自动分析摘要
- engine.py 新增 summarize_analysis() — 自动生成一句话分析摘要，从 run_analysis 的27个输出字段中提取关键信息

### M3: 批量回测验证
- screener.py 新增 screen_and_backtest() — 批量筛选+回测验证闭环，输出强推荐/弱推荐/不推荐

### SKILL.md
- 版本号 v2.0.0 → v2.1.0
- 新增 summarize_analysis 和 screen_and_backtest 说明

---

## v2.0.0 (2026-06-26)

四项增强：趋势加速/衰减 + 成交量深度分析 + 尾盘集合竞价感知 + 短线信号回测。

### L4: 趋势加速/衰减检测
- data.py 新增 `detect_momentum_shift()` — 检测趋势加速/衰减，比较K线实体大小趋势（扩大/收缩）
- 反转K线自动识别：十字星、长下影（底部反转）、长上影（顶部反转）
- 连续同向K线数计数，用于识别连涨/连跌势头

### L1: 成交量能深度分析
- data.py 新增 `analyze_volume_profile()` — 成交量能深度分析
- 量价模式识别：放量上涨/放量下跌/缩量企稳/缩量阴跌/正常
- 主力行为推断：吸筹信号（缩量+企稳）、派发信号（放量+连跌）
- 异常放量检测（>均值×2.5）、波动率收缩识别（变盘前兆）
- 最大成交量在价格区间的位置分析（顶部/底部/中部）

### L3: 尾盘集合竞价感知
- engine.py 集成尾盘集合竞价时段感知（14:57-15:00）
- 尾盘竞价阶段自动标注 `session_phase` 字段
- trade_plan 增加尾盘竞价提醒："最终收盘价可能偏离当前价"

### L2: 短线信号历史回测
- 新增 `scripts/backtest_st.py` — 短线信号历史回测模块
- `backtest_short_term()` — 逐日回放评分逻辑，对比次日实际涨跌
- 输出偏多/偏空/震荡准确率、策略收益 vs 买入持有
- `print_backtest_report()` — 格式化回测报告输出
- 注意：仅基于技术面因子（均线），不含美股/新闻数据

### engine.py 集成
- 新增 `detect_momentum_shift` 和 `analyze_volume_profile` 集成到 run_analysis()
- 结果新增 `session_phase`、`momentum`、`volume_profile` 字段
- 尾盘竞价（14:57-15:00）自动检测并提示

### SKILL.md
- 版本号 v1.9.0 → v2.0.0
- Step 2-4: 新增动量趋势 + 成交量深度分析说明
- Step 6: 新增 backtest_st.py 引用
- 模块列表更新

---

## v1.9.0 (2026-06-26)

两项增强：涨跌停板分析 + 行业联动对比。

### K1: 涨跌停板分析
- data.py::tencent_quote() 增加 limit_up/limit_down 字段（腾讯行情索引47=涨停价、48=跌停价）
- 新增 data.py::check_limit_status() — 检查涨跌停状态（封板/逼近/正常），返回 locked_up/locked_down、距离百分比等

### K3: 行业联动对比
- 新增 scoring.py::industry_peer_comparison() — 个股 vs 同行对比（领涨/领跌/跟随/逆势），分析板块内资金分化
- 板块全部上涨/下跌/分化的分类识别

### engine.py 集成
- run_analysis() 新增 peer_quotes 参数（同行行情 dict），用于行业联动分析
- 结果新增 limit_status 和 industry_comparison 字段

### SKILL.md
- 版本号 v1.8.0 → v1.9.0
- Step 2-4: 新增涨跌停板分析（check_limit_status）调用说明
- Step 5: 新增行业联动分析（industry_peer_comparison）调用说明
- run_analysis 参数：增加 peer_quotes 说明
- 模块列表更新

---

## v1.8.0 (2026-06-26)

三项增强：预测自动回填 + 市场可交易性评估 + 自动交易计划。

### J1: 预测自动回填
- 新增 `tracker.py::auto_fill_pending()` — 自动遍历 predictions.json 中未回填记录
- 对 >=3 日的预测获取最新行情价格，计算涨跌幅判定正确/错误
- 支持自定义行情函数注入（依赖注入，便于测试）
- 完成"记录→回填→复盘"完整闭环

### J3: 市场可交易性评估
- 新增 `data.py::assess_market_tradeability()` — 四大指数(000001/399001/399006/000688) 评估
- 判断指数一致性（一致上涨/一致下跌/分化）和波动率（>2%为宽幅震荡）
- 输出 tradeable/sentiment/detail 等综合判断
- 零外部依赖，纯使用已有指数数据

### J4: 自动交易计划生成
- engine.py 的 run_analysis() 结果新增 `market_tradeability` 和 `trade_plan` 字段
- 偏多方向：给出入场参考区间 S1~S2 + ATR 止损止盈
- 偏空方向：给出做空入场 + ATR 止损止盈
- 高波动市场自动降级为"观望(高波动)"

### SKILL.md
- 版本号 v1.7.0 → v1.8.0
- Step 2-4: 新增市场可交易性评估说明
- Step 5: 新增自动交易计划说明
- Step 8: 新增自动回填说明
- 模块总览首位置更新为 v1.8.0 功能

---

## v1.7.0 (2026-06-26)

三项增强：资金流自动推断 + 日级别趋势跟踪 + 批量筛选排序。

### H1: 批量筛选排序
- 新增 `scripts/screener.py` — `screen_stocks()` / `print_screen_results()`
- 对多只股票并行调用 `run_analysis()`，按信号强度排序输出
- 排序规则：方向 > 总分 > 有效因子数 > 波动率
- 最低有效因子数过滤（默认3），支持错误捕获和汇总

### H4: 资金流自动推断
- 新增 `data.py::infer_fund_activity()` — 通过成交额/成交量推断资金活跃度（无需东财API）
- 放量上涨推断为净流入，放量下跌推断为净流出，缩量/正常量为中性
- 引擎中自动将推断结果传入 factor_scores.fund_flow
- `run_analysis(fund_flow_net=None)` 默认自动推断，传值则用传入值

### H5: 日级别趋势跟踪
- 新增 `data.py::detect_daily_trend()` — 均线排列+高低点抬升判断日线趋势
- 输出趋势方向、强度、MA60位置、持续天数、一句话描述
- 引擎结果新增 `daily_trend` 字段，为短线判断提供中线大背景

### engine.py 集成
- `run_analysis()` 结果新增 `fund_activity` 和 `daily_trend` 字段
- 当 `fund_flow_net=None` 时自动调用 `infer_fund_activity()`
- 因子评分前插入资金流自动推断流程
- 接口不变，向后兼容

### SKILL.md
- 版本号 v1.6.0 → v1.7.0
- Step 1.5: 增加 infer_fund_activity() 调用说明
- Step 2-4: 增加 detect_daily_trend() 调用说明
- 新增 Step 6-B: screen_stocks() 批量筛选排序
- 更新引擎返回结构，标注 v1.7.0 新增字段

---

## v1.6.0 (2026-06-26)

六项增强：ATR波动率止损 + RSI超买超卖 + 数据完整性检查 + 多周期K线 + 相对强度 + 一键分析引擎。

### G1: ATR 波动率止损
- 新增 `data.py::compute_atr()` — ATR计算 + 动态止损/止盈位
- 新增 `data.py::detect_volatility_regime()` — 波动率环境判断（高/正常/低波动）

### G2: RSI 超买超卖
- 新增 `data.py::compute_rsi()` — RSI指标计算 + 超买/超卖/极值信号

### G3: 数据完整性检查
- 新增 `data.py::validate_kline()` — K线数据完整性校验（根数/停牌/日期跳跃/空字段）

### G4: 多周期K线支持
- `data.py::baidu_kline_with_ma()` 签名增加 `ktype` 参数，支持日线/5/15/30/60分钟K线
- 新增 `scoring.py::score_multi_timeframe()` — 多周期均线共振评分

### G5: 相对强度
- 新增 `scoring.py::relative_strength()` — 个股 vs 板块/大盘的相对强度计算
- 新增 `scoring.py::score_relative_strength()` — 相对强度因子分转化
- 新增 `scoring.py::INDUSTRY_INDEX_MAP` — 常用板块指数腾讯代码映射

### G6: 一键分析引擎
- 新增 `scripts/engine.py` 和 `run_analysis()` — 将9步手动调用整合为单个函数，支持缓存、数据校验、全自动评分

### SKILL.md
- 版本号 v1.5.0 → v1.6.0
- 新增模块总览表（v1.6.0 新增功能）
- Step 1.5: 增加 validate_kline() 调用
- Step 2-4: 增加 ATR/RSI 的调用示例和说明
- Step 5: 增加多周期共振和相对强度调用示例
- 新增 Step 6: run_analysis() 一键分析引擎
- 原 Step 6/7 → Step 7/8
- Step 5-B: ATR动态止损止盈替代固定价位

---

## v1.5.0 (2026-06-26)

三阶段架构优化，彻底去除对 a-stock-data 的依赖。

### 第一阶段：节流为主
- 创建 scripts/ 目录结构
- 新增 `scripts/data.py` — 轻量数据层（tencent_quote / baidu_kline_with_ma / sina_us_quote + build_short_summary），零外部依赖
- 新增 `scripts/cache.py` — 文件缓存系统（按分类TTL自动清除）

### 第二阶段：提升质量
- 新增 `scripts/patterns.py` — K线形态自动识别（十字星/锤子线/吞没/三连阳阴/晨星暮星 + simple_direction）
- 新增 `scripts/scoring.py` — 因子评分系统（均线/量价/资金/事件/美股/趋势 → 综合方向概率）

### 第三阶段：复盘能力
- 新增 `scripts/tracker.py` — 预测记录与复盘模块（record_prediction / fill_result / review_accuracy / print_review / report_bias）

### SKILL.md
- 重写 SKILL.md，v1.0.0 → v1.5.0
- Step 1 数据采集：a-stock-data 引用 → scripts/data.py
- Step 1.5 数据摘要：手算 → build_short_summary()
- Step 2-4 技术分析：新增 patterns.py 引用
- Step 5 综合判断：新增 scoring.py 引用
- Step 7 记录预测：新增 tracker.py 引用
- 移除所有 a-stock-data SKILL.md 的依赖
- 新增 scripts/ 目录模块说明

## v1.0.0 (初始版本)

初始发布版。
