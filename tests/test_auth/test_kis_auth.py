"""
KIS 인증 시스템 테스트 (TDD)
실패하는 테스트를 먼저 작성하여 요구사항을 명확히 정의
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock, mock_open
from datetime import datetime, timedelta
from pathlib import Path

# 아직 구현되지 않은 모듈들 - 테스트가 실패해야 함!
from src.auth.kis_auth import KISAuthManager
from src.auth.models import TokenInfo, KISCredentials
from src.auth.exceptions import TokenExpiredError, TokenIssueError


class TestKISAuthManager:
    """KIS 인증 관리자 테스트 클래스"""

    def setup_method(self):
        """각 테스트 전 초기화"""
        # Mock 환경변수 설정
        with patch.dict('os.environ', {
            'KIS_APP_KEY': 'test_app_key',
            'KIS_APP_SECRET': 'test_app_secret',
            'KIS_ACCOUNT_NO': '12345678-01',
            'KIS_ACCOUNT_PROD_CD': '01'
        }):
            self.auth_manager = KISAuthManager(env="vps")
        
        self.mock_credentials = KISCredentials(
            app_key="test_app_key",
            app_secret="test_app_secret", 
            account_no="12345678-01",
            account_prod_cd="01"
        )

    def test_init_with_valid_env(self):
        """유효한 환경으로 초기화 테스트"""
        # Given
        env = "vps"
        
        # When (환경변수 Mock과 함께)
        with patch.dict('os.environ', {
            'KIS_APP_KEY': 'test_app_key',
            'KIS_APP_SECRET': 'test_app_secret',
            'KIS_ACCOUNT_NO': '12345678-01',
            'KIS_ACCOUNT_PROD_CD': '01'
        }):
            auth_manager = KISAuthManager(env=env)
        
        # Then
        assert auth_manager.env == "vps"
        assert "vts" in auth_manager._get_api_base_url()  # 모의투자 URL
        assert auth_manager._get_token_file_path().endswith("kis_token_vps.json")

    def test_init_with_prod_env(self):
        """실전투자 환경 초기화 테스트"""
        # Given
        env = "prod"
        
        # When (환경변수 Mock과 함께)
        with patch.dict('os.environ', {
            'KIS_APP_KEY': 'test_app_key',
            'KIS_APP_SECRET': 'test_app_secret',
            'KIS_ACCOUNT_NO': '12345678-01',
            'KIS_ACCOUNT_PROD_CD': '01'
        }):
            auth_manager = KISAuthManager(env=env)
        
        # Then
        assert auth_manager.env == "prod"
        assert "openapi.koreainvestment.com" in auth_manager._get_api_base_url()
        assert auth_manager._get_token_file_path().endswith("kis_token_prod.json")

    @pytest.mark.asyncio
    async def test_get_access_token_with_valid_cached_token(self):
        """유효한 캐시된 토큰 조회 테스트"""
        # Given - 유효한 토큰이 파일에 저장되어 있음
        valid_token = TokenInfo(
            access_token="valid_token_123",
            expires_at=datetime.now() + timedelta(hours=12)  # 12시간 남음
        )
        
        with patch.object(self.auth_manager, '_load_token_from_file', return_value=valid_token):
            # When
            token = await self.auth_manager.get_access_token()
            
            # Then
            assert token == "valid_token_123"

    @pytest.mark.asyncio
    async def test_get_access_token_with_expired_token_auto_renew(self):
        """만료된 토큰 자동 갱신 테스트"""
        # Given - 만료된 토큰
        expired_token = TokenInfo(
            access_token="expired_token",
            expires_at=datetime.now() - timedelta(hours=1)  # 1시간 전 만료
        )
        
        new_token = TokenInfo(
            access_token="new_token_456",
            expires_at=datetime.now() + timedelta(hours=24)
        )
        
        with patch.object(self.auth_manager, '_load_token_from_file', return_value=expired_token), \
             patch.object(self.auth_manager, '_issue_new_token', new_callable=AsyncMock, return_value=new_token), \
             patch.object(self.auth_manager, '_save_token_to_file') as mock_save:
            
            # When
            token = await self.auth_manager.get_access_token()
            
            # Then
            assert token == "new_token_456"
            mock_save.assert_called_once_with(new_token)

    @pytest.mark.asyncio
    async def test_get_access_token_no_cached_token(self):
        """캐시된 토큰이 없을 때 새로 발급"""
        # Given - 캐시된 토큰이 없음
        new_token = TokenInfo(
            access_token="fresh_token_789",
            expires_at=datetime.now() + timedelta(hours=24)
        )
        
        with patch.object(self.auth_manager, '_load_token_from_file', return_value=None), \
             patch.object(self.auth_manager, '_issue_new_token', new_callable=AsyncMock, return_value=new_token), \
             patch.object(self.auth_manager, '_save_token_to_file') as mock_save:
            
            # When
            token = await self.auth_manager.get_access_token()
            
            # Then
            assert token == "fresh_token_789"
            mock_save.assert_called_once_with(new_token)

    @pytest.mark.asyncio
    async def test_issue_new_token_success(self):
        """새 토큰 발급 성공 테스트"""
        # Given
        mock_response = {
            "access_token": "newly_issued_token",
            "token_type": "Bearer",
            "expires_in": 86400
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aenter__.return_value.status = 200
            
            # When
            token_info = await self.auth_manager._issue_new_token()
            
            # Then
            assert token_info.access_token == "newly_issued_token"
            assert token_info.token_type == "Bearer"
            assert token_info.expires_in == 86400
            assert token_info.expires_at is not None

    @pytest.mark.asyncio
    async def test_issue_new_token_failure(self):
        """토큰 발급 실패 테스트"""
        # Given - API 에러 응답
        mock_response = {
            "error": "invalid_client",
            "error_description": "Invalid client credentials"
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aenter__.return_value.status = 401
            
            # When & Then
            with pytest.raises(TokenIssueError) as exc_info:
                await self.auth_manager._issue_new_token()
            
            assert "Invalid client credentials" in str(exc_info.value)

    def test_save_and_load_token_file(self):
        """토큰 파일 저장/로드 테스트"""
        # Given
        token_info = TokenInfo(
            access_token="test_token",
            expires_at=datetime.now() + timedelta(hours=24),
            created_at=datetime.now()
        )
        
        # Mock file operations
        mock_file_content = json.dumps({
            "access_token": token_info.access_token,
            "token_type": token_info.token_type, 
            "expires_in": token_info.expires_in,
            "expires_at": token_info.expires_at.isoformat(),
            "created_at": token_info.created_at.isoformat()
        })
        
        with patch("builtins.open", mock_open(read_data=mock_file_content)):
            with patch("pathlib.Path.exists", return_value=True):
                # When - Save
                self.auth_manager._save_token_to_file(token_info)
                
                # When - Load
                loaded_token = self.auth_manager._load_token_from_file()
                
                # Then
                assert loaded_token is not None
                assert loaded_token.access_token == "test_token"

    def test_is_token_valid_with_valid_token(self):
        """유효한 토큰 검증 테스트"""
        # Given - 12시간 남은 토큰
        token_info = TokenInfo(
            access_token="valid_token",
            expires_at=datetime.now() + timedelta(hours=12)
        )
        
        # When
        is_valid = self.auth_manager._is_token_valid(token_info)
        
        # Then
        assert is_valid is True

    def test_is_token_valid_with_expired_token(self):
        """만료된 토큰 검증 테스트"""
        # Given - 1시간 전 만료된 토큰
        token_info = TokenInfo(
            access_token="expired_token",
            expires_at=datetime.now() - timedelta(hours=1)
        )
        
        # When
        is_valid = self.auth_manager._is_token_valid(token_info)
        
        # Then
        assert is_valid is False

    def test_is_token_valid_with_none_token(self):
        """None 토큰 검증 테스트"""
        # When
        is_valid = self.auth_manager._is_token_valid(None)
        
        # Then
        assert is_valid is False

    def test_get_headers_format(self):
        """API 호출용 헤더 형식 테스트"""
        # Given - 유효한 토큰이 파일에 저장되어 있음
        valid_token = TokenInfo(
            access_token="test_token_123",
            expires_at=datetime.now() + timedelta(hours=12)
        )
        
        with patch.object(self.auth_manager, '_load_token_from_file', return_value=valid_token):
            # When
            headers = self.auth_manager.get_headers()
            
            # Then
            assert headers["Authorization"] == "Bearer test_token_123"
            assert headers["Content-Type"] == "application/json"
            assert "appkey" in headers
            assert "appsecret" in headers

    @pytest.mark.asyncio
    async def test_get_websocket_approval_key_success(self):
        """WebSocket 인증키 발급 성공 테스트"""
        # Given
        mock_response = {
            "approval_key": "websocket_approval_key_123"
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aenter__.return_value.status = 200
            
            # When
            approval_key = await self.auth_manager.get_websocket_approval_key()
            
            # Then
            assert approval_key == "websocket_approval_key_123"

    def test_get_token_expiry_time_calculation(self):
        """토큰 만료시간 계산 테스트"""
        # Given
        expires_in_seconds = 86400  # 24시간
        
        # When
        expiry_time = self.auth_manager._get_token_expiry_time(expires_in_seconds)
        
        # Then
        expected_time = datetime.now() + timedelta(seconds=expires_in_seconds)
        # 1분 오차 허용 (테스트 실행 시간 고려)
        assert abs((expiry_time - expected_time).total_seconds()) < 60