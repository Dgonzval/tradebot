"""
Precio de activos sin yfinance:
- Crypto: CoinGecko (gratis, sin API key, sin bloqueo)
- Stocks: Alpha Vantage (gratis, 25 req/dia, requiere API key)
- Fallback: yfinance sin sesion custom
"""
import requests
import logging

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
    """Obtiene precio actual. Crypto via CoinGecko, stocks via Alpha Vantage."""
    if symbol in CRYPTO_SYMBOLS:
        return _coingecko_price(symbol)
    return _alphavantage_price(symbol)


def get_history(symbol: str, days: int = 90):
    """Devuelve DataFrame OHLCV. Intenta yfinance primero, luego alternativas."""
    try:
        import yfinance as yf
        ticker_str = f"{symbol}-USD" if symbol in CRYPTO_SYMBOLS else symbol
        df = yf.Ticker(ticker_str).history(period=f"{days}d")
        if not df.empty:
            return df
    except Exception:
        pass

    if symbol in CRYPTO_SYMBOLS:
        return _coingecko_history(symbol, days)

    return None


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
        logger.error(f"CoinGecko error for {symbol}: {e}")
        return None


def _alphavantage_price(symbol: str) -> float | None:
    from config import ALPHA_VANTAGE_API_KEY
    if not ALPHA_VANTAGE_API_KEY:
        return _yfinance_fallback(symbol)
    try:
        r = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": ALPHA_VANTAGE_API_KEY,
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json().get("Global Quote", {})
        price = data.get("05. price")
        return float(price) if price else None
    except Exception as e:
        logger.error(f"AlphaVantage error for {symbol}: {e}")
        return _yfinance_fallback(symbol)


def _yfinance_fallback(symbol: str) -> float | None:
    try:
        import yfinance as yf
        ticker_str = f"{symbol}-USD" if symbol in CRYPTO_SYMBOLS else symbol
        hist = yf.Ticker(ticker_str).history(period="2d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def _coingecko_history(symbol: str, days: int):
    """Histórico OHLCV de CoinGecko para crypto."""
    import pandas as pd
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
