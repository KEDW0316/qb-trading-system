# 내일 실제 거래 테스트 체크리스트 ✅

## 🌅 아침 8:30 - 사전 준비

### 1. 환경 변수 설정 확인
```bash
# .env.development 파일 열기
cat .env.development

# 다음 항목들이 실제 값으로 설정되어 있는지 확인:
KIS_APP_KEY=실제앱키 (your_app_key_here가 아닌)
KIS_APP_SECRET=실제시크릿키 (your_app_secret_here가 아닌) 
KIS_ACCOUNT_NO=실제계좌번호 (your_account_here가 아닌)
```

### 2. 계좌 상태 확인
- [ ] KIS 계좌 로그인 확인
- [ ] 거래 가능 잔고 확인 (최소 10만원)
- [ ] 모의투자 vs 실제투자 모드 확인
- [ ] API 키 활성화 상태 확인

### 3. 시스템 인프라 실행
```bash
# Redis 시작
brew services start redis  # macOS
# 또는
sudo systemctl start redis  # Linux

# PostgreSQL 시작  
brew services start postgresql  # macOS
# 또는
sudo systemctl start postgresql  # Linux

# 연결 확인
redis-cli ping  # PONG 응답 확인
pg_isready     # accepting connections 확인
```

## 🚀 09:00 - 장 개장, 거래 시작

### 빠른 시작 (권장)
```bash
cd /Users/dongwon/project/QB
./quick_start.sh
```

### 수동 실행
```bash
cd /Users/dongwon/project/QB

# 1. 사전 오프라인 테스트
/Users/dongwon/anaconda3/envs/qb/bin/python run_offline_test.py

# 2. 실제 거래 시작 (소액)
/Users/dongwon/anaconda3/envs/qb/bin/python run_live_trading.py \
    --symbol 005930 \
    --max-amount 100000 \
    --stop-loss 3.0
```

### 모의 거래 모드 (실제 주문 없음)
```bash
/Users/dongwon/anaconda3/envs/qb/bin/python run_live_trading.py \
    --symbol 005930 \
    --max-amount 100000 \
    --dry-run
```

## 📊 거래 중 모니터링

### 실시간 확인사항
- [ ] 시장 데이터 수신 중 (30초마다 상태 출력)
- [ ] 거래 신호 생성 확인
- [ ] 리스크 알림 모니터링
- [ ] 주문 체결 확인

### 로그 파일 확인
```bash
# 실시간 로그 모니터링
tail -f logs/live_trading_report_*.json

# API 모니터링
ls -la logs/api_monitor.db
```

## 🛑 비상 상황 대응

### 시스템 중단 방법
```bash
# Ctrl+C로 안전한 종료
# 또는 프로세스 종료
pkill -f run_live_trading.py
```

### 수동 거래 전환
1. 시스템 중단
2. KIS 웹/앱으로 직접 거래
3. 열린 포지션 정리

## 📋 15:30 - 장 마감 후

### 결과 분석
```bash
# 최종 리포트 확인
cat logs/live_trading_report_$(date +%Y%m%d)_*.json

# 거래 기록 확인
grep "체결완료" logs/live_trading_report_*.json
```

### 다음 단계 계획
- [ ] 거래 결과 분석
- [ ] 시스템 성능 평가
- [ ] 개선점 도출
- [ ] 내일 거래 계획 수립

## 🎯 성공 기준

### 최소 목표 (반드시 달성)
- [ ] 시스템 무중단 운영 (9:00-15:30)
- [ ] 실시간 데이터 수신 정상
- [ ] 1회 이상 주문 체결 성공
- [ ] 리스크 관리 정상 작동

### 이상 목표 (달성 시 확장 고려)
- [ ] 주문 성공률 95% 이상
- [ ] API 응답시간 1초 이하
- [ ] 수익 실현 (손실도 학습!)
- [ ] 메모리 사용량 1GB 이하

## ⚠️ 주의사항

1. **소액으로만 시작**: 처음엔 반드시 10만원 이하
2. **손절매 준수**: 3% 손실 시 즉시 중단  
3. **상시 모니터링**: 자리를 비우지 말 것
4. **수동 개입 준비**: 문제 시 즉시 수동 거래로 전환
5. **로그 보관**: 모든 거래 기록 저장

---

**🍀 행운을 빕니다! 안전하고 성공적인 첫 실제 거래가 되길 바랍니다! 🚀**