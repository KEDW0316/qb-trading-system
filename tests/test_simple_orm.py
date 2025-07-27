"""
간단한 ORM 모델 CRUD 테스트
"""

import sys
import os
from datetime import datetime, timezone
from decimal import Decimal

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from qb.database.connection import DatabaseManager
from qb.database.models import MarketData, Trade, Position

def test_market_data_crud():
    """MarketData 모델 CRUD 테스트"""
    print("🔥 Testing MarketData CRUD...")
    
    manager = DatabaseManager()
    assert manager.initialize(), "Failed to initialize database"
    
    with manager.get_session() as session:
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
        session.add(market_data)
        session.commit()
        print("✅ MarketData created")
        
        # Read
        retrieved = session.query(MarketData).filter_by(symbol="005930").first()
        assert retrieved is not None
        assert retrieved.symbol == "005930"
        assert retrieved.close == Decimal("75200.00")
        print("✅ MarketData retrieved")
        
        # Update
        retrieved.close = Decimal("75300.00")
        session.commit()
        
        updated = session.query(MarketData).filter_by(symbol="005930").first()
        assert updated.close == Decimal("75300.00")
        print("✅ MarketData updated")
        
        # Delete
        session.delete(updated)
        session.commit()
        
        deleted = session.query(MarketData).filter_by(symbol="005930").first()
        assert deleted is None
        print("✅ MarketData deleted")
    
    manager.close()

def test_trade_crud():
    """Trade 모델 CRUD 테스트"""
    print("\n💰 Testing Trade CRUD...")
    
    manager = DatabaseManager()
    assert manager.initialize(), "Failed to initialize database"
    
    with manager.get_session() as session:
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
        session.add(trade)
        session.commit()
        print("✅ Trade created")
        
        # Read
        retrieved = session.query(Trade).filter_by(symbol="005930").first()
        assert retrieved is not None
        assert retrieved.side == "BUY"
        assert retrieved.quantity == 100
        assert retrieved.price == Decimal("75000.00")
        print("✅ Trade retrieved")
        
        # Cleanup
        session.delete(retrieved)
        session.commit()
        print("✅ Trade deleted")
    
    manager.close()

def test_position_crud():
    """Position 모델 CRUD 테스트"""
    print("\n📊 Testing Position CRUD...")
    
    manager = DatabaseManager()
    assert manager.initialize(), "Failed to initialize database"
    
    with manager.get_session() as session:
        # Create
        position = Position(
            symbol="005930",
            quantity=100,
            average_price=Decimal("75000.00"),
            current_price=Decimal("75200.00"),
            unrealized_pnl=Decimal("20000.00")
        )
        session.add(position)
        session.commit()
        print("✅ Position created")
        
        # Read
        retrieved = session.query(Position).filter_by(symbol="005930").first()
        assert retrieved is not None
        assert retrieved.quantity == 100
        assert retrieved.unrealized_pnl == Decimal("20000.00")
        print("✅ Position retrieved")
        
        # Cleanup
        session.delete(retrieved)
        session.commit()
        print("✅ Position deleted")
    
    manager.close()

if __name__ == "__main__":
    print("🚀 Starting ORM CRUD Tests...")
    
    try:
        test_market_data_crud()
        test_trade_crud() 
        test_position_crud()
        print("\n🎉 All tests passed! Task 20 완료!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()