# Trading Bot con IA 24/7

Bot de trading autónomo que analiza mercados, noticias y genera señales con Claude IA. Monitorea BTC, ETH y AAPL en tiempo real con +15 indicadores técnicos, alertas Telegram y reportes PDF diarios.

## Stack

- **Backend**: FastAPI + APScheduler
- **BD**: PostgreSQL 16 + Redis 7 (Docker)
- **IA**: Claude Sonnet (Anthropic) con prompt caching
- **Datos**: Yahoo Finance API directa → CoinGecko (crypto) / Alpha Vantage (stocks) como fallback
- **Noticias**: NewsAPI
- **Alertas**: Telegram Bot
- **Dashboard**: Streamlit + Plotly
- **Reportes**: ReportLab PDF
- **Deploy**: Hostinger KVM1 VPS via Dokploy

---

## Quick Start

### 1. Requisitos

- Python 3.10+
- Docker y Docker Compose
- Token de Telegram Bot (`@BotFather`)
- API Key de Claude (console.anthropic.com)
- API Key de NewsAPI (newsapi.org)
- API Key de Alpha Vantage (alphavantage.co) — fallback gratuito para stocks

### 2. Entorno virtual e instalación

```bash
git clone <tu-repo>
cd trading-bot

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Variables de entorno

Crea `.env` en la carpeta `Requirements/files/`:

```env
CLAUDE_API_KEY=sk-ant-xxxxxxx
TELEGRAM_BOT_TOKEN=123456:ABCdef...
TELEGRAM_CHAT_ID=tu_chat_id
NEWS_API_KEY=xxxxxxx
ALPHA_VANTAGE_API_KEY=xxxxxxx
DATABASE_URL=postgresql://trading_user:secure_password_123@localhost:5432/trading_bot
REDIS_URL=redis://localhost:6379
PORTFOLIO_SYMBOLS=BTC,ETH,AAPL
STOP_LOSS_PERCENT=5
TAKE_PROFIT_PERCENT=10
PRICE_CHECK_INTERVAL=30
NEWS_CHECK_INTERVAL=180
```

### 4. Levantar infraestructura

```bash
cd Requirements/files
docker-compose up -d postgres redis

# Verificar
docker ps
# → trading_bot_db (PostgreSQL) y trading_bot_cache (Redis)
```

### 5. Ejecutar

```bash
cd Requirements/files

# Terminal 1 — API Backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# → http://localhost:8000

# Terminal 2 — Bot de Telegram
python telegram_bot.py

# Terminal 3 — Dashboard
python -m streamlit run dashboard.py
# → http://localhost:8501
```

---

## Estructura del Proyecto

```
trading-bot/
├── Requirements/files/
│   ├── main.py                  # FastAPI + APScheduler + endpoints
│   ├── telegram_bot.py          # Bot Telegram con todos los comandos
│   ├── ai_analyzer.py           # Análisis con Claude IA
│   ├── technical_indicators.py  # RSI, MACD, Bollinger, ATR, VWAP...
│   ├── yf_session.py            # Capa de datos: YF → CoinGecko / AlphaVantage
│   ├── dashboard.py             # Dashboard Streamlit interactivo
│   ├── pdf_generator.py         # Reportes PDF automáticos
│   ├── models.py                # Modelos SQLAlchemy (DB)
│   ├── database.py              # Conexión PostgreSQL
│   ├── cache.py                 # Wrapper Redis
│   ├── news_fetcher.py          # NewsAPI por ticker
│   ├── config.py                # Variables de configuración
│   └── docker-compose.yml       # PostgreSQL + Redis + pgAdmin (local)
├── docker-compose.prod.yml      # Deploy producción (5 servicios)
├── Dockerfile
├── requirements.txt
└── .env                         # Credenciales (no commitear)
```

---

## Fuentes de Datos

| Fuente | Uso | Límite |
|---|---|---|
| Yahoo Finance API v8 | Precio + historial OHLCV (todos los tickers) | Sin límite conocido |
| CoinGecko | Precio + historial crypto (fallback) | ~30 req/min gratis |
| Alpha Vantage | Precio + historial stocks (fallback) | 25 req/día gratis |

> Yahoo Finance es la fuente primaria para todos los activos (incluido BTC-USD, ETH-USD con volumen real). Si es bloqueado en el servidor, cae automáticamente al fallback correspondiente.

---

## Indicadores Técnicos

Calculados con pandas/numpy sobre 90 días de datos OHLCV:

| Categoría | Indicadores |
|---|---|
| Osciladores | RSI 14, Williams %R, CCI 20, Estocástico K/D |
| Tendencia | MACD, EMA 9/21, SMA 20/50, VWAP |
| Volatilidad | ATR 14, Bollinger Bands (ancho %) |
| Volumen | OBV + tendencia, ratio vs media 20 |
| Niveles | Fibonacci (7 niveles), Soporte/Resistencia |
| Momentum | Cambio 1d / 7d / 14d / 30d |
| Fundamentales | P/E, P/B, ROE, Market Cap, margen, dividendo (solo stocks) |
| Opciones | Put/Call ratio, IV promedio, sesgo bullish/bearish (solo stocks) |

---

## API Endpoints

```bash
GET  /health                        # Estado API + Redis
GET  /positions                     # Posiciones con P&L
POST /positions                     # Crear posición
PUT  /positions/{symbol}            # Actualizar cantidad/precio
DELETE /positions/{symbol}          # Eliminar posición
GET  /portfolio-value               # Valor total en USD
GET  /indicators/{symbol}           # Indicadores técnicos calculados
GET  /news                          # Noticias cacheadas
GET  /signals?limit=20              # Señales TradingView
GET  /signals/ai-stats              # Precisión histórica IA
POST /tradingview-webhook           # Recibir alertas TradingView
POST /report/generate               # Generar PDF ahora
GET  /report/download/{filename}    # Descargar PDF
```

> El puerto 8000 está vinculado a `127.0.0.1` — no es accesible públicamente. Solo los contenedores internos y el proxy de Dokploy pueden acceder.

### Webhook TradingView

```json
POST /tradingview-webhook
{
  "ticker": "BTCUSD",
  "action": "buy",
  "close": 65000,
  "exchange": "BINANCE",
  "interval": "1h"
}
```

---

## Comandos Telegram

| Comando | Descripción |
|---|---|
| `/start` | Menú principal con botones |
| `/posiciones` | Posiciones abiertas + P&L + valor total |
| `/precio BTC` | Precio actual + cambio % del día |
| `/indicadores BTC` | RSI, MACD, Bollinger, VWAP, fundamentales... |
| `/noticias` | Últimas noticias por activo |
| `/senales` | Señales recibidas de TradingView |
| `/precision` | % de acierto histórico de señales IA |
| `/reporte` | Genera y envía PDF con análisis completo |
| `/help` | Lista de comandos |

---

## Reportes PDF Automáticos

Generados diariamente a las **8:00 AM UTC** y bajo demanda via `/reporte`:

- Resumen de cartera con P&L por posición
- Top 5 noticias + análisis de impacto IA
- Señales BUY/SELL/HOLD con confianza y precio objetivo
- Precisión histórica de señales IA (cuando hay datos evaluados)
- Evaluación de riesgo del portafolio
- Recomendaciones concretas
- Aviso legal

---

## Feedback Loop IA

Cada señal generada queda registrada en `ai_signal_outcomes`. Un job diario a las **9:00 AM UTC** evalúa señales de hace 7+ días:

- Calcula P&L real obtenido
- Marca si la dirección fue correcta (BUY → subió, SELL → bajó)
- Acumula estadísticas de precisión por activo

```bash
curl http://localhost:8000/signals/ai-stats
```

---

## Base de Datos

### Acceso visual — pgAdmin (solo local)

```
http://localhost:5050
Email:    admin@example.com
Password: admin

