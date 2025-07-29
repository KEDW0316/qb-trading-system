"""
전략 로더 모듈

동적으로 전략 클래스를 발견하고 로드/언로드하는 플러그인 시스템을 구현합니다.
런타임에 새로운 전략을 추가하거나 기존 전략을 교체할 수 있습니다.
"""

import importlib
import inspect
import os
import sys
from pathlib import Path
from typing import Dict, Type, List, Optional, Any
import logging
from datetime import datetime

from .base import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyLoader:
    """
    전략 플러그인 로더
    
    전략 디렉토리를 스캔하여 사용 가능한 전략 클래스를 자동으로 발견하고,
    런타임에 동적으로 로드/언로드할 수 있는 기능을 제공합니다.
    """

    def __init__(self, strategies_dir: str = "strategies", redis_manager=None):
        """
        전략 로더 초기화
        
        Args:
            strategies_dir: 전략 파일이 위치한 디렉토리 경로
            redis_manager: Redis 연결 관리자
        """
        self.strategies_dir = strategies_dir
        self.redis_manager = redis_manager
        self.available_strategies: Dict[str, Type[BaseStrategy]] = {}
        self.loaded_strategies: Dict[str, BaseStrategy] = {}
        self.strategy_modules: Dict[str, Any] = {}
        
        # 전략 디렉토리 경로 설정
        self._setup_strategy_path()
        
        logger.info(f"StrategyLoader initialized with directory: {self.strategies_dir}")

    def _setup_strategy_path(self):
        """전략 디렉토리를 Python 경로에 추가"""
        try:
            # 현재 작업 디렉토리 기준 전략 경로 설정
            current_dir = Path.cwd()
            strategy_path = current_dir / "qb" / "engines" / "strategy_engine" / self.strategies_dir
            
            if not strategy_path.exists():
                strategy_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created strategy directory: {strategy_path}")
            
            # __init__.py 파일 생성 (패키지로 인식되도록)
            init_file = strategy_path / "__init__.py"
            if not init_file.exists():
                init_file.touch()
                logger.info(f"Created __init__.py in strategy directory")
            
            self.strategy_path = strategy_path
            
        except Exception as e:
            logger.error(f"Error setting up strategy path: {e}")
            raise

    def discover_strategies(self) -> List[str]:
        """
        전략 디렉토리에서 사용 가능한 전략 클래스 탐색
        
        Returns:
            List[str]: 발견된 전략 클래스명 리스트
        """
        discovered = []
        
        try:
            if not self.strategy_path.exists():
                logger.warning(f"Strategy directory does not exist: {self.strategy_path}")
                return discovered
            
            # .py 파일 스캔
            for py_file in self.strategy_path.glob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                
                module_name = py_file.stem
                strategies_in_module = self._discover_strategies_in_module(module_name)
                discovered.extend(strategies_in_module)
            
            logger.info(f"Discovered {len(discovered)} strategies: {discovered}")
            return discovered
            
        except Exception as e:
            logger.error(f"Error discovering strategies: {e}")
            return discovered

    def _discover_strategies_in_module(self, module_name: str) -> List[str]:
        """
        특정 모듈에서 전략 클래스 탐색
        
        Args:
            module_name: 모듈명
            
        Returns:
            List[str]: 모듈 내 전략 클래스명 리스트
        """
        strategies = []
        
        try:
            # 모듈 동적 import
            module_path = f"qb.engines.strategy_engine.{self.strategies_dir}.{module_name}"
            
            # 이미 로드된 모듈인 경우 리로드
            if module_path in sys.modules:
                module = importlib.reload(sys.modules[module_path])
            else:
                module = importlib.import_module(module_path)
            
            # 모듈 내 클래스 검사
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # BaseStrategy를 상속받고, 추상 클래스가 아닌 클래스만 선택
                if (issubclass(obj, BaseStrategy) and 
                    obj != BaseStrategy and 
                    not inspect.isabstract(obj)):
                    
                    strategy_name = name
                    self.available_strategies[strategy_name] = obj
                    self.strategy_modules[strategy_name] = module
                    strategies.append(strategy_name)
                    
                    logger.debug(f"Found strategy class: {strategy_name} in module {module_name}")
            
        except Exception as e:
            logger.error(f"Error discovering strategies in module {module_name}: {e}")
        
        return strategies

    def load_strategy(self, strategy_name: str, params: Optional[Dict[str, Any]] = None) -> Optional[BaseStrategy]:
        """
        전략 이름으로 전략 인스턴스 로드
        
        Args:
            strategy_name: 로드할 전략 클래스명
            params: 전략 초기화 파라미터
            
        Returns:
            BaseStrategy: 로드된 전략 인스턴스 또는 None
        """
        try:
            # 이미 로드된 전략인 경우
            if strategy_name in self.loaded_strategies:
                logger.warning(f"Strategy {strategy_name} is already loaded")
                return self.loaded_strategies[strategy_name]
            
            # 사용 가능한 전략인지 확인
            if strategy_name not in self.available_strategies:
                # 전략 재탐색
                self.discover_strategies()
                
                if strategy_name not in self.available_strategies:
                    logger.error(f"Strategy {strategy_name} not found in available strategies")
                    return None
            
            # 전략 클래스 가져오기
            strategy_class = self.available_strategies[strategy_name]
            
            # 파라미터 검증 및 기본값 설정
            if params is None:
                # 전략의 기본 파라미터 사용
                temp_instance = strategy_class(redis_manager=self.redis_manager)
                params = temp_instance.get_default_parameters()
                del temp_instance
            
            # 전략 인스턴스 생성 (redis_manager 전달)
            strategy_instance = strategy_class(params, self.redis_manager)
            
            # 파라미터 유효성 검증
            if not strategy_instance.validate_parameters(params):
                logger.error(f"Invalid parameters for strategy {strategy_name}: {params}")
                return None
            
            # 로드된 전략 등록
            self.loaded_strategies[strategy_name] = strategy_instance
            
            logger.info(f"Successfully loaded strategy: {strategy_name}")
            return strategy_instance
            
        except Exception as e:
            logger.error(f"Error loading strategy {strategy_name}: {e}")
            return None

    def unload_strategy(self, strategy_name: str) -> bool:
        """
        로드된 전략 언로드
        
        Args:
            strategy_name: 언로드할 전략명
            
        Returns:
            bool: 언로드 성공 여부
        """
        try:
            if strategy_name not in self.loaded_strategies:
                logger.warning(f"Strategy {strategy_name} is not loaded")
                return False
            
            # 전략 비활성화
            strategy = self.loaded_strategies[strategy_name]
            strategy.disable()
            
            # 로드된 전략에서 제거
            del self.loaded_strategies[strategy_name]
            
            logger.info(f"Successfully unloaded strategy: {strategy_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error unloading strategy {strategy_name}: {e}")
            return False

    def reload_strategy(self, strategy_name: str, params: Optional[Dict[str, Any]] = None) -> Optional[BaseStrategy]:
        """
        전략 리로드 (언로드 후 다시 로드)
        
        Args:
            strategy_name: 리로드할 전략명
            params: 새로운 파라미터
            
        Returns:
            BaseStrategy: 리로드된 전략 인스턴스 또는 None
        """
        try:
            # 기존 파라미터 보존 (새 파라미터가 없는 경우)
            if params is None and strategy_name in self.loaded_strategies:
                params = self.loaded_strategies[strategy_name].get_parameters()
            
            # 언로드
            self.unload_strategy(strategy_name)
            
            # 모듈 리로드
            if strategy_name in self.strategy_modules:
                importlib.reload(self.strategy_modules[strategy_name])
            
            # 전략 재탐색
            self.discover_strategies()
            
            # 다시 로드
            return self.load_strategy(strategy_name, params)
            
        except Exception as e:
            logger.error(f"Error reloading strategy {strategy_name}: {e}")
            return None

    def get_available_strategies(self) -> List[str]:
        """사용 가능한 전략 목록 반환"""
        return list(self.available_strategies.keys())

    def get_loaded_strategies(self) -> List[str]:
        """현재 로드된 전략 목록 반환"""
        return list(self.loaded_strategies.keys())

    def get_strategy_info(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """
        전략 정보 조회
        
        Args:
            strategy_name: 조회할 전략명
            
        Returns:
            Dict: 전략 정보 또는 None
        """
        try:
            if strategy_name in self.loaded_strategies:
                strategy = self.loaded_strategies[strategy_name]
                return strategy.get_status()
            elif strategy_name in self.available_strategies:
                strategy_class = self.available_strategies[strategy_name]
                # 임시 인스턴스로 정보 조회
                temp_instance = strategy_class()
                info = {
                    'name': strategy_name,
                    'loaded': False,
                    'description': temp_instance.get_description(),
                    'required_indicators': temp_instance.get_required_indicators(),
                    'parameter_schema': temp_instance.get_parameter_schema(),
                    'default_parameters': temp_instance.get_default_parameters()
                }
                del temp_instance
                return info
            else:
                logger.warning(f"Strategy {strategy_name} not found")
                return None
                
        except Exception as e:
            logger.error(f"Error getting strategy info for {strategy_name}: {e}")
            return None

    def get_all_strategies_info(self) -> Dict[str, Dict[str, Any]]:
        """모든 전략의 정보 반환"""
        all_info = {}
        
        # 사용 가능한 모든 전략에 대해 정보 수집
        for strategy_name in self.available_strategies:
            info = self.get_strategy_info(strategy_name)
            if info:
                all_info[strategy_name] = info
        
        return all_info

    def validate_strategy_file(self, file_path: Path) -> bool:
        """
        전략 파일의 유효성 검증
        
        Args:
            file_path: 검증할 전략 파일 경로
            
        Returns:
            bool: 유효성 검증 결과
        """
        try:
            if not file_path.exists() or not file_path.suffix == '.py':
                return False
            
            # 파일을 임시로 로드하여 유효한 전략 클래스가 있는지 확인
            module_name = file_path.stem
            strategies = self._discover_strategies_in_module(module_name)
            
            return len(strategies) > 0
            
        except Exception as e:
            logger.error(f"Error validating strategy file {file_path}: {e}")
            return False

    def create_strategy_template(self, strategy_name: str) -> bool:
        """
        새로운 전략 템플릿 파일 생성
        
        Args:
            strategy_name: 생성할 전략명
            
        Returns:
            bool: 생성 성공 여부
        """
        try:
            # 파일명을 snake_case로 변환
            file_name = ''.join(['_' + c.lower() if c.isupper() else c for c in strategy_name]).lstrip('_')
            file_path = self.strategy_path / f"{file_name}.py"
            
            if file_path.exists():
                logger.error(f"Strategy file already exists: {file_path}")
                return False
            
            template = f'''"""
{strategy_name} 전략 구현

TODO: 전략 로직을 구현하세요.
"""

from typing import Dict, Any, List, Optional
from ..base import BaseStrategy, MarketData, TradingSignal


class {strategy_name}(BaseStrategy):
    """
    {strategy_name} 전략
    
    TODO: 전략 설명을 작성하세요.
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {{
            # TODO: 기본 파라미터 설정
            # 'period': 20,
            # 'threshold': 0.5
        }}
        super().__init__(params or default_params)

    async def analyze(self, market_data: MarketData) -> Optional[TradingSignal]:
        """
        시장 데이터 분석 및 거래 신호 생성
        
        Args:
            market_data: 시장 데이터
            
        Returns:
            TradingSignal: 거래 신호 또는 None
        """
        # TODO: 전략 로직 구현
        
        # 예시: 간단한 신호 생성
        # if some_condition:
        #     return TradingSignal(
        #         action='BUY',
        #         symbol=market_data.symbol,
        #         confidence=0.8,
        #         reason='strategy_condition_met'
        #     )
        
        return None

    def get_required_indicators(self) -> List[str]:
        """필요한 기술적 지표 목록 반환"""
        return [
            # TODO: 필요한 지표 목록 작성
            # 'sma_20',
            # 'rsi',
            # 'macd'
        ]

    def get_parameter_schema(self) -> Dict[str, Dict[str, Any]]:
        """파라미터 스키마 정보 반환"""
        return {{
            # TODO: 파라미터 스키마 정의
            # 'period': {{
            #     'type': int,
            #     'default': 20,
            #     'min': 1,
            #     'max': 200,
            #     'description': '이동평균 기간'
            # }},
            # 'threshold': {{
            #     'type': float,
            #     'default': 0.5,
            #     'min': 0.0,
            #     'max': 1.0,
            #     'description': '신호 임계값'
            # }}
        }}

    def get_description(self) -> str:
        """전략 설명 반환"""
        return f"{strategy_name} 전략 - TODO: 상세 설명 작성"
'''

            # 템플릿 파일 작성
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(template)
            
            logger.info(f"Created strategy template: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating strategy template {strategy_name}: {e}")
            return False

    def get_loader_status(self) -> Dict[str, Any]:
        """로더 상태 정보 반환"""
        return {
            'strategies_dir': str(self.strategy_path),
            'available_strategies': len(self.available_strategies),
            'loaded_strategies': len(self.loaded_strategies),
            'available_list': self.get_available_strategies(),
            'loaded_list': self.get_loaded_strategies(),
            'last_discovery': datetime.now().isoformat()
        }

    def __str__(self) -> str:
        return f"StrategyLoader(available={len(self.available_strategies)}, loaded={len(self.loaded_strategies)})"

    def __repr__(self) -> str:
        return f"<StrategyLoader dir='{self.strategies_dir}' available={len(self.available_strategies)} loaded={len(self.loaded_strategies)}>"