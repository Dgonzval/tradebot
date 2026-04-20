"""
Precio de activos sin yfinance (bloqueado en VPS por Yahoo Finance):
- Crypto precio:   CoinGecko (gratis, sin API key)
- Crypto historial: CoinGecko OHLC endpoint
- Stocks precio:   Alpha Vantage (gratis, 25 req/dia, requiere API key)
                   -> fallback: Stooq (gratis, sin API key)
- Stocks historial: Stooq CSV (gratis, sin API key)
"""
import io
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


def get_price(symbol: str) -> float | None:
    """Precio actual. Crypto via CoinGecko, stocks via AlphaVantage -> Stooq."""
    if symbol in CRYPTO_SYMBOLS:
        return _coingecko_price(symbol)
    return _stock_price(symbol)


def get_history(symbol: str, days: int = 90):
    """DataFrame OHLCV. Crypto via CoinGecko, stocks via Stooq.
    Accepts both 'BTC' and 'BTC-USD' for crypto."""
    base = symbol.upper().replace("-USD", "").replace("-USDT", "")
    if base in CRYPTO_SYMBOLS:
        return _coingecko_history(base, days)
    return _stooq_history(symbol, days)


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


def _coingecko_history(symbol: str, days: int) -> pd.DataFrame | None:
    coin_id = CRYPTO_IDS.get(symbol)
    if not coin_id:
        return None
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc",
            params={"vs_currency": "usd", "days": min(days, 90)},
            timeout=15,
        )
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


# ── Stocks ────────────────────────────────────────────────────────────────────

def _stock_price(symbol: str) -> float | None:
    """Alpha Vantage con clave, Stooq sin clave como fallback."""
    try:
        from config import ALPHA_VANTAGE_API_KEY
    except Exception:
        ALPHA_VANTAGE_API_KEY = ""

    if ALPHA_VANTAGE_API_KEY:
        price = _alphavantage_price(symbol, ALPHA_VANTAGE_API_KEY)
        if price is not None:
            return price

    return _stooq_price(symbol)


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
        # API key limit reached returns empty Global Quote
        logger.warning(f"AlphaVantage empty response for {symbol} (limit?)")
        return None
    except Exception as e:
        logger.error(f"AlphaVantage error for {symbol}: {e}")
        return None


def _stooq_price(symbol: str) -> float | None:
    """Precio EOD de Stooq (gratis, sin API key, no bloqueado en VPS)."""
    try:
        df = _stooq_history(symbol, days=5)
        if df is not None and not df.empty:
            return round(float(df["Close"].iloc[-1]), 2)
    except Exception as e:
        logger.error(f"Stooq price error for {symbol}: {e}")
    return None


def _stooq_history(symbol: str, days: int = 90) -> pd.DataFrame | None:
    """Historial OHLCV desde Stooq CSV. Devuelve los últimos `days` dias."""
    try:
        stooq_sym = f"{symbol.lower()}.us"
        r = requests.get(
            "https://stooq.com/q/d/l/",
            params={"s": stooq_sym, "i": "d"},
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        r.raise_for_status()
        if not r.text.strip() or "No data" in r.text:
            logger.warning(f"Stooq: no data for {symbol}")
            return None
        df = pd.read_csv(io.StringIO(r.text), parse_dates=["Date"])
        df = df.sort_values("Date").set_index("Date")
        df = df.rename(columns={"Open": "Open", "High": "High", "Low": "Low",
                                 "Close": "Close", "Volume": "Volume"})
        return df.tail(days)
    except Exception as e:
        logger.error(f"Stooq history error for {symbol}: {e}")
        return None
