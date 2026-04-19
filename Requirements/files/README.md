# Trading Bot con IA 24/7

Bot de trading autónomo que analiza mercados, noticias y genera señales con Claude IA. Monitorea BTC, ETH, AAPL, GOOGL y MSFT en tiempo real con +15 indicadores técnicos, alertas Telegram y reportes PDF diarios.

## Stack

- **Backend**: FastAPI + APScheduler
- **BD**: PostgreSQL 16 + Redis 7 (Docker)
- **IA**: Claude Sonnet (Anthropic) con prompt caching
- **Datos**: Yahoo Finance (precios + fundamentales + opciones)
- **Noticias**: NewsAPI
- **Alertas**: Telegram Bot
- **Dashboard**: Streamlit + Plotly
- **Reportes**: ReportLab PDF

---

## Quick Start

### 1. Requisitos

- Python 3.10+
- Docker y Docker Compose
- Token de Telegram Bot (`@BotFather`)
- API Key de Claude (console.anthropic.com)
- API Key de NewsAPI (newsapi.org)

### 2. Instalación

```bash
git clone <tu-repo>
cd trading-bot

pip install fastapi uvicorn sqlalchemy psycopg2-binary redis apscheduler \
    python-telegram-bot yfinance anthropic reportlab streamlit plotly \
    requests pandas numpy newsapi-python python-dotenv
```

### 3. Variables de entorno

Crea `.env` en la carpeta del proyecto:

```env
CLAUDE_API_KEY=sk-ant-xxxxxxx
TELEGRAM_BOT_TOKEN=123456:ABCdef...
TELEGRAM_CHAT_ID=tu_chat_id
NEWS_API_KEY=xxxxxxx
DATABASE_URL=postgresql://trading_user:secure_password_123@localhost:5432/trading_bot
REDIS_URL=redis://localhost:6379
PORTFOLIO_SYMBOLS=BTC,ETH,AAPL,GOOGL,MSFT
STOP_LOSS_PERCENT=5
TAKE_PROFIT_PERCENT=10
PRICE_CHECK_INTERVAL=5
NEWS_CHECK_INTERVAL=30
```

### 4. Levantar infraestructura

```bash
docker-compose up -d

# Verificar
docker ps
# → trading_bot_db (PostgreSQL) y trading_bot_cache (Redis)
```

### 5. Ejecutar

```bash
# Terminal 1 — API Backend (crea tablas automáticamente al iniciar)
python main.py
# → http://localhost:8000

# Terminal 2 — Bot de Telegram
python telegram_bot.py

# Terminal 3 — Dashboard (opcional)
streamlit run dashboard.py
# → http://localhost:8501
```

---

## Estructura del Proyecto

```
trading-bot/
├── main.py                  # FastAPI + APScheduler + endpoints
├── telegram_bot.py          # Bot Telegram con todos los comandos
├── ai_analyzer.py           # Análisis con Claude IA
├── technical_indicators.py  # RSI, MACD, Bollinger, ATR, VWAP...
├── dashboard.py             # Dashboard Streamlit interactivo
├── pdf_generator.py         # Reportes PDF automáticos
├── models.py                # Modelos SQLAlchemy (DB)
├── database.py              # Conexión PostgreSQL
├── cache.py                 # Wrapper Redis
├── news_fetcher.py          # NewsAPI por ticker
├── config.py                # Variables de configuración
├── docker-compose.yml       # PostgreSQL + Redis + pgAdmin
└── .env                     # Credenciales (no commitear)
```

---

## Indicadores Técnicos

