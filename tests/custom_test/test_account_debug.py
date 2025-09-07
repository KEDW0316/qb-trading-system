#!/usr/bin/env python3
"""
계좌 정보 조회 디버깅 테스트
"""

import sys
import os
import json

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.api.bithumb_api import BithumbAPI

def test_account_info():
    """계좌 정보 조회 테스트"""
    print("🔍 계좌 정보 조회 디버깅 시작...")
    
    # 1. 환경변수 확인
    print("\n1. 환경변수 확인:")
    api_key = os.getenv('BIT_APP_KEY')
    secret_key = os.getenv('BIT_APP_SECRET')
    
    print(f"   BIT_APP_KEY: {'설정됨' if api_key else '❌ 설정되지 않음'}")
    print(f"   BIT_APP_SECRET: {'설정됨' if secret_key else '❌ 설정되지 않음'}")
    
    if not api_key or not secret_key:
        print("\n❌ API 키가 설정되지 않았습니다!")
        print("   .env 파일을 생성하고 다음을 추가하세요:")
        print("   BIT_APP_KEY=your_api_key")
        print("   BIT_APP_SECRET=your_secret_key")
        return
    
    # 2. API 객체 생성
    print("\n2. API 객체 생성:")
    try:
        api = BithumbAPI()
        print("   ✅ BithumbAPI 객체 생성 성공")
    except Exception as e:
        print(f"   ❌ BithumbAPI 객체 생성 실패: {e}")
        return
    
    # 3. 공개 API 테스트 (인증 불필요)
    print("\n3. 공개 API 테스트:")
    try:
        market_list = api.get_market_list()
        print(f"   ✅ 마켓 리스트 조회 성공: {len(market_list) if isinstance(market_list, list) else '알 수 없음'}개")
    except Exception as e:
        print(f"   ❌ 마켓 리스트 조회 실패: {e}")
    
    # 4. 계좌 정보 조회 테스트
    print("\n4. 계좌 정보 조회 테스트:")
    try:
        account_info = api.get_account_info()
        print(f"   응답 타입: {type(account_info)}")
        print(f"   응답 내용: {json.dumps(account_info, indent=2, ensure_ascii=False)}")
        
        if isinstance(account_info, dict) and "status" in account_info:
            if account_info["status"] == "error":
                print(f"   ❌ API 오류: {account_info.get('message', '알 수 없는 오류')}")
            else:
                print("   ✅ 계좌 정보 조회 성공")
        elif isinstance(account_info, list):
            print(f"   ✅ 계좌 정보 조회 성공: {len(account_info)}개 화폐")
        else:
            print(f"   ⚠️ 예상치 못한 응답 형식: {account_info}")
            
    except Exception as e:
        print(f"   ❌ 계좌 정보 조회 실패: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. JWT 토큰 생성 테스트
    print("\n5. JWT 토큰 생성 테스트:")
    try:
        import jwt
        import uuid
        import time
        
        payload = {
            'access_key': api_key,
            'nonce': str(uuid.uuid4()),
            'timestamp': round(time.time() * 1000)
        }
        
        jwt_token = jwt.encode(payload, secret_key, algorithm='HS256')
        print(f"   ✅ JWT 토큰 생성 성공: {jwt_token[:50]}...")
        
    except Exception as e:
        print(f"   ❌ JWT 토큰 생성 실패: {e}")

if __name__ == "__main__":
    test_account_info()
