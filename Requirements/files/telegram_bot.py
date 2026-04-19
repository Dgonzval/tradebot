import asyncio
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from config import TELEGRAM_BOT_TOKEN


def _get(url, **kwargs):
    return requests.get(url, **kwargs)

def _post(url, **kwargs):
    return requests.post(url, **kwargs)

logging.basicConfig(level=logging.INFO, encoding="utf-8")
logger = logging.getLogger(__name__)

import os
API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")


# ============= HANDLERS =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Mis posiciones", callback_data="positions"),
            InlineKeyboardButton("Valor cartera", callback_data="portfolio"),
        ],
        [
            InlineKeyboardButton("Noticias", callback_data="news"),
            InlineKeyboardButton("Reporte PDF", callback_data="report"),
        ],
        [
            InlineKeyboardButton("Senales TradingView", callback_data="signals"),
            InlineKeyboardButton("Precision IA", callback_data="precision"),
        ],
    ]
    await update.effective_message.reply_text(
        "*Trading Bot IA 24/7*\n\n"
        "Comandos disponibles:\n"
        "/posiciones — Ver inversiones actuales\n"
        "/precio BTC — Precio de cualquier activo\n"
        "/indicadores BTC — Indicadores tecnicos\n"
        "/noticias — Noticias del mercado\n"
        "/senales — Senales TradingView\n"
        "/precision — Precision historica IA\n"
        "/reporte — PDF con analisis IA\n\n"
        "O usa los botones:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def positions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r_pos = await asyncio.to_thread(_get, f"{API_BASE_URL}/positions", timeout=10)
        r_val = await asyncio.to_thread(_get, f"{API_BASE_URL}/portfolio-value", timeout=10)
        data = r_pos.json()
        total_usd = r_val.json().get("total_usd", 0)

        total_invested = sum(p["quantity"] * p["entry_price"] for p in data.values())
        total_pnl = total_usd - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0

        text = "*Mis Posiciones*\n\n"
        for symbol, pos in data.items():
            pnl = pos.get("pnl_percent") or 0
            arrow = "+" if pnl >= 0 else "-"
            cp = pos.get("current_price") or 0
            qty = pos.get("quantity") or 0
            ep = pos.get("entry_price") or 0
            val = qty * cp if cp else qty * ep
            cp_str = f"${cp:,.2f}" if cp else "Sin precio"
            text += (
                f"[{arrow}] *{symbol}*  {qty} uds\n"
                f"  Entrada: ${ep:,.2f}  |  Actual: {cp_str}\n"
                f"  Valor: ${val:,.2f}  |  P&L: {pnl:+.2f}%\n\n"
            )

        text += (
            f"*Total cartera:* ${total_usd:,.2f}\n"
            f"*Invertido:* ${total_invested:,.2f}\n"
            f"*P&L total:* ${total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)"
        )
        await update.effective_message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.effective_message.reply_text(f"Error: {str(e)}")


async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r_val = await asyncio.to_thread(_get, f"{API_BASE_URL}/portfolio-value", timeout=10)
        r_pos = await asyncio.to_thread(_get, f"{API_BASE_URL}/positions", timeout=10)
        total = r_val.json()["total_usd"]
        positions = r_pos.json()
        invested = sum(p["quantity"] * p["entry_price"] for p in positions.values())
        pnl = total - invested
        pnl_pct = (pnl / invested * 100) if invested else 0
        await update.effective_message.reply_text(
            f"*Valor de Cartera*\n\n"
            f"Valor actual: *${total:,.2f}*\n"
            f"Invertido: ${invested:,.2f}\n"
            f"P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.effective_message.reply_text(f"Error: {str(e)}")


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text(
            "Uso: `/precio BTC` o `/precio AAPL`", parse_mode="Markdown"
        )
        return

    symbol = context.args[0].upper()
    try:
        import yfinance as yf
        CRYPTO = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE"}

        def _fetch():
            ticker = f"{symbol}-USD" if symbol in CRYPTO else symbol
            data = yf.Ticker(ticker)
            price = data.info.get("currentPrice") or data.history(period="1d")["Close"].iloc[-1]
            prev = data.history(period="5d")["Close"]
            chg = ((float(prev.iloc[-1]) - float(prev.iloc[-2])) / float(prev.iloc[-2]) * 100) if len(prev) >= 2 else 0
            return float(price), chg

        price, chg = await asyncio.to_thread(_fetch)
        arrow = "+" if chg >= 0 else ""
        await update.effective_message.reply_text(
            f"*{symbol}*: ${price:,.2f}  ({arrow}{chg:.2f}% hoy)",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.effective_message.reply_text(f"No encontre {symbol}: {str(e)}")


async def indicators_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text(
            "Uso: `/indicadores BTC` o `/indicadores AAPL`", parse_mode="Markdown"
        )
        return

    symbol = context.args[0].upper()
    msg = await update.effective_message.reply_text(f"Calculando indicadores de {symbol}...")
    try:
        def _fetch():
            from technical_indicators import get_indicators
            return get_indicators(symbol)

        ind = await asyncio.to_thread(_fetch)
        if not ind:
            await msg.edit_text(f"No se pudieron obtener indicadores para {symbol}.")
            return

        osc = ind.get("osciladores", {})
        mm = ind.get("medias_moviles", {})
        macd = ind.get("MACD", {})
        bb = ind.get("bollinger_bands", {})
        vol = ind.get("volumen", {})
        atr = ind.get("volatilidad", {})
        mom = ind.get("momentum_pct", {})
        rsi = osc.get("RSI_14", {})
        wr = osc.get("Williams_R", {})
        cci = osc.get("CCI_20", {})
        stoch = osc.get("Estocastico", {})

        text = (
            f"*Indicadores {symbol}*\n"
            f"Precio: ${ind.get('precio_actual', 0):,.2f}  |  Tendencia: {ind.get('tendencia_general', 'N/A')}\n\n"
            f"*Osciladores*\n"
            f"RSI 14: {rsi.get('valor', 'N/A')} ({rsi.get('zona', '')})\n"
            f"Williams %R: {wr.get('valor', 'N/A')} ({wr.get('zona', '')})\n"
            f"CCI 20: {cci.get('valor', 'N/A')} ({cci.get('zona', '')})\n"
            f"Estoc. K/D: {stoch.get('K', 'N/A')} / {stoch.get('D', 'N/A')} — {stoch.get('cruce', '')}\n\n"
            f"*MACD*\n"
            f"Linea: {macd.get('linea', 'N/A')}  |  Senal: {macd.get('senal', 'N/A')}\n"
            f"Histograma: {macd.get('histograma', 'N/A')}  |  Dir: {macd.get('direccion', '')}\n\n"
            f"*Medias Moviles*\n"
            f"SMA20: ${mm.get('SMA20', 0):,.2f}  |  SMA50: ${mm.get('SMA50', 0) or 0:,.2f}\n"
            f"EMA9: ${mm.get('EMA9', 0):,.2f}  |  VWAP: ${mm.get('VWAP', 0):,.2f}\n\n"
            f"*Bollinger Bands*\n"
            f"Sup: ${bb.get('superior', 0):,.2f}  |  Inf: ${bb.get('inferior', 0):,.2f}\n"
            f"Zona: {bb.get('zona', 'N/A')}  |  Ancho: {bb.get('ancho_pct', 0):.1f}%\n\n"
            f"*Volumen y Volatilidad*\n"
            f"OBV: {vol.get('OBV_tendencia', 'N/A')}  |  Nivel: {vol.get('nivel', 'N/A')}\n"
            f"ATR14: ${atr.get('ATR_14', 0):,.2f} ({atr.get('ATR_pct_precio', 0):.2f}% precio)\n\n"
            f"*Momentum*\n"
            f"1d: {mom.get('1d', 0):+.2f}%  |  7d: {mom.get('7d', 0):+.2f}%  |  30d: {mom.get('30d', 0):+.2f}%"
        )

        # Fundamentales si existen
        fund = ind.get("fundamentales")
        if fund:
            text += (
                f"\n\n*Fundamentales*\n"
                f"P/E: {fund.get('pe_ratio', 'N/A')}  |  P/B: {fund.get('pb_ratio', 'N/A')}\n"
                f"Market Cap: ${fund.get('market_cap_B', 0):.1f}B\n"
                f"ROE: {fund.get('roe_pct', 'N/A')}%  |  Margen: {fund.get('profit_margin_pct', 'N/A')}%\n"
                f"Analistas: {str(fund.get('recomendacion_analistas', 'N/A')).upper()}"
                f"  |  Objetivo: ${fund.get('precio_objetivo_analistas', 0):,.2f}"
            )

        await msg.edit_text(text, parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"Error: {str(e)}")


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = await asyncio.to_thread(_get, f"{API_BASE_URL}/news", timeout=20)
        data = response.json()
        articles = data.get("articles", [])[:5]

        if not articles:
            await update.effective_message.reply_text("No hay noticias disponibles.")
            return

        text = f"*Ultimas noticias* ({data['count']} total):\n\n"
        for a in articles:
            title = a["title"][:80]
            text += f"*{a['symbol']}* — {title}\n"
            text += f"_{a['source']}_ · {a['published_at'][:10]}\n\n"

        await update.effective_message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.effective_message.reply_text(f"Error: {str(e)}")


async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = await asyncio.to_thread(_get, f"{API_BASE_URL}/signals?limit=5", timeout=10)
        signals = response.json()

        if not signals:
            await update.effective_message.reply_text("No hay senales de TradingView aun.")
            return

        text = "*Ultimas senales TradingView:*\n\n"
        for s in signals:
            tag = "BUY" if s["action"] == "BUY" else "SELL"
            price_str = f"${s['price']:,.2f}" if s["price"] else "N/A"
            text += f"[{tag}] *{s['symbol']}* @ {price_str}\n"
            text += f"_{s['created_at'][:16].replace('T', ' ')}_\n\n"

        await update.effective_message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.effective_message.reply_text(f"Error: {str(e)}")


async def precision_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = await asyncio.to_thread(_get, f"{API_BASE_URL}/signals/ai-stats", timeout=10)
        data = response.json()

        if not data.get("evaluated"):
            await update.effective_message.reply_text(
                "*Precision IA*\n\n"
                "Aun no hay senales evaluadas.\n"
                "Las senales se evaluan 7 dias despues de generarse.\n"
                f"Pendientes de evaluacion: {data.get('pending', 0)}",
                parse_mode="Markdown",
            )
            return

        acc = data["accuracy_pct"]
        verdict = "Excelente" if acc >= 60 else ("Aceptable" if acc >= 50 else "Mejorable")
        text = (
            f"*Precision Historica IA*\n\n"
            f"Senales evaluadas: {data['evaluated']}\n"
            f"Pendientes: {data.get('pending', 0)}\n"
            f"Precision global: *{acc}%* ({verdict})\n\n"
            "*Por activo:*\n"
        )
        for sym, s in data.get("by_symbol", {}).items():
            pnl_str = f"{s['avg_pnl_pct']:+.2f}%" if s.get("avg_pnl_pct") is not None else "N/A"
            text += f"  *{sym}*: {s['accuracy_pct']}% precision  |  P&L medio: {pnl_str}\n"

        await update.effective_message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.effective_message.reply_text(f"Error: {str(e)}")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.effective_message.reply_text(
        "Generando reporte con analisis IA... (puede tardar 20-40s)"
    )
    try:
        response = await asyncio.to_thread(_post, f"{API_BASE_URL}/report/generate", timeout=120)
        data = response.json()

        if response.status_code != 200:
            await msg.edit_text(f"Error: {data.get('detail', 'desconocido')}")
            return

        with open(data["path"], "rb") as pdf_file:
            await update.effective_message.reply_document(
                document=pdf_file,
                filename=data["filename"],
                caption="Reporte de trading diario con analisis IA",
            )
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"Error: {str(e)}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    handlers = {
        "positions": positions_command,
        "portfolio": portfolio_command,
        "news": news_command,
        "report": report_command,
        "signals": signals_command,
        "precision": precision_command,
    }
    handler = handlers.get(query.data)
    if handler:
        await handler(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "*Ayuda del Bot*\n\n"
        "/posiciones — Posiciones abiertas con P&L\n"
        "/precio SYMBOL — Precio actual y cambio diario\n"
        "/indicadores SYMBOL — RSI, MACD, Bollinger, etc.\n"
        "/noticias — Ultimas noticias del mercado\n"
        "/senales — Senales de TradingView\n"
        "/precision — Historial de aciertos IA\n"
        "/reporte — Genera PDF con analisis IA completo\n"
        "/help — Esta ayuda",
        parse_mode="Markdown",
    )


# ============= SETUP =============
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("posiciones", positions_command))
    application.add_handler(CommandHandler("cartera", portfolio_command))
    application.add_handler(CommandHandler("precio", price_command))
    application.add_handler(CommandHandler("indicadores", indicators_command))
    application.add_handler(CommandHandler("noticias", news_command))
    application.add_handler(CommandHandler("senales", signals_command))
    application.add_handler(CommandHandler("precision", precision_command))
    application.add_handler(CommandHandler("reporte", report_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot de Telegram iniciado. Esperando mensajes...")
    application.run_polling()


if __name__ == "__main__":
    main()
