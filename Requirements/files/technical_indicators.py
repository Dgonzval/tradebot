import pandas as pd
import numpy as np
import yfinance as yf
import logging

logger = logging.getLogger(__name__)

CRYPTO = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE"}


# ============= CALCULOS TECNICOS =============

def _rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return round(float(100 - (100 / (1 + rs.iloc[-1]))), 2)


def _macd(close: pd.Series):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    line = ema12 - ema26
    signal = line.ewm(span=9, adjust=False).mean()
    hist = line - signal
    return round(float(line.iloc[-1]), 4), round(float(signal.iloc[-1]), 4), round(float(hist.iloc[-1]), 4)


def _bollinger(close: pd.Series, period: int = 20):
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + 2 * std
    lower = sma - 2 * std
    price = close.iloc[-1]
    width = float(upper.iloc[-1] - lower.iloc[-1])
    pct_b = float((price - lower.iloc[-1]) / width) if width else 0.5
    return round(float(upper.iloc[-1]), 2), round(float(sma.iloc[-1]), 2), round(float(lower.iloc[-1]), 2), round(pct_b, 2)


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    prev = close.shift(1)
    tr = pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return round(float(tr.rolling(period).mean().iloc[-1]), 2)


def _stochastic(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    lowest = low.rolling(period).min()
    highest = high.rolling(period).max()
    k = 100 * (close - lowest) / (highest - lowest).replace(0, np.nan)
    d = k.rolling(3).mean()
    return round(float(k.iloc[-1]), 2), round(float(d.iloc[-1]), 2)


def _williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    highest = high.rolling(period).max()
    lowest = low.rolling(period).min()
    wr = -100 * (highest - close) / (highest - lowest).replace(0, np.nan)
    return round(float(wr.iloc[-1]), 2)


def _cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> float:
    tp = (high + low + close) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())))
    cci = (tp - sma) / (0.015 * mad)
    return round(float(cci.iloc[-1]), 2)


def _obv(close: pd.Series, volume: pd.Series) -> dict:
    direction = np.sign(close.diff())
    obv = (direction * volume).cumsum()
    obv_sma = obv.rolling(20).mean()
    trend = "ALCISTA" if float(obv.iloc[-1]) > float(obv_sma.iloc[-1]) else "BAJISTA"
    return {"valor": round(float(obv.iloc[-1])), "tendencia": trend}


def _vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> float:
    tp = (high + low + close) / 3
    vwap = (tp * volume).cumsum() / volume.cumsum()
    return round(float(vwap.iloc[-1]), 2)


def _fibonacci_levels(high: float, low: float) -> dict:
    diff = high - low
    return {
        "0%": round(low, 2),
        "23.6%": round(low + 0.236 * diff, 2),
        "38.2%": round(low + 0.382 * diff, 2),
        "50%": round(low + 0.5 * diff, 2),
        "61.8%": round(low + 0.618 * diff, 2),
        "78.6%": round(low + 0.786 * diff, 2),
        "100%": round(high, 2),
    }


def _support_resistance(close: pd.Series, window: int = 10) -> dict:
    highs = close[(close.shift(1) < close) & (close.shift(-1) < close)]
    lows = close[(close.shift(1) > close) & (close.shift(-1) > close)]
    price = float(close.iloc[-1])
    resistances = sorted([float(x) for x in highs if float(x) > price], reverse=False)[:3]
    supports = sorted([float(x) for x in lows if float(x) < price], reverse=True)[:3]
    return {
        "soportes": [round(x, 2) for x in supports],
        "resistencias": [round(x, 2) for x in resistances],
    }


def _momentum(close: pd.Series) -> dict:
    price = float(close.iloc[-1])
    return {
        "1d": round((price - float(close.iloc[-2])) / float(close.iloc[-2]) * 100, 2),
        "7d": round((price - float(close.iloc[-7])) / float(close.iloc[-7]) * 100, 2),
        "14d": round((price - float(close.iloc[-14])) / float(close.iloc[-14]) * 100, 2),
        "30d": round((price - float(close.iloc[-30])) / float(close.iloc[-30]) * 100, 2),
    }


# ============= DATOS FUNDAMENTALES (solo acciones, no crypto) =============

def _get_fundamentals(ticker_obj) -> dict:
    try:
        info = ticker_obj.info
        result = {}
        fields = {
            "beta": "beta",
            "pe_ratio": "trailingPE",
            "pe_forward": "forwardPE",
            "pb_ratio": "priceToBook",
            "market_cap_B": None,
            "dividend_yield_pct": None,
            "short_ratio": "shortRatio",
            "profit_margin_pct": None,
            "revenue_growth_pct": None,
            "debt_equity": "debtToEquity",
            "roe_pct": None,
            "sector": "sector",
            "recomendacion_analistas": "recommendationKey",
            "precio_objetivo_analistas": "targetMeanPrice",
        }
        for key, yf_key in fields.items():
            if yf_key and info.get(yf_key) is not None:
                result[key] = info[yf_key]

        if info.get("marketCap"):
            result["market_cap_B"] = round(info["marketCap"] / 1e9, 2)
        if info.get("dividendYield"):
            result["dividend_yield_pct"] = round(info["dividendYield"] * 100, 2)
        if info.get("profitMargins"):
            result["profit_margin_pct"] = round(info["profitMargins"] * 100, 2)
        if info.get("revenueGrowth"):
            result["revenue_growth_pct"] = round(info["revenueGrowth"] * 100, 2)
        if info.get("returnOnEquity"):
            result["roe_pct"] = round(info["returnOnEquity"] * 100, 2)

        return result
    except Exception:
        return {}


