import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Tu chat ID para alertas automáticas
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/trading_bot")

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Trading
PORTFOLIO_SYMBOLS = os.getenv("PORTFOLIO_SYMBOLS", "BTC,ETH,AAPL").split(",")
BASE_CURRENCY = "USD"

# Scheduler
PRICE_CHECK_INTERVAL = 5  # minutos
NEWS_CHECK_INTERVAL = 15  # minutos
REPORT_GENERATION_TIME = "08:00"  # Hora diaria para reportes

# Risk Management
STOP_LOSS_PERCENT = 5.0
TAKE_PROFIT_PERCENT = 15.0
MAX_POSITION_SIZE = 10000  # USD máximo por posición

# Notificaciones
PRICE_ALERT_THRESHOLD = 3.0  # % de cambio para alertar
IMPORTANT_NEWS_KEYWORDS = ["earnings", "merger", "bankruptcy", "scandal", "record"]
