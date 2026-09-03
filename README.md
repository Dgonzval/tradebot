# TradeBot

An autonomous trading assistant that watches the market 24/7, reads the news, and turns it all into AI-generated trading signals — delivered straight to Telegram and a live dashboard.

It tracks a configurable portfolio (BTC, ETH, AAPL by default) in real time, computes 15+ technical indicators, and uses Claude to reason about price action, fundamentals, and breaking news before producing a BUY/SELL/HOLD call with a confidence score and target price. Every signal is logged and later scored against what actually happened, so the model's accuracy is measurable over time — not just claimed.

> The bot does not place real trades. It generates signals and alerts only.

## Features

- **AI-driven signals** — Claude analyzes indicators, fundamentals, and news together to produce a reasoned BUY/SELL/HOLD call with confidence and target price
- **Real-time market data** — price and OHLCV history for crypto and stocks, with automatic fallback across providers if one is unavailable
- **15+ technical indicators** — oscillators, trend, volatility, volume, momentum, and support/resistance levels, computed over 90 days of history
- **Stock fundamentals & options data** — P/E, P/B, ROE, margins, dividend yield, put/call ratio, and implied volatility for equities
- **News monitoring** — per-ticker news fetched and cached, with AI-assessed impact
- **Telegram bot** — check prices, positions, indicators, news, and signal accuracy from chat, and get pushed alerts for stop-loss/take-profit and daily reports
- **Interactive dashboard** — portfolio, indicators, and signals visualized with Streamlit + Plotly
- **Automated PDF reports** — daily portfolio summary, top news with AI impact analysis, active signals, and risk assessment
- **TradingView webhook ingestion** — accepts external alerts as another signal source
- **Self-evaluating feedback loop** — every AI signal is checked against real price movement 7 days later to track historical accuracy per asset

## Tech Stack

| Layer | Technology |
|---|---|
| API & scheduling | FastAPI, APScheduler |
| AI | Claude (Anthropic), with prompt caching |
| Data & analysis | pandas, numpy, yfinance |
| Database | PostgreSQL (SQLAlchemy ORM) |
| Cache | Redis |
| Messaging bot | python-telegram-bot |
| Dashboard | Streamlit + Plotly |
| News | NewsAPI |
| Reports | ReportLab (PDF) |
| Validation | Pydantic |

**Market data sources**, in priority order with automatic fallback: Yahoo Finance (primary, all assets) → CoinGecko (crypto) / Alpha Vantage (stocks).

## How it works

```
                 ┌───────────────┐
                 │  Schedulers    │  price/news polling, daily report,
                 │ (APScheduler)  │  signal outcome evaluation
                 └───────┬────────┘
                          │
   Market data ──▶  ┌────▼────┐   Technical    ┌───────────┐
   (Yahoo/CoinGecko/ │  main.py│──indicators──▶ │ AIAnalyzer │──▶ Claude
    Alpha Vantage)    │ FastAPI │◀── + news ────│ (ai_analyzer)│    signal
                       └────┬────┘                └───────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼              ▼
        PostgreSQL       Redis        Telegram bot
       (positions,      (cache)      (commands + alerts)
        signals,
        outcomes)             ▲
              │                │
              ▼                │
        PDF reports      Streamlit dashboard
```

## Technical Indicators

Computed with pandas/numpy over 90 days of OHLCV data:

| Category | Indicators |
|---|---|
| Oscillators | RSI 14, Williams %R, CCI 20, Stochastic K/D |
| Trend | MACD, EMA 9/21, SMA 20/50, VWAP |
| Volatility | ATR 14, Bollinger Bands (% width) |
| Volume | OBV + trend, ratio vs. 20-period average |
| Levels | Fibonacci (7 levels), Support/Resistance |
| Momentum | 1d / 7d / 14d / 30d change |
| Fundamentals (stocks only) | P/E, P/B, ROE, Market Cap, margins, dividend |
| Options (stocks only) | Put/Call ratio, average IV, bullish/bearish skew |