Servidor → Host: trading_bot_db  Port: 5432
DB: trading_bot  User: trading_user  Password: secure_password_123
```

### Acceso por terminal

```bash
docker exec -it trading_bot_db psql -U trading_user -d trading_bot
```

```sql
\dt
SELECT * FROM positions;
SELECT * FROM trading_signals;
SELECT * FROM ai_signal_outcomes WHERE evaluated = true;
\q
```

### Tablas

| Tabla | Descripción |
|---|---|
| `positions` | Cartera: símbolo, cantidad, precio entrada/actual |
| `trading_signals` | Señales recibidas de TradingView |
| `ai_signal_outcomes` | Señales IA + resultado real 7 días después |

---

## Schedulers (tareas automáticas)

| Tarea | Frecuencia | Descripción |
|---|---|---|
| `fetch_prices` | Cada 30 min | Actualiza precios + alertas stop-loss/take-profit |
| `fetch_news` | Cada 180 min | Obtiene noticias de NewsAPI y cachea en Redis |
| `generate_daily_report` | 08:00 AM UTC | Genera PDF + notifica Telegram |
| `evaluate_signal_outcomes` | 09:00 AM UTC | Evalúa señales de hace 7 días |

---

## Deploy en Producción

### Hostinger KVM1 VPS + Dokploy (configuración actual)

1. Crear proyecto en Dokploy apuntando al repo de GitHub
2. Configurar variables de entorno en Dokploy (no usar `.env` en producción)
3. Añadir dominio y SSL via Let's Encrypt en Dokploy
4. Desplegar — Dokploy auto-redeploya en cada push a `main`

**Variables requeridas en Dokploy:**
```
CLAUDE_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
NEWS_API_KEY, ALPHA_VANTAGE_API_KEY,
POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB,
PORTFOLIO_SYMBOLS=BTC,ETH,AAPL,
PRICE_CHECK_INTERVAL=30, NEWS_CHECK_INTERVAL=180
```

---

## Seguridad

- `.env` está en `.gitignore` — nunca commitear credenciales
- Puerto 8000 (API) vinculado a `127.0.0.1` — no expuesto públicamente
- Puerto 8501 (Dashboard) accesible via dominio con SSL
- El bot NO ejecuta órdenes reales — solo genera señales y alertas

---

## Estado del Proyecto

| Fase | Estado | Descripción |
|---|---|---|
| Fase 1 — MVP | Completada | FastAPI, DB, precios, Telegram básico |
| Fase 2 — Datos | Completada | NewsAPI, Redis, TradingView webhooks |
| Fase 3 — IA | Completada | Claude análisis, PDF, indicadores técnicos |
| Fase 4 — Dashboard | Completada | Streamlit con 5 tabs, +15 indicadores |
| Fase 5 — Feedback Loop | Completada | Evaluación automática de señales IA |
| Fase 6 — Servidor | Completada | Deploy Hostinger VPS + Dokploy + dominio SSL |
| Fase 7 — Alpaca | Pendiente | Ejecución real de órdenes |

---

**Última actualización**: Abril 2026
