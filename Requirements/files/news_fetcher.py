import requests
import logging
from config import NEWS_API_KEY, PORTFOLIO_SYMBOLS

logger = logging.getLogger(__name__)

BASE_URL = "https://newsapi.org/v2"

SYMBOL_QUERIES = {
    "BTC": "Bitcoin OR BTC crypto",
    "ETH": "Ethereum OR ETH crypto",
    "AAPL": "Apple AAPL stock",
    "GOOGL": "Google Alphabet GOOGL stock",
    "MSFT": "Microsoft MSFT stock",
}


def fetch_news_for_symbol(symbol: str, page_size: int = 3) -> list[dict]:
    query = SYMBOL_QUERIES.get(symbol, symbol)
    try:
        resp = requests.get(
            f"{BASE_URL}/everything",
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": page_size,
                "apiKey": NEWS_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        return [
            {
                "symbol": symbol,
                "title": a["title"],
                "source": a["source"]["name"],
                "url": a["url"],
                "published_at": a["publishedAt"],
            }
            for a in articles
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]
    except Exception as e:
        logger.error(f"Error fetching news for {symbol}: {e}")
        return []


def fetch_all_news(symbols: list[str] = None) -> list[dict]:
    symbols = symbols or PORTFOLIO_SYMBOLS
    all_articles = []
    for symbol in symbols:
        all_articles.extend(fetch_news_for_symbol(symbol))
    all_articles.sort(key=lambda x: x["published_at"], reverse=True)
    return all_articles
