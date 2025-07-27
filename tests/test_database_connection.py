"""
Database connection and ORM models test
PostgreSQL/TimescaleDB 연결 및 SQLAlchemy 모델 테스트
"""

import pytest
import sys
import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from qb.database.connection import DatabaseManager, db_manager
from qb.database.models import (
    MarketData, Trade, Position, StrategyPerformance, 
    StockMetadata, RiskMetric, SystemLog
)


class TestDatabaseConnection:
    """데이터베이스 연결 테스트"""
    
    @pytest.fixture(scope="class")
    def db_manager_instance(self):
        """테스트용 데이터베이스 매니저 인스턴스"""
        manager = DatabaseManager()
        assert manager.initialize(), "Failed to initialize database"
        yield manager
        manager.close()
    
    def test_database_initialization(self, db_manager_instance):
        """데이터베이스 초기화 테스트"""
        assert db_manager_instance.engine is not None
        assert db_manager_instance.session_factory is not None
    
    def test_database_ping(self, db_manager_instance):
        """데이터베이스 연결 상태 테스트"""
        assert db_manager_instance.ping() is True
    
    def test_connection_info(self, db_manager_instance):
        """데이터베이스 연결 정보 테스트"""
        info = db_manager_instance.get_connection_info()
        assert info["status"] == "connected"
        assert "version" in info
        assert info["database"] == "qb_trading_dev"
        assert info["user"] == "qb_user"
        assert info["timescaledb"]["available"] is True
    
    def test_table_info(self, db_manager_instance):
        """테이블 정보 조회 테스트"""
        info = db_manager_instance.get_table_info()
        assert "tables" in info
        assert "hypertables" in info
        assert info["total_tables"] >= 7  # 최소 7개 테이블
        
        # 하이퍼테이블 확인
        hypertable_names = [ht["hypertable_name"] for ht in info["hypertables"]]
        assert "market_data" in hypertable_names


