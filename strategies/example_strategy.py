"""
예제 전략

기본 전략 템플릿
"""

from qb.engines.strategy_engine.base_strategy import BaseStrategy


class ExampleStrategy(BaseStrategy):
    """예제 전략 클래스"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.name = "Example Strategy"
        self.version = "1.0.0"
    
    async def on_market_data(self, data):
        """시장 데이터 수신 핸들러"""
        # 전략 로직 구현
        pass
    
    async def generate_signal(self, symbol, data):
        """매매 신호 생성"""
        # 신호 생성 로직
        return None