"""
KIS API HTTP Client 테스트 (TDD)
API 호출을 쉽게 만들어주는 래퍼 클래스 테스트
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# 아직 구현되지 않은 모듈
from src.api.http_client import KISHttpClient
from src.auth.kis_auth import KISAuthManager
from src.utils.rate_limiter import RateLimiter


class TestKISHttpClient:
    """KIS API HTTP Client 테스트"""
    
    def setup_method(self):
        """각 테스트 전 초기화"""
        with patch.dict('os.environ', {
            'KIS_APP_KEY': 'test_app_key',
            'KIS_APP_SECRET': 'test_app_secret',
            'KIS_ACCOUNT_NO': '12345678-01',
            'KIS_ACCOUNT_PROD_CD': '01'
        }):
            self.auth_manager = KISAuthManager(env="vps")
            self.rate_limiter = RateLimiter()
            self.client = KISHttpClient(self.auth_manager, self.rate_limiter)
    
    @pytest.mark.asyncio
    async def test_get_current_price(self):
        """현재가 조회 테스트"""
        # Given
        mock_response = {
            "rt_cd": "0",
            "msg_cd": "APBK0013",
            "msg1": "주식현재가 조회가 완료되었습니다.",
            "output": {
                "stck_prpr": "70000",  # 현재가
                "prdy_vrss": "1000",   # 전일대비
                "prdy_ctrt": "1.45",   # 등락률
                "acml_vol": "15234567" # 누적거래량
            }
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_get.return_value.__aenter__.return_value.status = 200
            
            # When
            result = await self.client.get_current_price("005930")
            
            # Then
            assert result["stck_prpr"] == "70000"
            assert result["prdy_vrss"] == "1000"
            assert result["prdy_ctrt"] == "1.45"
    
    @pytest.mark.asyncio
    async def test_get_daily_chart(self):
        """일봉 차트 조회 테스트"""
        # Given
        mock_response = {
            "rt_cd": "0",
            "msg1": "일별주가 조회 성공",
            "output1": [
                {
                    "stck_bsop_date": "20240118",
                    "stck_oprc": "70000",  # 시가
                    "stck_hgpr": "71000",  # 고가
                    "stck_lwpr": "69500",  # 저가
                    "stck_clpr": "70500",  # 종가
                    "acml_vol": "12345678"  # 거래량
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_get.return_value.__aenter__.return_value.status = 200
            
            # When
            result = await self.client.get_daily_chart("005930", start_date="20240118", end_date="20240118")
            
            # Then
            assert len(result) == 1
            assert result[0]["stck_clpr"] == "70500"
            assert result[0]["stck_bsop_date"] == "20240118"
    
    @pytest.mark.asyncio
    async def test_get_account_balance(self):
        """계좌 잔고 조회 테스트"""
        # Given
        mock_response = {
            "rt_cd": "0",
            "msg1": "계좌 잔고 조회 성공",
            "output1": [
                {
                    "pdno": "005930",
                    "prdt_name": "삼성전자",
                    "hldg_qty": "100",
                    "evlu_amt": "7000000",
                    "pchs_avg_pric": "68000"
                }
            ],
            "output2": [
                {
                    "dnca_tot_amt": "10000000",  # 예수금
                    "tot_evlu_amt": "17000000",  # 총평가금액
                    "pchs_amt_smtl_amt": "16800000"  # 매입금액합계
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_get.return_value.__aenter__.return_value.status = 200
            
            # When
            stocks, summary = await self.client.get_account_balance()
            
            # Then
            assert len(stocks) == 1
            assert stocks[0]["pdno"] == "005930"
            assert stocks[0]["hldg_qty"] == "100"
            assert summary["dnca_tot_amt"] == "10000000"
    
    @pytest.mark.asyncio
    async def test_place_order(self):
        """주문 실행 테스트"""
        # Given
        mock_response = {
            "rt_cd": "0",
            "msg1": "주문이 정상 처리되었습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": "91234",
                "ODNO": "0000123456",
                "ORD_TMD": "145623"
            }
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aenter__.return_value.status = 200
            
            # When
            result = await self.client.place_order(
                stock_code="005930",
                order_type="buy",
                quantity=10,
                price=70000
            )
            
            # Then
            assert result["ODNO"] == "0000123456"
            assert result["ORD_TMD"] is not None
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """에러 처리 테스트"""
        # Given - API 에러 응답
        mock_response = {
            "rt_cd": "1",
            "msg_cd": "APBK0919",
            "msg1": "계좌번호 오류입니다."
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_get.return_value.__aenter__.return_value.status = 200
            
            # When & Then
            with pytest.raises(Exception) as exc_info:
                await self.client.get_current_price("005930")
            
            assert "계좌번호 오류" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self):
        """Rate Limiter 통합 테스트"""
        # Given
        self.client.rate_limiter.max_calls = 2
        self.client.rate_limiter.time_window = 0.1
        
        mock_response = {
            "rt_cd": "0",
            "output": {"stck_prpr": "70000"}
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_get.return_value.__aenter__.return_value.status = 200
            
            # When - 3번째 호출은 대기해야 함
            start_time = datetime.now()
            
            await self.client.get_current_price("005930")
            await self.client.get_current_price("000660")
            await self.client.get_current_price("035420")  # 이 호출은 대기
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Then
            assert elapsed >= 0.1  # Rate limit으로 인한 대기 발생
    
    @pytest.mark.asyncio
    async def test_auto_token_renewal(self):
        """토큰 자동 갱신 테스트"""
        # Given - 만료된 토큰
        with patch.object(self.auth_manager, 'get_access_token', 
                         new=AsyncMock(return_value="new_token_123")):
            
            mock_response = {"rt_cd": "0", "output": {"stck_prpr": "70000"}}
            
            with patch('aiohttp.ClientSession.get') as mock_get:
                mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
                mock_get.return_value.__aenter__.return_value.status = 200
                
                # When
                await self.client.get_current_price("005930")
                
                # Then - 헤더에 새 토큰이 사용되었는지 확인
                call_args = mock_get.call_args
                headers = call_args[1].get('headers', {})
                assert "Bearer new_token_123" in headers.get('Authorization', '')