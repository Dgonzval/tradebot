import yfinance as yf

try:
    from curl_cffi import requests as curl_requests
    _session = curl_requests.Session(impersonate="chrome")
    # Test the session works
    _session.get("https://httpbin.org/get", timeout=5)
except Exception:
    _session = None


def ticker(symbol: str) -> yf.Ticker:
    if _session:
        return yf.Ticker(symbol, session=_session)
    return yf.Ticker(symbol)