def _get_options_sentiment(ticker_obj) -> dict:
    try:
        expirations = ticker_obj.options
        if not expirations:
            return {}
        chain = ticker_obj.option_chain(expirations[0])
        put_vol = float(chain.puts["volume"].sum())
        call_vol = float(chain.calls["volume"].sum())
        pc_ratio = round(put_vol / call_vol, 2) if call_vol else None
        avg_iv = round(float(chain.calls["impliedVolatility"].mean()) * 100, 2)
        return {
            "put_call_ratio": pc_ratio,
            "iv_promedio_pct": avg_iv,
            "sesgo": "BEARISH" if pc_ratio and pc_ratio > 1 else "BULLISH",
        }
    except Exception:
        return {}


# ============= FUNCION PRINCIPAL =============

def get_indicators(symbol: str, period: str = "90d") -> dict:
    is_crypto = symbol in CRYPTO
    ticker_str = f"{symbol}-USD" if is_crypto else symbol
    try:
        tk = yf.Ticker(ticker_str)
        df = tk.history(period=period)
        if df.empty or len(df) < 30:
            return {}

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]
        price = round(float(close.iloc[-1]), 2)

        # Medias moviles
        sma20 = round(float(close.rolling(20).mean().iloc[-1]), 2)
        sma50 = round(float(close.rolling(50).mean().iloc[-1]), 2) if len(df) >= 50 else None
        ema9 = round(float(close.ewm(span=9).mean().iloc[-1]), 2)
        ema21 = round(float(close.ewm(span=21).mean().iloc[-1]), 2)

        # Tendencia
        if sma50:
            trend = "ALCISTA" if price > sma20 > sma50 else ("BAJISTA" if price < sma20 < sma50 else "LATERAL")
        else:
            trend = "ALCISTA" if price > sma20 else "BAJISTA"

        macd_line, macd_sig, macd_hist = _macd(close)
        bb_upper, bb_mid, bb_lower, pct_b = _bollinger(close)
        stoch_k, stoch_d = _stochastic(high, low, close)
        rsi_val = _rsi(close)
        wr = _williams_r(high, low, close)
        cci_val = _cci(high, low, close)
        obv_data = _obv(close, volume)
        vwap_val = _vwap(high, low, close, volume)
        atr_val = _atr(high, low, close)
        momentum = _momentum(close)
        fib = _fibonacci_levels(float(high.max()), float(low.min()))
        sr = _support_resistance(close)

        vol_avg = float(volume.rolling(20).mean().iloc[-1])
        vol_ratio = round(float(volume.iloc[-1]) / vol_avg, 2) if vol_avg else 1.0

        high_period = round(float(high.max()), 2)
        low_period = round(float(low.min()), 2)
        pct_from_high = round((price - high_period) / high_period * 100, 2)

        result = {
            "precio_actual": price,
            "tendencia_general": trend,
            "momentum_pct": momentum,
            "medias_moviles": {
                "SMA20": sma20, "SMA50": sma50, "EMA9": ema9, "EMA21": ema21,
                "precio_sobre_SMA20": price > sma20,
                "precio_sobre_SMA50": price > sma50 if sma50 else None,
                "EMA9_sobre_EMA21": ema9 > ema21,
                "VWAP": vwap_val,
                "precio_sobre_VWAP": price > vwap_val,
            },
            "osciladores": {
                "RSI_14": {"valor": rsi_val, "zona": "SOBRECOMPRA" if rsi_val > 70 else ("SOBREVENTA" if rsi_val < 30 else "NEUTRAL")},
                "Williams_R": {"valor": wr, "zona": "SOBRECOMPRA" if wr > -20 else ("SOBREVENTA" if wr < -80 else "NEUTRAL")},
                "CCI_20": {"valor": cci_val, "zona": "SOBRECOMPRA" if cci_val > 100 else ("SOBREVENTA" if cci_val < -100 else "NEUTRAL")},
                "Estocastico": {"K": stoch_k, "D": stoch_d, "cruce": "ALCISTA" if stoch_k > stoch_d else "BAJISTA"},
            },
            "MACD": {
                "linea": macd_line, "senal": macd_sig, "histograma": macd_hist,
                "direccion": "ALCISTA" if macd_line > macd_sig else "BAJISTA",
                "acelerando": macd_hist > 0,
            },
            "bollinger_bands": {
                "superior": bb_upper, "media": bb_mid, "inferior": bb_lower,
                "pct_b": pct_b,
                "zona": "CERCA BANDA SUPERIOR" if pct_b > 0.8 else ("CERCA BANDA INFERIOR" if pct_b < 0.2 else "DENTRO BANDAS"),
                "ancho_pct": round((bb_upper - bb_lower) / bb_mid * 100, 2),
            },
            "volumen": {
                "OBV_tendencia": obv_data["tendencia"],
                "ratio_vs_media20": vol_ratio,
                "nivel": "ALTO" if vol_ratio > 1.5 else ("BAJO" if vol_ratio < 0.5 else "NORMAL"),
            },
            "volatilidad": {
                "ATR_14": atr_val,
                "ATR_pct_precio": round(atr_val / price * 100, 2),
            },
            "niveles_clave": {
                "fibonacci_90d": fib,
                "soporte_resistencia": sr,
                "maximo_periodo": high_period,
                "minimo_periodo": low_period,
                "pct_desde_maximo": pct_from_high,
            },
        }

        if not is_crypto:
            fundamentals = _get_fundamentals(tk)
            if fundamentals:
                result["fundamentales"] = fundamentals
            options = _get_options_sentiment(tk)
            if options:
                result["opciones_sentimiento"] = options

        return result

    except Exception as e:
        logger.error(f"Error calculando indicadores para {symbol}: {e}")
        return {}
