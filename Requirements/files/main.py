import json
import logging
import os
from datetime import datetime, timedelta

import requests as http_requests
from yf_session import get_price, get_history
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

import cache
from ai_analyzer import AIAnalyzer
from config import (
    NEWS_CHECK_INTERVAL,
    PORTFOLIO_SYMBOLS,
    PRICE_CHECK_INTERVAL,
    STOP_LOSS_PERCENT,
    TAKE_PROFIT_PERCENT,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)
from database import SessionLocal, get_db, init_db
from models import AISignalOutcome, Position, TradingSignal
from news_fetcher import fetch_all_news
from pdf_generator import PDFReportGenerator
from technical_indicators import get_indicators

logging.basicConfig(level=logging.INFO, encoding="utf-8")
logger = logging.getLogger(__name__)

app = FastAPI(title="Trading Bot API")
scheduler = BackgroundScheduler()
ai = AIAnalyzer()

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


# ============= PYDANTIC SCHEMAS =============
class TradingViewWebhook(BaseModel):
    ticker: str
    action: str
    close: float | None = None
    exchange: str | None = None
    interval: str | None = None


# ============= HELPERS =============
def send_telegram_alert(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        http_requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        logger.error(f"Error sending Telegram alert: {e}")


def seed_initial_positions():
    db = SessionLocal()
    try:
        existing = {p.symbol for p in db.query(Position).all()}
        new_positions = [
            Position(symbol=symbol, quantity=0, entry_price=0.0)
            for symbol in PORTFOLIO_SYMBOLS
            if symbol not in existing
        ]
        if new_positions:
            db.add_all(new_positions)
            db.commit()
            logger.info(f"Posiciones creadas: {[p.symbol for p in new_positions]}")
    finally:
        db.close()


# ============= TAREAS SCHEDULADAS =============
def fetch_prices():
    logger.info("Actualizando precios...")
    db = SessionLocal()
    try:
        for symbol in PORTFOLIO_SYMBOLS:
            cached = cache.get_price(symbol)
            if cached:
                logger.info(f"{symbol}: ${cached:.2f} (cache)")
                continue

            try:
                price = get_price(symbol)
                if price is None:
                    raise ValueError(f"Sin datos para {symbol}")
                cache.set_price(symbol, price)

                pos = db.query(Position).filter(Position.symbol == symbol).first()
                if pos:
                    pos.current_price = price
                    pos.updated_at = datetime.utcnow()
                    db.commit()

                    pnl = (price - pos.entry_price) / pos.entry_price * 100
                    logger.info(f"{symbol}: ${price:.2f} | P&L: {pnl:+.2f}%")

                    if pnl <= -STOP_LOSS_PERCENT:
                        send_telegram_alert(
                            f"*ALERTA STOP-LOSS* {symbol}\n"
                            f"P&L: *{pnl:+.2f}%* (limite: -{STOP_LOSS_PERCENT}%)\n"
                            f"Precio actual: ${price:,.2f}"
                        )
                    elif pnl >= TAKE_PROFIT_PERCENT:
                        send_telegram_alert(
                            f"*ALERTA TAKE-PROFIT* {symbol}\n"
                            f"P&L: *{pnl:+.2f}%* (objetivo: +{TAKE_PROFIT_PERCENT}%)\n"
                            f"Precio actual: ${price:,.2f}"
                        )
            except Exception as e:
                logger.error(f"Error fetching {symbol}: {e}")
    finally:
        db.close()


def fetch_news():
    logger.info("Buscando noticias...")
    try:
        articles = fetch_all_news()
        if articles:
            cache.set_news(articles)
            logger.info(f"{len(articles)} noticias cacheadas en Redis")
    except Exception as e:
        logger.error(f"Error fetching news: {e}")


def generate_report_file() -> str:
    """Genera PDF con análisis IA. Devuelve la ruta del archivo."""
    db = SessionLocal()
    try:
        positions_rows = db.query(Position).all()
        positions = {
            p.symbol: {
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "pnl_percent": round((p.current_price - p.entry_price) / p.entry_price * 100, 2)
                if p.current_price else 0,
            }
            for p in positions_rows
        }

        articles = cache.get_news() or fetch_all_news()

        logger.info("Generando análisis IA...")
        news_analysis = ai.analyze_news(articles, positions)
        risk_analysis = ai.assess_portfolio_risk(positions)

        signals = []
        for p in positions_rows:
            if p.current_price:
                indicators = get_indicators(p.symbol)
                if p.entry_price and p.entry_price > 0:
                    indicators["pnl_cartera_pct"] = round(
                        (p.current_price - p.entry_price) / p.entry_price * 100, 2
                    )
                signal = ai.generate_trading_signal(p.symbol, indicators, db=db)
                signals.append(signal)

        # Estadísticas de precisión del feedback loop
        evaluated = db.query(AISignalOutcome).filter(AISignalOutcome.evaluated == True).all()
        ai_stats = None
        if evaluated:
            correct = sum(1 for r in evaluated if r.was_correct)
            by_sym = {}
            for r in evaluated:
                s = by_sym.setdefault(r.symbol, {"total": 0, "correct": 0, "pnls": []})
                s["total"] += 1
                if r.was_correct:
                    s["correct"] += 1
                if r.actual_pnl_pct is not None:
                    s["pnls"].append(r.actual_pnl_pct)
            ai_stats = {
                "total": len(evaluated),
                "correct": correct,
                "accuracy_pct": round(correct / len(evaluated) * 100, 1),
                "by_symbol": {
                    sym: {
                        "accuracy_pct": round(d["correct"] / d["total"] * 100, 1),
                        "avg_pnl_pct": round(sum(d["pnls"]) / len(d["pnls"]), 2) if d["pnls"] else 0,
                    }
                    for sym, d in by_sym.items()
                },
            }

        filename = os.path.join(REPORTS_DIR, f"trading_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        report = PDFReportGenerator(filename=filename)
        report.add_title("Reporte de Trading Diario")
        report.add_portfolio_summary(positions)
        report.add_news_analysis(articles[:5], news_analysis)
        report.add_trading_signals(signals)
        if ai_stats:
            report.add_ai_accuracy(ai_stats)
        report.add_risk_assessment({"analysis": risk_analysis})
        report.add_recommendations([
            s["reasoning"][:120] + "..." for s in signals if s["action"] != "HOLD"
        ] or ["Sin senales activas hoy."])
        report.add_disclaimer()
        report.generate()

        logger.info(f"PDF generado: {filename}")
        return filename
    finally:
        db.close()


def evaluate_signal_outcomes():
    """Evalúa señales IA de hace 7 días comparando precio entonces vs ahora."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=7)
        pending = (
            db.query(AISignalOutcome)
            .filter(AISignalOutcome.evaluated == False, AISignalOutcome.created_at <= cutoff)
            .all()
        )
        if not pending:
            return

        logger.info(f"Evaluando {len(pending)} señales pendientes...")
        for rec in pending:
            try:
                price_now = get_price(rec.symbol)
                if price_now is None:
                    raise ValueError(f"No price for {rec.symbol}")
                if rec.price_at_signal and rec.price_at_signal > 0:
                    pnl = (price_now - rec.price_at_signal) / rec.price_at_signal * 100
                else:
                    pnl = 0.0

                correct = (rec.action == "BUY" and pnl > 0) or (rec.action == "SELL" and pnl < 0)
                rec.price_at_eval = price_now
                rec.actual_pnl_pct = round(pnl, 2)
                rec.was_correct = correct
                rec.evaluated = True
                rec.eval_at = datetime.utcnow()
            except Exception as e:
                logger.warning(f"Error evaluando señal {rec.id} ({rec.symbol}): {e}")

        db.commit()
        correct_count = sum(1 for r in pending if r.was_correct)
        logger.info(f"Evaluación completada: {correct_count}/{len(pending)} señales correctas")
    finally:
        db.close()


def generate_daily_report():
    logger.info("Generando reporte diario...")
    try:
        path = generate_report_file()
        send_telegram_alert(f"*Reporte diario generado*\nRevisa con /reporte en el bot.")
        logger.info(f"Reporte enviado: {path}")
    except Exception as e:
        logger.error(f"Error generando reporte: {e}")


# ============= RUTAS API =============
@app.get("/health")
async def health_check():
    return {
        "status": "running",
        "redis": "connected" if cache.is_healthy() else "disconnected",
    }


@app.get("/positions")
async def get_positions(db: Session = Depends(get_db)):
    positions = db.query(Position).all()
    return {
        pos.symbol: {
            "quantity": pos.quantity,
            "entry_price": pos.entry_price,
            "current_price": pos.current_price,
            "pnl_percent": round((pos.current_price - pos.entry_price) / pos.entry_price * 100, 2)
            if pos.current_price else 0,
            "last_updated": pos.updated_at.isoformat() if pos.updated_at else None,
        }
        for pos in positions
    }


@app.post("/positions")
async def create_position(
    symbol: str, quantity: float, entry_price: float, db: Session = Depends(get_db)
):
    symbol = symbol.upper()
    if db.query(Position).filter(Position.symbol == symbol).first():
        raise HTTPException(status_code=400, detail=f"Ya existe posicion para {symbol}")
    pos = Position(symbol=symbol, quantity=quantity, entry_price=entry_price)
    db.add(pos)
    db.commit()
    db.refresh(pos)
    return {"message": f"Posicion {symbol} creada", "symbol": pos.symbol}


@app.put("/positions/{symbol}")
async def update_position(
    symbol: str,
    quantity: float = None,
    entry_price: float = None,
    db: Session = Depends(get_db),
):
    pos = db.query(Position).filter(Position.symbol == symbol.upper()).first()
    if not pos:
        raise HTTPException(status_code=404, detail=f"No se encontro posicion para {symbol}")
    if quantity is not None:
        pos.quantity = quantity
    if entry_price is not None:
        pos.entry_price = entry_price
    pos.updated_at = datetime.utcnow()
    db.commit()
    return {"message": f"Posicion {symbol.upper()} actualizada"}


@app.delete("/positions/{symbol}")
async def delete_position(symbol: str, db: Session = Depends(get_db)):
    pos = db.query(Position).filter(Position.symbol == symbol.upper()).first()
    if not pos:
        raise HTTPException(status_code=404, detail=f"No se encontro posicion para {symbol}")
    db.delete(pos)
    db.commit()
    return {"message": f"Posicion {symbol.upper()} eliminada"}


@app.get("/portfolio-value")
async def portfolio_value(db: Session = Depends(get_db)):
    positions = db.query(Position).all()
    total = sum(pos.quantity * pos.current_price for pos in positions if pos.current_price)
    return {"total_usd": round(total, 2)}


@app.get("/news")
async def get_news():
    articles = cache.get_news()
    if not articles:
        articles = fetch_all_news()
        if articles:
            cache.set_news(articles)
    return {"count": len(articles), "articles": articles}


@app.post("/tradingview-webhook")
async def tradingview_webhook(payload: TradingViewWebhook, db: Session = Depends(get_db)):
    symbol = payload.ticker.replace("USD", "").replace("USDT", "").upper()
    action = payload.action.upper()
    if action not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="action debe ser BUY o SELL")

    signal = TradingSignal(
        symbol=symbol,
        action=action,
        price=payload.close,
        source="tradingview",
        extra=json.dumps({"exchange": payload.exchange, "interval": payload.interval}),
    )
    db.add(signal)
    db.commit()

    send_telegram_alert(
        f"*Senal TradingView* {'compra' if action == 'BUY' else 'venta'} *{symbol}*\n"
        f"Precio: ${payload.close:,.2f}" if payload.close else f"*Senal TradingView* {action} {symbol}"
    )
    logger.info(f"TradingView signal: {action} {symbol} @ {payload.close}")
    return {"message": f"Senal {action} {symbol} registrada", "id": signal.id}


@app.get("/signals")
async def get_signals(limit: int = 20, db: Session = Depends(get_db)):
    signals = (
        db.query(TradingSignal)
        .order_by(TradingSignal.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "action": s.action,
            "price": s.price,
            "source": s.source,
            "created_at": s.created_at.isoformat(),
        }
        for s in signals
    ]


@app.get("/indicators/{symbol}")
async def get_indicators_endpoint(symbol: str):
    """Indicadores técnicos calculados en el contenedor API (caché compartida)."""
    try:
        ind = get_indicators(symbol.upper())
        if not ind:
            raise HTTPException(status_code=503, detail=f"Sin datos para {symbol}")
        return ind
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/report/generate")
async def generate_report():
    try:
        path = generate_report_file()
        return {"path": path, "filename": os.path.basename(path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/ai-stats")
async def ai_signal_stats(db: Session = Depends(get_db)):
    """Estadísticas de acierto de las señales IA evaluadas."""
    evaluated = db.query(AISignalOutcome).filter(AISignalOutcome.evaluated == True).all()
    pending = db.query(AISignalOutcome).filter(AISignalOutcome.evaluated == False).count()

    if not evaluated:
        return {"evaluated": 0, "pending": pending, "accuracy_pct": None, "by_symbol": {}}

    correct = [r for r in evaluated if r.was_correct]
    accuracy = round(len(correct) / len(evaluated) * 100, 1)

    by_symbol = {}
    for r in evaluated:
        s = by_symbol.setdefault(r.symbol, {"total": 0, "correct": 0, "avg_pnl": []})
        s["total"] += 1
        if r.was_correct:
            s["correct"] += 1
        if r.actual_pnl_pct is not None:
            s["avg_pnl"].append(r.actual_pnl_pct)

    for s in by_symbol.values():
        s["accuracy_pct"] = round(s["correct"] / s["total"] * 100, 1)
        s["avg_pnl_pct"] = round(sum(s["avg_pnl"]) / len(s["avg_pnl"]), 2) if s["avg_pnl"] else None
        del s["avg_pnl"]

    return {
        "evaluated": len(evaluated),
        "pending": pending,
        "accuracy_pct": accuracy,
        "by_symbol": by_symbol,
    }


@app.get("/report/download/{filename}")
async def download_report(filename: str):
    path = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return FileResponse(path, media_type="application/pdf", filename=filename)


# ============= STARTUP/SHUTDOWN =============
@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando Trading Bot...")
    init_db()
    seed_initial_positions()

    scheduler.add_job(fetch_prices, "interval", minutes=PRICE_CHECK_INTERVAL, id="fetch_prices")
    scheduler.add_job(fetch_news, "interval", minutes=NEWS_CHECK_INTERVAL, id="fetch_news")
    scheduler.add_job(generate_daily_report, "cron", hour=8, minute=0, id="daily_report")
    scheduler.add_job(evaluate_signal_outcomes, "cron", hour=9, minute=0, id="eval_signals")

    scheduler.start()
    logger.info(f"Scheduler iniciado con {len(scheduler.get_jobs())} trabajos")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Apagando Trading Bot...")
    scheduler.shutdown()


# ============= EJECUCION =============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
