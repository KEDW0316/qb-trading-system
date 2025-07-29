#!/bin/bash

# QB Trading System Docker 실행 스크립트

echo "🚀 QB Trading System Docker 시작 스크립트"
echo "========================================="

# 환경 변수 확인
if [ ! -f ".env" ]; then
    echo "❌ .env 파일이 없습니다!"
    echo "📝 .env.example을 복사하여 .env 파일을 생성하고 실제 API 키를 입력하세요."
    exit 1
fi

# API 키 설정 확인
if grep -q "your_app_key_here" .env; then
    echo "⚠️  경고: .env 파일에 기본 API 키가 설정되어 있습니다!"
    echo "실제 KIS API 키로 변경해주세요."
    read -p "계속하시겠습니까? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Docker 실행 확인
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker가 실행되고 있지 않습니다!"
    echo "Docker Desktop을 실행하고 다시 시도하세요."
    exit 1
fi

echo "✅ Docker 환경 확인 완료"

# 이전 컨테이너 정리
echo "🧹 이전 컨테이너 정리 중..."
docker-compose down

# 이미지 빌드
echo "🔨 Docker 이미지 빌드 중... (처음 실행 시 5-10분 소요)"
docker-compose build

# 시스템 시작
echo "🚀 시스템 시작 중..."
docker-compose up -d

# 상태 확인
echo "⏳ 시스템 초기화 대기 중..."
sleep 10

echo "📊 시스템 상태:"
docker-compose ps

echo ""
echo "✅ QB Trading System이 시작되었습니다!"
echo ""
echo "📌 유용한 명령어:"
echo "  - 로그 확인: docker-compose logs -f qb_trading"
echo "  - 시스템 중지: docker-compose down"
echo "  - 상태 확인: docker-compose ps"
echo ""
echo "💡 팁: 다른 터미널에서 'docker-compose logs -f qb_trading'을 실행하여 실시간 로그를 확인하세요."