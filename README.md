# temp-omni-analysis
temp-omni-analysis is a short-term / intraday A-share stock analysis skill designed for event-driven and technical analysis. It is triggered when users request same-day price movement predictions, short-term trading guidance, or market commentary incorporating overnight US market trends and breaking news.

Key features:


Time-window classification — automatically detects whether the request falls into pre-market (8:30-9:25), morning session (9:30-11:30), afternoon session (12:30-15:00), post-market review (15:00-17:00), or weekend/off-day prediction mode


Tiered data sourcing — primary data via a-stock-data SDK functions (Tencent quotes, Baidu candlestick charts, Sina financials, East Money fund flows, THS north-bound capital); secondary via wiki knowledge base for historical patterns; tertiary via web search as fallback


Three-phase data collection — phase 1 (free, non-rate-limited): Tencent quotes + Baidu K-lines + Sina US markets; phase 2 (East Money rate-limited): sector rankings, fund flows, news; phase 3 (low-latency): north-bound capital, THS hot stock reasons


Probabilistic output — instead of binary buy/hold/sell, outputs a weighted directional probability (60%/70%/neutral) based on 5 factors: moving average alignment, volume-price relationship, fund flows, event catalysts, and US market transmission


US market transmission analysis — fetches DJI/IXIC/INX closing data from Sina (free, no API key), applies time-decay weighting (full weight during morning, half-weight in afternoon, flagging stale data on weekends)


Weighted factor model — each factor contributes +1(bullish)/-1(bearish)/0(neutral), with confidence modifiers (weekend US data=0.5x, off-hours=0.3x). Total score maps to probability bands; insufficient factors (<3) fall back to directional tendency


Counterparty risk flags — supports/resistance levels (S1/S2/R1/R2), stop-loss suggestions, time-window specific predictions (morning open bias, afternoon reversal signals, post-market next-day outlook)



Skill size: 180 lines, 7.6KB — optimized for minimal token consumption.