class TestORMModels:
    """SQLAlchemy ORM 모델 테스트"""
    
    @pytest.fixture(scope="class")
    def db_session(self):
        """테스트용 데이터베이스 세션"""
        assert db_manager.initialize(), "Failed to initialize database"
        with db_manager.get_session() as session:
            yield session
    
    def test_market_data_crud(self, db_session):
        """MarketData 모델 CRUD 테스트"""
        # Create
        market_data = MarketData(
            time=datetime.now(timezone.utc),
            symbol="005930",
            interval_type="1m",
            open=Decimal("75000.00"),
            high=Decimal("75500.00"),
            low=Decimal("74800.00"),
            close=Decimal("75200.00"),
            volume=1000000
        )
        db_session.add(market_data)
        db_session.commit()
        
        # Read
        retrieved = db_session.query(MarketData).filter_by(symbol="005930").first()
        assert retrieved is not None
        assert retrieved.symbol == "005930"
        assert retrieved.close == Decimal("75200.00")
        
        # Update
        retrieved.close = Decimal("75300.00")
        db_session.commit()
        
        updated = db_session.query(MarketData).filter_by(symbol="005930").first()
        assert updated.close == Decimal("75300.00")
        
        # Delete
        db_session.delete(updated)
        db_session.commit()
        
        deleted = db_session.query(MarketData).filter_by(symbol="005930").first()
        assert deleted is None
    
    def test_trade_crud(self, db_session):
        """Trade 모델 CRUD 테스트"""
        # Create
        trade = Trade(
            symbol="005930",
            side="BUY",
            quantity=100,
            price=Decimal("75000.00"),
            commission=Decimal("750.00"),
            strategy_name="test_strategy",
            order_type="MARKET",
            status="FILLED"
        )
        db_session.add(trade)
        db_session.commit()
        
        # Read
        retrieved = db_session.query(Trade).filter_by(symbol="005930").first()
        assert retrieved is not None
        assert retrieved.side == "BUY"
        assert retrieved.quantity == 100
        assert retrieved.price == Decimal("75000.00")
        
        # Cleanup
        db_session.delete(retrieved)
        db_session.commit()
    
    def test_position_crud(self, db_session):
        """Position 모델 CRUD 테스트"""
        # Create
        position = Position(
            symbol="005930",
            quantity=100,
            average_price=Decimal("75000.00"),
            current_price=Decimal("75200.00"),
            unrealized_pnl=Decimal("20000.00")
        )
        db_session.add(position)
        db_session.commit()
        
        # Read
        retrieved = db_session.query(Position).filter_by(symbol="005930").first()
        assert retrieved is not None
        assert retrieved.quantity == 100
        assert retrieved.unrealized_pnl == Decimal("20000.00")
        
        # Cleanup
        db_session.delete(retrieved)
        db_session.commit()
    
    def test_strategy_performance_crud(self, db_session):
        """StrategyPerformance 모델 CRUD 테스트"""
        # Create
        performance = StrategyPerformance(
            strategy_name="test_strategy",
            date=datetime.now(timezone.utc),
            total_return=Decimal("0.0250"),
            trades_count=10,
            win_rate=Decimal("70.00"),
            max_drawdown=Decimal("0.0150"),
            sharpe_ratio=Decimal("1.250")
        )
        db_session.add(performance)
        db_session.commit()
        
        # Read
        retrieved = db_session.query(StrategyPerformance).filter_by(
            strategy_name="test_strategy"
        ).first()
        assert retrieved is not None
        assert retrieved.win_rate == Decimal("70.00")
        assert retrieved.sharpe_ratio == Decimal("1.250")
        
        # Cleanup
        db_session.delete(retrieved)
        db_session.commit()
    
    def test_stock_metadata_crud(self, db_session):
        """StockMetadata 모델 CRUD 테스트"""
        # Create
        stock = StockMetadata(
            symbol="005930",
            name="삼성전자",
            market="KOSPI",
            sector="기술",
            industry="반도체",
            market_cap=400000000000000,
            listed_shares=5969782550
        )
        db_session.add(stock)
        db_session.commit()
        
        # Read
        retrieved = db_session.query(StockMetadata).filter_by(symbol="005930").first()
        assert retrieved is not None
        assert retrieved.name == "삼성전자"
        assert retrieved.market == "KOSPI"
        
        # Cleanup
        db_session.delete(retrieved)
        db_session.commit()
    
    def test_risk_metric_crud(self, db_session):
        """RiskMetric 모델 CRUD 테스트"""
        # Create
        risk_metric = RiskMetric(
            portfolio_value=Decimal("2000000.00"),
            total_exposure=Decimal("1800000.00"),
            cash_balance=Decimal("200000.00"),
            daily_pnl=Decimal("50000.00"),
            var_95=Decimal("100000.00"),
            max_drawdown=Decimal("0.0500")
        )
        db_session.add(risk_metric)
        db_session.commit()
        
        # Read
        retrieved = db_session.query(RiskMetric).filter_by(
            portfolio_value=Decimal("2000000.00")
        ).first()
        assert retrieved is not None
        assert retrieved.daily_pnl == Decimal("50000.00")
        
        # Cleanup
        db_session.delete(retrieved)
        db_session.commit()
    
    def test_system_log_crud(self, db_session):
        """SystemLog 모델 CRUD 테스트"""
        # Create
        log = SystemLog(
            level="INFO",
            component="DataCollector",
            message="Test log message",
            details='{"key": "value"}'
        )
        db_session.add(log)
        db_session.commit()
        
        # Read
        retrieved = db_session.query(SystemLog).filter_by(
            component="DataCollector"
        ).first()
        assert retrieved is not None
        assert retrieved.level == "INFO"
        assert retrieved.message == "Test log message"
        
        # Cleanup
        db_session.delete(retrieved)
        db_session.commit()


if __name__ == "__main__":
    # 직접 실행시 간단한 연결 테스트
    print("Testing database connection...")
    
    manager = DatabaseManager()
    if manager.initialize():
        print("✅ Database connection successful")
        
        info = manager.get_connection_info()
        print(f"✅ Database: {info.get('database', 'unknown')}")
        print(f"✅ User: {info.get('user', 'unknown')}")
        print(f"✅ TimescaleDB: {info.get('timescaledb', {}).get('available', False)}")
        
        table_info = manager.get_table_info()
        print(f"✅ Tables: {table_info.get('total_tables', 0)}")
        print(f"✅ Hypertables: {len(table_info.get('hypertables', []))}")
        
        manager.close()
    else:
        print("❌ Database connection failed")