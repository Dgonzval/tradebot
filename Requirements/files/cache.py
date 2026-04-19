import json
import redis
from config import REDIS_URL

_client = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def set_price(symbol: str, price: float, ttl: int = 300):
    get_client().setex(f"price:{symbol}", ttl, str(price))


def get_price(symbol: str) -> float | None:
    val = get_client().get(f"price:{symbol}")
    return float(val) if val else None


def set_news(articles: list, ttl: int = 900):
    get_client().setex("news:latest", ttl, json.dumps(articles))


def get_news() -> list:
    val = get_client().get("news:latest")
    return json.loads(val) if val else []


def is_healthy() -> bool:
    try:
        return get_client().ping()
    except Exception:
        return False
