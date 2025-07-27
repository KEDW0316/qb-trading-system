#!/bin/bash

# QB Trading System - 빠른 시작 스크립트
# 내일 장 개장 시 실행할 스크립트

echo "🚀 QB Trading System 빠른 시작"
echo "================================"

# 1. 환경 확인
echo "📋 1. 환경 확인 중..."

# Python 환경 확인
PYTHON_PATH="/Users/dongwon/anaconda3/envs/qb/bin/python"
if [ ! -f "$PYTHON_PATH" ]; then
    echo "❌ Python 환경을 찾을 수 없습니다: $PYTHON_PATH"
    exit 1
fi
echo "✅ Python 환경: $PYTHON_PATH"

# 환경 변수 파일 확인
if [ ! -f ".env.development" ]; then
    echo "❌ .env.development 파일이 없습니다"
    exit 1
fi
echo "✅ 환경 변수 파일 확인"

# Redis 실행 확인
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️ Redis가 실행되지 않았습니다. 시작 중..."
    if command -v brew > /dev/null; then
        brew services start redis
    else
        sudo systemctl start redis
    fi
    sleep 3
fi

if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis 실행 중"
else
    echo "❌ Redis 연결 실패"
    exit 1
fi

# PostgreSQL 확인
if ! pg_isready > /dev/null 2>&1; then
    echo "⚠️ PostgreSQL이 실행되지 않았습니다. 시작 중..."
    if command -v brew > /dev/null; then
        brew services start postgresql
    else
        sudo systemctl start postgresql
    fi
    sleep 5
fi

if pg_isready > /dev/null 2>&1; then
    echo "✅ PostgreSQL 실행 중"
else
    echo "❌ PostgreSQL 연결 실패"
    exit 1
fi

# 2. 사전 테스트 실행
echo ""
echo "📋 2. 사전 오프라인 테스트..."
echo "   (실제 거래 전 시스템 점검)"

$PYTHON_PATH run_offline_test.py
if [ $? -ne 0 ]; then
    echo "❌ 오프라인 테스트 실패. 실제 거래를 중단합니다."
    exit 1
fi

echo "✅ 오프라인 테스트 통과"

# 3. 실제 거래 시작 메뉴
echo ""
echo "🎯 3. 실제 거래 시작 옵션"
echo "================================"
echo "1) 소액 테스트 (삼성전자 1주, 최대 10만원)"
echo "2) 모의 거래 모드 (실제 주문 없음)"
echo "3) 커스텀 설정"
echo "4) 취소"
echo ""

read -p "선택하세요 (1-4): " choice

case $choice in
    1)
        echo "💰 소액 실제 거래 시작..."
        $PYTHON_PATH run_live_trading.py --symbol 005930 --max-amount 100000 --stop-loss 3.0
        ;;
    2)
        echo "🎭 모의 거래 모드 시작..."
        $PYTHON_PATH run_live_trading.py --symbol 005930 --max-amount 100000 --dry-run
        ;;
    3)
        echo ""
        read -p "종목 코드 (기본: 005930): " symbol
        symbol=${symbol:-005930}
        read -p "최대 거래 금액 (기본: 100000): " amount
        amount=${amount:-100000}
        read -p "손절매 비율 % (기본: 3.0): " stoploss
        stoploss=${stoploss:-3.0}
        
        echo "🎯 커스텀 설정으로 시작..."
        $PYTHON_PATH run_live_trading.py --symbol $symbol --max-amount $amount --stop-loss $stoploss
        ;;
    4)
        echo "❌ 거래가 취소되었습니다."
        exit 0
        ;;
    *)
        echo "❌ 잘못된 선택입니다."
        exit 1
        ;;
esac

echo ""
echo "🎯 거래 완료! 로그 파일을 확인하세요:"
echo "   - logs/live_trading_report_*.json"
echo "   - logs/api_monitor.db"