Calculados con pandas/numpy sobre datos OHLCV de Yahoo Finance (90 días):

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
GET  /news                          # Noticias cacheadas
GET  /signals?limit=20              # Señales TradingView
GET  /signals/ai-stats              # Precisión histórica IA
POST /tradingview-webhook           # Recibir alertas TradingView
POST /report/generate               # Generar PDF ahora
GET  /report/download/{filename}    # Descargar PDF
```

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

Generados diariamente a las **8:00 AM** y bajo demanda via `/reporte`:

- Resumen de cartera con P&L por posición
- Top 5 noticias + análisis de impacto IA
- Señales BUY/SELL/HOLD con confianza y precio objetivo
- Precisión histórica de señales IA (cuando hay datos evaluados)
- Evaluación de riesgo del portafolio
- Recomendaciones concretas
- Aviso legal

---

## Feedback Loop IA

Cada señal generada queda registrada en `ai_signal_outcomes`. Un job diario a las **9:00 AM** evalúa las señales de hace 7+ días comparando el precio en el momento de la señal vs el precio actual:

- Calcula P&L real obtenido
- Marca si la dirección fue correcta (BUY → subió, SELL → bajó)
- Acumula estadísticas de precisión por activo

Consultar en cualquier momento:
```bash
curl http://localhost:8000/signals/ai-stats
```

---

## Base de Datos

### Acceso visual — pgAdmin

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
\dt                            -- listar tablas
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
| `fetch_prices` | Cada 5 min | Actualiza precios + alertas stop-loss/take-profit |
| `fetch_news` | Cada 30 min | Obtiene noticias de NewsAPI y cachea en Redis |
| `generate_daily_report` | 08:00 AM | Genera PDF + notifica Telegram |
| `evaluate_signal_outcomes` | 09:00 AM | Evalúa señales de hace 7 días |

---

## Alertas Automáticas Telegram

El bot envía alertas automáticas cuando:
- Un activo alcanza el **stop-loss** (por defecto -5%)
- Un activo alcanza el **take-profit** (por defecto +10%)
- Se recibe una señal de **TradingView**
- Se genera el **reporte diario**

---

## Configuración de API Keys

### Claude (Anthropic)
1. Ir a [console.anthropic.com](https://console.anthropic.com)
2. Crear API key → pegar en `.env` como `CLAUDE_API_KEY`

### Telegram Bot
1. Abrir Telegram → buscar `@BotFather`
2. `/newbot` → seguir pasos → copiar token
3. Para obtener tu `TELEGRAM_CHAT_ID`: envía un mensaje al bot y visita:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`

### NewsAPI
1. Registrarse en [newsapi.org](https://newsapi.org) (free: 100 req/día)
2. Copiar API key → `NEWS_API_KEY`

---

## Deploy en Producción (próximo paso)

### Opción recomendada — Hetzner VPS (4-5€/mes)

```bash
# En el servidor
curl -fsSL https://get.docker.com | sh
git clone <repo>
cd trading-bot
cp .env.example .env  # rellenar credenciales
docker-compose up -d
python main.py &
python telegram_bot.py &
```

### Otras opciones

| Plataforma | Precio | Notas |
|---|---|---|
| Railway.app | ~$5/mes | Auto-deploy desde GitHub |
| Render.com | Gratis / $7 | Con limitaciones en free tier |
| AWS EC2 t3.micro | ~$8/mes | Más control |

---

## Seguridad

- Nunca commitear `.env` — está en `.gitignore`
- Para producción: usar variables de entorno del servidor, no archivos `.env`
- El bot NO ejecuta órdenes reales (aún) — solo genera señales y alertas
- La integración con Alpaca (ejecución real) está en desarrollo

---

## Estado del Proyecto

| Fase | Estado | Descripción |
|---|---|---|
| Fase 1 — MVP | Completada | FastAPI, DB, precios, Telegram básico |
| Fase 2 — Datos | Completada | NewsAPI, Redis, TradingView webhooks |
| Fase 3 — IA | Completada | Claude análisis, PDF, indicadores técnicos |
| Fase 4 — Dashboard | Completada | Streamlit con 5 tabs, +15 indicadores |
| Fase 5 — Feedback Loop | Completada | Evaluación automática de señales IA |
| Fase 6 — Alpaca | En desarrollo | Ejecución real de órdenes |
| Fase 7 — Servidor | Pendiente | Deploy VPS 24/7 |

---

**Última actualización**: Abril 2026
