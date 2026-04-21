"""
Precio de activos:
- Crypto:  CoinGecko (gratis, sin API key)
- Stocks precio:   Yahoo Finance API directa -> Alpha Vantage (con key)
- Stocks historial: Yahoo Finance API directa -> Alpha Vantage (con key)

Caché en memoria por contenedor (TTL configurable) para evitar rate limits.
"""
import io
import time
import requests
import logging
import pandas as pd

logger = logging.getLogger(__name__)

CRYPTO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
}

CRYPTO_SYMBOLS = set(CRYPTO_IDS.keys())

_YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finance.yahoo.com",
}

# ── Caché en memoria ──────────────────────────────────────────────────────────
_CACHE: dict[str, tuple[float, object]] = {}

def _cache_get(key: str, ttl: int):
    entry = _CACHE.get(key)
    if entry and time.time() - entry[0] < ttl:
        return entry[1]
    return None

def _cache_set(key: str, value):
    _CACHE[key] = (time.time(), value)


# ── Públicas ──────────────────────────────────────────────────────────────────

def get_price(symbol: str) -> float | None:
    """Precio actual. Crypto via CoinGecko, stocks via Yahoo Finance -> Alpha Vantage."""
    key = f"price:{symbol}"
    cached = _cache_get(key, ttl=120)
    if cached is not None:
        return cached
    price = _coingecko_price(symbol) if symbol in CRYPTO_SYMBOLS else _stock_price(symbol)
    if price is not None:
        _cache_set(key, price)
    return price


def get_history(symbol: str, days: int = 90) -> pd.DataFrame | None:
    """DataFrame OHLCV. Acepta 'BTC' o 'BTC-USD' para crypto."""
    base = symbol.upper().replace("-USD", "").replace("-USDT", "")
    key = f"hist:{base}:{days}"
    cached = _cache_get(key, ttl=300)
    if cached is not None:
        return cached
    if base in CRYPTO_SYMBOLS:
        df = _coingecko_history(base, days)
    else:
        df = _yahoo_history(symbol, days)
        if df is None or df.empty:
            api_key = _get_av_key()
            df = _alphavantage_history(symbol, days, api_key) if api_key else None
    if df is not None and not df.empty:
        _cache_set(key, df)
    return df


# ── Crypto ────────────────────────────────────────────────────────────────────

def _coingecko_price(symbol: str) -> float | None:
    coin_id = CRYPTO_IDS.get(symbol)
    if not coin_id:
        return None
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin_id, "vs_currencies": "usd"},
            timeout=10,
        )
        r.raise_for_status()
        return float(r.json()[coin_id]["usd"])
    except Exception as e:
        logger.error(f"CoinGecko price error for {symbol}: {e}")
        return None


_CG_VALID_DAYS = [1, 7, 14, 30, 90, 180, 365]

def _coingecko_valid_days(days: int) -> int:
    return min(_CG_VALID_DAYS, key=lambda v: abs(v - days))


def _coingecko_history(symbol: str, days: int) -> pd.DataFrame | None:
    coin_id = CRYPTO_IDS.get(symbol)
    if not coin_id:
        return None
    for attempt in range(3):
        try:
            r = requests.get(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc",
                params={"vs_currency": "usd", "days": _coingecko_valid_days(days)},
                timeout=15,
            )
            if r.status_code == 429:
                wait = 10 * (attempt + 1)
                logger.warning(f"CoinGecko 429 for {symbol}, esperando {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            df = pd.DataFrame(data, columns=["timestamp", "Open", "High", "Low", "Close"])
            df.index = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.drop("timestamp", axis=1)
            df["Volume"] = 0
            return df
        except Exception as e:
            logger.error(f"CoinGecko history error for {symbol}: {e}")
            return None
    return None


# ── Stocks: Yahoo Finance directo ─────────────────────────────────────────────

def _yahoo_price(symbol: str) -> float | None:
    """Precio via Yahoo Finance API v8 (sin librería yfinance)."""
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"interval": "1d", "range": "2d"},
            headers=_YF_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        closes = r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        price = next((p for p in reversed(closes) if p is not None), None)
        return round(float(price), 2) if price else None
    except Exception as e:
        logger.warning(f"Yahoo Finance price error for {symbol}: {e}")
        return None


def _yahoo_history(symbol: str, days: int) -> pd.DataFrame | None:
    """Historial OHLCV via Yahoo Finance API v8."""
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"interval": "1d", "range": f"{min(days, 365)}d"},
            headers=_YF_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        result = r.json()["chart"]["result"][0]
        timestamps = result["timestamp"]
        q = result["indicators"]["quote"][0]
        df = pd.DataFrame({
            "Open": q["open"],
            "High": q["high"],
            "Low": q["low"],
            "Close": q["close"],
            "Volume": q["volume"],
        }, index=pd.to_datetime(timestamps, unit="s"))
        df.index.name = "Date"
        df = df.dropna(subset=["Close"])
        return df.tail(days)
    except Exception as e:
        logger.warning(f"Yahoo Finance history error for {symbol}: {e}")
        return None


# ── Stocks: Alpha Vantage (fallback) ─────────────────────────────────────────

def _get_av_key() -> str:
    try:
        from config import ALPHA_VANTAGE_API_KEY
        return ALPHA_VANTAGE_API_KEY or ""
    except Exception:
        return ""


def _stock_price(symbol: str) -> float | None:
    price = _yahoo_price(symbol)
    if price is not None:
        return price
    api_key = _get_av_key()
    if api_key:
        return _alphavantage_price(symbol, api_key)
    return None


def _alphavantage_price(symbol: str, api_key: str) -> float | None:
    try:
        r = requests.get(
            "https://www.alphavantage.co/query",
            params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": api_key},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json().get("Global Quote", {})
        price = data.get("05. price")
        if price:
            return float(price)
        logger.warning(f"AlphaVantage empty response for {symbol}")
        return None
    except Exception as e:
        logger.error(f"AlphaVantage price error for {symbol}: {e}")
        return None


def _alphavantage_history(symbol: str, days: int, api_key: str) -> pd.DataFrame | None:
    """Historial OHLCV via Alpha Vantage TIME_SERIES_DAILY."""
    try:
        r = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "outputsize": "compact",
                "apikey": api_key,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("Time Series (Daily)", {})
        if not data:
            logger.warning(f"AlphaVantage history empty for {symbol}")
            return None
        rows = [
            {
                "Date": pd.to_datetime(d),
                "Open": float(v["1. open"]),
                "High": float(v["2. high"]),
                "Low": float(v["3. low"]),
                "Close": float(v["4. close"]),
                "Volume": float(v["5. volume"]),
            }
            for d, v in data.items()
        ]
        df = pd.DataFrame(rows).sort_values("Date").set_index("Date")
        return df.tail(days)
    except Exception as e:
        logger.error(f"AlphaVantage history error for {symbol}: {e}")
        return None
