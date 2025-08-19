#!/bin/bash
# 장 마감 후 전체 시스템 테스트 스크립트

echo "🕐 장 마감 시간 통합 테스트 시작..."
echo "=================================="

# Redis 확인
echo "📊 Redis 상태 확인..."
redis-cli ping > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Redis 연결 성공"
else
    echo "❌ Redis 연결 실패 - Redis를 먼저 시작하세요"
    exit 1
fi

# PostgreSQL 확인 (선택사항)
echo "🗄️ PostgreSQL 상태 확인..."
pg_isready > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ PostgreSQL 연결 성공"
else
    echo "⚠️ PostgreSQL 미연결 - 일부 기능 제한"
fi

echo ""
echo "🧪 테스트 옵션:"
echo "1) 기본 Mock 테스트 (5초)"
echo "2) 전체 파이프라인 테스트 (30초)"
echo "3) 장시간 안정성 테스트 (5분)"
echo "4) 사용자 정의 시간"

read -p "선택하세요 (1-4): " choice

case $choice in
    1)
        echo "▶️ 기본 Mock 테스트 실행 중..."
        python tests/test_mock_kis_flow.py
        ;;
    2)
        echo "▶️ 전체 파이프라인 테스트 실행 중..."
        python tests/enhanced_mock_test.py
        ;;
    3)
        echo "▶️ 장시간 안정성 테스트 실행 중 (5분)..."
        python tests/enhanced_mock_test.py --duration 300
        ;;
    4)
        read -p "테스트 시간(초): " duration
        echo "▶️ ${duration}초 테스트 실행 중..."
        python tests/enhanced_mock_test.py --duration $duration
        ;;
    *)
        echo "잘못된 선택입니다."
        exit 1
        ;;
esac

echo ""
echo "✅ 테스트 완료!"
echo "📄 로그 파일:"
echo "   - mock_test.log"
echo "   - mock_orders.json (주문 기록)"

# 결과 요약 표시
if [ -f mock_orders.json ]; then
    order_count=$(grep -c "timestamp" mock_orders.json 2>/dev/null || echo "0")
    echo ""
    echo "📊 테스트 요약:"
    echo "   - Mock 주문 생성: ${order_count}건"
fi