## Project Structure

```
TradeBot/
├── Requirements/files/
│   ├── main.py                  # FastAPI app, scheduler jobs, API endpoints
│   ├── telegram_bot.py          # Telegram bot and its commands
│   ├── ai_analyzer.py           # Claude-based signal analysis
│   ├── technical_indicators.py  # RSI, MACD, Bollinger, ATR, VWAP...
│   ├── yf_session.py            # Market data layer with provider fallback
│   ├── dashboard.py             # Streamlit dashboard
│   ├── pdf_generator.py         # PDF report generation
│   ├── models.py                # SQLAlchemy models
│   ├── database.py              # PostgreSQL connection
│   ├── cache.py                 # Redis wrapper
│   ├── news_fetcher.py          # NewsAPI integration
│   └── config.py                # Runtime configuration
├── Dockerfile
└── requirements.txt
```

## Getting Started

### Requirements

- Python 3.10+
- PostgreSQL and Redis (locally or via Docker)
- API keys: Anthropic (Claude), Telegram Bot token, NewsAPI, Alpha Vantage

### Install

```bash
git clone <this-repo>
cd TradeBot

python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
```

### Configure

Create a `.env` file with your credentials and portfolio settings:

```env
CLAUDE_API_KEY=sk-ant-xxxxxxx
TELEGRAM_BOT_TOKEN=123456:ABCdef...
TELEGRAM_CHAT_ID=your_chat_id
NEWS_API_KEY=xxxxxxx
ALPHA_VANTAGE_API_KEY=xxxxxxx
DATABASE_URL=postgresql://user:password@localhost:5432/trading_bot
REDIS_URL=redis://localhost:6379
PORTFOLIO_SYMBOLS=BTC,ETH,AAPL
STOP_LOSS_PERCENT=5
TAKE_PROFIT_PERCENT=10
PRICE_CHECK_INTERVAL=30
NEWS_CHECK_INTERVAL=180
```

### Run

```bash
cd Requirements/files

# API backend
python -m uvicorn main:app --reload

# Telegram bot
python telegram_bot.py

# Dashboard
python -m streamlit run dashboard.py
```

## API Overview

```
GET  /health                        # API + Redis status
GET  /positions                     # Portfolio positions with P&L
POST /positions                     # Create a position
PUT  /positions/{symbol}            # Update quantity/price
DELETE /positions/{symbol}          # Remove a position
GET  /portfolio-value               # Total portfolio value (USD)
GET  /indicators/{symbol}           # Computed technical indicators
GET  /news                          # Cached news
GET  /signals?limit=20              # Received signals
GET  /signals/ai-stats              # Historical AI accuracy
POST /tradingview-webhook           # Ingest TradingView alerts
POST /report/generate               # Generate a PDF report on demand
GET  /report/download/{filename}    # Download a generated report
```

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Main menu |
| `/posiciones` | Open positions, P&L, and total value |
| `/precio <symbol>` | Current price and daily % change |
| `/indicadores <symbol>` | RSI, MACD, Bollinger, VWAP, fundamentals... |
| `/noticias` | Latest news per asset |
| `/senales` | Signals received from TradingView |
| `/precision` | Historical accuracy of AI signals |
| `/reporte` | Generate and send a full PDF report |
| `/help` | List of commands |

## AI Feedback Loop

Every signal Claude generates is stored, and a daily job re-checks signals that are 7+ days old: it computes the real P&L, marks whether the predicted direction was correct, and rolls the result into per-asset accuracy stats — so the model's track record is visible via `/signals/ai-stats`, not just assumed.

## Roadmap

- [x] Core API, database, and Telegram bot
- [x] News ingestion and TradingView webhooks
- [x] Claude-based analysis, PDF reports, technical indicators
- [x] Streamlit dashboard
- [x] AI signal accuracy feedback loop
- [ ] Real order execution (Alpaca)

## Disclaimer

This project is for research and educational purposes. It does not execute real trades and nothing it outputs constitutes financial advice.
