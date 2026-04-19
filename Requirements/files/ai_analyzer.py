import json
import re
import logging

from anthropic import Anthropic
from config import CLAUDE_API_KEY

logger = logging.getLogger(__name__)
client = Anthropic(api_key=CLAUDE_API_KEY)

SYSTEM_PROMPT = """Eres un analista de trading experto con acceso a datos de mercado en tiempo real.
Tu rol es:
1. Analizar noticias financieras y su impacto en activos específicos
2. Generar recomendaciones de compra/venta basadas en datos
3. Identificar riesgos en la cartera
4. Explicar decisiones en lenguaje claro y conciso

IMPORTANTE: Responde siempre en español, en texto plano sin markdown.
No uses #, ##, **, *, -, backticks ni emojis. Usa solo letras, números y puntuación normal.
Separa las secciones con saltos de línea."""


class AIAnalyzer:

    def _call(self, prompt: str, max_tokens: int = 1024) -> str:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def analyze_news(self, news_items: list, portfolio: dict) -> str:
        news_text = "\n".join(
            f"- [{a.get('source', '?')}] {a['title']} (activo: {a.get('symbol', '?')})"
            for a in news_items[:10]
        )
        portfolio_text = "\n".join(
            f"- {sym}: {pos['quantity']} unidades @ ${pos['entry_price']} entrada"
            + (f", actual ${pos['current_price']:.2f} (P&L {pos.get('pnl_percent', 0):+.1f}%)" if pos.get('current_price') else "")
            for sym, pos in portfolio.items()
        )
        prompt = f"""NOTICIAS RECIENTES:
{news_text}

MI CARTERA:
{portfolio_text}

Analiza el impacto de estas noticias en la cartera. Indica:
1. Qué activos se ven afectados y cómo (positivo/negativo)
2. Nivel de riesgo actual (Bajo/Medio/Alto) con justificación
3. 2-3 acciones concretas recomendadas"""
        return self._call(prompt, max_tokens=800)

    def generate_trading_signal(self, symbol: str, indicators: dict, db=None) -> dict:
        prompt = f"""Activo: {symbol}
Indicadores tecnicos:
{json.dumps(indicators, indent=2, ensure_ascii=False)}

Basandote en estos indicadores tecnicos proporciona:
1. Señal: BUY / SELL / HOLD
2. Confianza: 0-100%
3. Precio objetivo: (numero concreto)
4. Stop loss: (numero concreto)
5. Razonamiento: (maximo 3 lineas, sin markdown)"""
        response = self._call(prompt, max_tokens=400)
        signal = self._parse_signal(response, symbol)

        if db is not None:
            self._persist_signal(signal, indicators, db)

        return signal

    def _persist_signal(self, signal: dict, indicators: dict, db):
        try:
            from models import AISignalOutcome
            snapshot = {
                "rsi": indicators.get("osciladores", {}).get("RSI_14", {}).get("valor"),
                "macd_dir": indicators.get("MACD", {}).get("direccion"),
                "tendencia": indicators.get("tendencia_general"),
                "bb_zona": indicators.get("bollinger_bands", {}).get("zona"),
                "volumen_nivel": indicators.get("volumen", {}).get("nivel"),
            }
            record = AISignalOutcome(
                symbol=signal["symbol"],
                action=signal["action"],
                confidence=signal.get("confidence"),
                price_at_signal=signal.get("target_price"),
                target_price=signal.get("target_price"),
                stop_loss=signal.get("stop_loss"),
                indicators_snapshot=json.dumps(snapshot),
            )
            db.add(record)
            db.commit()
        except Exception as e:
            logger.warning(f"No se pudo persistir señal IA para {signal['symbol']}: {e}")

    def assess_portfolio_risk(self, positions: dict) -> str:
        prompt = f"""CARTERA ACTUAL:
{json.dumps(positions, indent=2)}

Evalúa:
1. Riesgo sistemático (Bajo/Medio/Alto)
2. Concentración del portafolio y riesgo específico por activo
3. Recomendaciones de rebalanceo si son necesarias
Sé específico con porcentajes y números."""
        return self._call(prompt, max_tokens=600)

    def _parse_signal(self, response: str, symbol: str) -> dict:
        signal = {
            "symbol": symbol,
            "action": "HOLD",
            "confidence": 50,
            "target_price": None,
            "stop_loss": None,
            "reasoning": response,
        }

        upper = response.upper()
        if "BUY" in upper or "COMPRA" in upper:
            signal["action"] = "BUY"
        elif "SELL" in upper or "VENTA" in upper:
            signal["action"] = "SELL"

        pct_matches = re.findall(r'(\d+)%', response)
        if pct_matches:
            signal["confidence"] = int(pct_matches[0])

        price_matches = re.findall(r'\$?(\d[\d,]*(?:\.\d+)?)', response)
        floats = []
        for p in price_matches:
            try:
                val = float(p.replace(',', ''))
                if val > 100:
                    floats.append(val)
            except ValueError:
                continue
        if len(floats) >= 2:
            signal["target_price"] = floats[0]
            signal["stop_loss"] = floats[1]

        return signal
