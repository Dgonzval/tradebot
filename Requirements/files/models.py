from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class Position(Base):
    __tablename__ = "positions"

    symbol = Column(String, primary_key=True, index=True)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TradingSignal(Base):
    __tablename__ = "trading_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)  # BUY, SELL, HOLD
    price = Column(Float, nullable=True)
    source = Column(String, default="tradingview")
    extra = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AISignalOutcome(Base):
    """Registra señales IA y su resultado real para el feedback loop."""
    __tablename__ = "ai_signal_outcomes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)       # BUY / SELL / HOLD
    confidence = Column(Integer, nullable=True)   # 0-100
    price_at_signal = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    indicators_snapshot = Column(Text, nullable=True)  # JSON compacto
    created_at = Column(DateTime, default=datetime.utcnow)

    # Rellenados por el job de evaluación (7 días después)
    evaluated = Column(Boolean, default=False)
    price_at_eval = Column(Float, nullable=True)
    actual_pnl_pct = Column(Float, nullable=True)  # % ganado/perdido
    was_correct = Column(Boolean, nullable=True)    # si la dirección fue acertada
    eval_at = Column(DateTime, nullable=True)
