"""
SQLAlchemy ORM models for QB Trading System
TimescaleDB 최적화된 시계열 데이터 모델
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4
from sqlalchemy import Column, String, Numeric, BigInteger, DateTime, Text, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class MarketData(Base):
    """시계열 주가 데이터 (TimescaleDB 하이퍼테이블)"""
    __tablename__ = 'market_data'
    
    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol = Column(String(10), primary_key=True, nullable=False)
    interval_type = Column(String(5), primary_key=True, nullable=False)  # '1m', '5m', '1d'
    open = Column(Numeric(12, 2))
    high = Column(Numeric(12, 2))
    low = Column(Numeric(12, 2))
    close = Column(Numeric(12, 2))
    volume = Column(BigInteger)
    
    __table_args__ = (
        Index('idx_market_data_symbol_time', 'symbol', 'time'),
        Index('idx_market_data_time_desc', 'time'),
    )
    
    def __repr__(self):
        return f"<MarketData(symbol={self.symbol}, time={self.time}, close={self.close})>"


class Trade(Base):
    """거래 기록"""
    __tablename__ = 'trades'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())
    symbol = Column(String(10), nullable=False)
    side = Column(String(4), nullable=False)  # 'BUY', 'SELL'
    quantity = Column(BigInteger, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    commission = Column(Numeric(10, 2), default=0)
    strategy_name = Column(String(100))
    order_type = Column(String(20))  # 'MARKET', 'LIMIT', 'STOP'
    status = Column(String(20), default='FILLED')  # 'FILLED', 'PARTIAL', 'CANCELLED'
    profit_loss = Column(Numeric(12, 2))
    
    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name='check_trade_side'),
        CheckConstraint("quantity > 0", name='check_trade_quantity'),
        CheckConstraint("price > 0", name='check_trade_price'),
        Index('idx_trades_symbol_timestamp', 'symbol', 'timestamp'),
        Index('idx_trades_strategy', 'strategy_name'),
        Index('idx_trades_timestamp_desc', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<Trade(symbol={self.symbol}, side={self.side}, quantity={self.quantity}, price={self.price})>"


class Position(Base):
    """포지션 정보"""
    __tablename__ = 'positions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol = Column(String(10), nullable=False, unique=True)
    quantity = Column(BigInteger, nullable=False, default=0)
    average_price = Column(Numeric(12, 2))
    current_price = Column(Numeric(12, 2))
    unrealized_pnl = Column(Numeric(12, 2), default=0)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_positions_symbol', 'symbol'),
        Index('idx_positions_updated', 'updated_at'),
    )
    
    def __repr__(self):
        return f"<Position(symbol={self.symbol}, quantity={self.quantity}, avg_price={self.average_price})>"


class StrategyPerformance(Base):
    """전략 성과"""
    __tablename__ = 'strategy_performance'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    strategy_name = Column(String(100), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    total_return = Column(Numeric(8, 4))  # 총 수익률
    trades_count = Column(BigInteger, default=0)
    win_rate = Column(Numeric(5, 2))  # 승률 (%)
    max_drawdown = Column(Numeric(8, 4))  # 최대 손실률
    sharpe_ratio = Column(Numeric(6, 3))  # 샤프 비율
    profit_factor = Column(Numeric(6, 3))  # 수익 팩터
    avg_trade_pnl = Column(Numeric(12, 2))  # 평균 거래 손익
    
    __table_args__ = (
        Index('idx_strategy_performance_name_date', 'strategy_name', 'date'),
        Index('idx_strategy_performance_date', 'date'),
    )
    
    def __repr__(self):
        return f"<StrategyPerformance(strategy={self.strategy_name}, date={self.date}, return={self.total_return})>"


class StockMetadata(Base):
    """종목 메타데이터"""
    __tablename__ = 'stocks_metadata'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol = Column(String(10), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    market = Column(String(20))  # 'KOSPI', 'KOSDAQ', 'KONEX'
    sector = Column(String(50))
    industry = Column(String(100))
    market_cap = Column(BigInteger)  # 시가총액
    listed_shares = Column(BigInteger)  # 상장주식수
    is_active = Column(String(1), default='Y')  # 'Y', 'N'
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        CheckConstraint("is_active IN ('Y', 'N')", name='check_stock_active'),
        Index('idx_stocks_symbol', 'symbol'),
        Index('idx_stocks_market', 'market'),
        Index('idx_stocks_sector', 'sector'),
    )
    
    def __repr__(self):
        return f"<StockMetadata(symbol={self.symbol}, name={self.name}, market={self.market})>"


class RiskMetric(Base):
    """리스크 지표"""
    __tablename__ = 'risk_metrics'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())
    portfolio_value = Column(Numeric(15, 2), nullable=False)
    total_exposure = Column(Numeric(15, 2))  # 총 익스포저
    cash_balance = Column(Numeric(15, 2))  # 현금 잔고
    daily_pnl = Column(Numeric(12, 2))  # 일일 손익
    var_95 = Column(Numeric(12, 2))  # 95% VaR
    max_drawdown = Column(Numeric(8, 4))  # 최대 손실률
    leverage_ratio = Column(Numeric(6, 3))  # 레버리지 비율
    
    __table_args__ = (
        Index('idx_risk_metrics_timestamp', 'timestamp'),
        Index('idx_risk_metrics_timestamp_desc', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<RiskMetric(timestamp={self.timestamp}, portfolio_value={self.portfolio_value})>"


class SystemLog(Base):
    """시스템 로그"""
    __tablename__ = 'system_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())
    level = Column(String(10), nullable=False)  # 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    component = Column(String(50))  # 'DataCollector', 'StrategyEngine', etc.
    message = Column(Text, nullable=False)
    details = Column(Text)  # JSON 형태의 추가 정보
    
    __table_args__ = (
        CheckConstraint("level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')", name='check_log_level'),
        Index('idx_system_logs_timestamp', 'timestamp'),
        Index('idx_system_logs_level', 'level'),
        Index('idx_system_logs_component', 'component'),
    )
    
    def __repr__(self):
        return f"<SystemLog(level={self.level}, component={self.component}, message={self.message[:50]})>"