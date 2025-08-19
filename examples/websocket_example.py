"""
KIS WebSocket Handler 사용 예제
실시간 호가 및 체결 데이터 수신 예제
"""

import asyncio
import logging
import pandas as pd
from datetime import datetime

# 프로젝트 모듈 import
from src.auth.kis_auth import KISAuthManager
from src.api.websocket_handler import KISWebSocketHandler

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebSocketExample:
    """WebSocket 사용 예제"""
    
    def __init__(self):
        self.ws_handler = None
        self.received_data_count = 0
    
    async def setup(self):
        """초기화"""
        try:
            # 인증 관리자 생성
            auth_manager = KISAuthManager()
            
            # WebSocket 핸들러 생성
            self.ws_handler = KISWebSocketHandler(
                auth_manager=auth_manager,
                max_retries=3
            )
            
            # 콜백 함수 설정
            self.ws_handler.set_callbacks(
                on_quote=self.on_quote_received,
                on_tick=self.on_tick_received,
                on_error=self.on_error_occurred
            )
            
            logger.info("WebSocket Handler 초기화 완료")
            
        except Exception as e:
            logger.error(f"초기화 실패: {e}")
            raise
    
    async def on_quote_received(self, df: pd.DataFrame):
        """실시간 호가 데이터 수신 콜백"""
        try:
            self.received_data_count += 1
            
            if not df.empty:
                stock_code = df.iloc[0]['MKSC_SHRN_ISCD']
                
                # 매수 호가 1,2,3
                bid_prices = [df.iloc[0][f'BIDP{i}'] for i in range(1, 4)]
                bid_quantities = [df.iloc[0][f'BIDP_RSQN{i}'] for i in range(1, 4)]
                
                # 매도 호가 1,2,3
                ask_prices = [df.iloc[0][f'ASKP{i}'] for i in range(1, 4)]
                ask_quantities = [df.iloc[0][f'ASKP_RSQN{i}'] for i in range(1, 4)]
                
                logger.info(f"[호가] {stock_code} | " +
                           f"매수: {bid_prices[0]}({bid_quantities[0]}) | " +
                           f"매도: {ask_prices[0]}({ask_quantities[0]})")
                
                # 데이터 처리 로직을 여기에 추가
                await self.process_quote_data(df)
            
        except Exception as e:
            logger.error(f"호가 데이터 처리 오류: {e}")
    
    async def on_tick_received(self, df: pd.DataFrame):
        """실시간 체결 데이터 수신 콜백"""
        try:
            self.received_data_count += 1
            
            if not df.empty:
                stock_code = df.iloc[0]['MKSC_SHRN_ISCD']
                current_price = df.iloc[0]['STCK_PRPR']
                volume = df.iloc[0]['CNTG_VOL']
                change_sign = df.iloc[0]['PRDY_VRSS_SIGN']
                change_amount = df.iloc[0]['PRDY_VRSS']
                change_rate = df.iloc[0]['PRDY_CTRT']
                
                logger.info(f"[체결] {stock_code} | " +
                           f"가격: {current_price} | 거래량: {volume} | " +
                           f"등락: {change_sign}{change_amount}({change_rate}%)")
                
                # 데이터 처리 로직을 여기에 추가
                await self.process_tick_data(df)
            
        except Exception as e:
            logger.error(f"체결 데이터 처리 오류: {e}")
    
    async def on_error_occurred(self, error: Exception, message: str = None):
        """에러 발생 콜백"""
        logger.error(f"WebSocket 에러: {error}")
        if message:
            logger.error(f"관련 메시지: {message}")
        
        # 에러 처리 로직을 여기에 추가
        await self.handle_error(error)
    
    async def process_quote_data(self, df: pd.DataFrame):
        """호가 데이터 처리"""
        # 실제 매매 전략에서는 여기에 호가 분석 로직을 구현
        # 예: 호가창 압박 분석, 스프레드 분석 등
        pass
    
    async def process_tick_data(self, df: pd.DataFrame):
        """체결 데이터 처리"""
        # 실제 매매 전략에서는 여기에 체결 분석 로직을 구현
        # 예: RSI 계산, 이동평균 업데이트, 매매 신호 생성 등
        pass
    
    async def handle_error(self, error: Exception):
        """에러 처리"""
        # 실제 매매 시스템에서는 여기에 에러 복구 로직을 구현
        # 예: 알림 발송, 포지션 정리, 시스템 재시작 등
        pass
    
    async def run_example(self):
        """예제 실행"""
        try:
            await self.setup()
            
            # WebSocket 연결
            await self.ws_handler.connect()
            logger.info("WebSocket 연결됨")
            
            # 관심 종목 설정
            target_stocks = ["005930", "000660"]  # 삼성전자, SK하이닉스
            
            # 실시간 호가 구독 (통합 거래소)
            success = await self.ws_handler.subscribe_quote(
                stock_codes=target_stocks,
                exchange="UN"  # 통합 거래소 (기본값)
            )
            
            if success:
                logger.info(f"실시간 호가 구독 완료: {target_stocks}")
            else:
                logger.warning("일부 호가 구독이 실패했습니다")
            
            # 실시간 체결 구독 (통합 거래소)
            success = await self.ws_handler.subscribe_tick(
                stock_codes=target_stocks,
                exchange="UN"  # 통합 거래소 (기본값)
            )
            
            if success:
                logger.info(f"실시간 체결 구독 완료: {target_stocks}")
            else:
                logger.warning("일부 체결 구독이 실패했습니다")
            
            # 구독 상태 확인
            subscriptions = self.ws_handler.get_subscriptions()
            logger.info(f"현재 구독 수: {len(subscriptions)}")
            
            # 실시간 데이터 수신 (30초간)
            logger.info("실시간 데이터 수신 시작... (30초간)")
            await asyncio.sleep(30)
            
            # 통계 출력
            logger.info(f"총 수신 데이터: {self.received_data_count}건")
            
            # 구독 해제
            for stock_code in target_stocks:
                await self.ws_handler.unsubscribe(
                    stock_code=stock_code,
                    data_type="all",
                    exchange="UN"
                )
            
            logger.info("모든 구독 해제 완료")
            
        except Exception as e:
            logger.error(f"예제 실행 오류: {e}")
            raise
        
        finally:
            # WebSocket 연결 해제
            if self.ws_handler:
                await self.ws_handler.disconnect()
                logger.info("WebSocket 연결 해제됨")


async def main():
    """메인 함수"""
    example = WebSocketExample()
    
    try:
        await example.run_example()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"예제 실행 중 오류: {e}")
    finally:
        logger.info("예제 종료")


if __name__ == "__main__":
    # 이벤트 루프 실행
    asyncio.run(main())