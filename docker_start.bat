@echo off
REM QB Trading System Docker 실행 스크립트 (Windows)

echo ===================================================
echo    QB Trading System Docker 시작 스크립트
echo ===================================================
echo.

REM 환경 변수 확인
if not exist ".env" (
    echo [ERROR] .env 파일이 없습니다!
    echo .env.example을 복사하여 .env 파일을 생성하고 실제 API 키를 입력하세요.
    pause
    exit /b 1
)

REM Docker 실행 확인
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker가 실행되고 있지 않습니다!
    echo Docker Desktop을 실행하고 다시 시도하세요.
    pause
    exit /b 1
)

echo [OK] Docker 환경 확인 완료
echo.

REM 이전 컨테이너 정리
echo 이전 컨테이너 정리 중...
docker-compose down

REM 이미지 빌드
echo.
echo Docker 이미지 빌드 중... (처음 실행 시 5-10분 소요)
docker-compose build

REM 시스템 시작
echo.
echo 시스템 시작 중...
docker-compose up -d

REM 상태 확인
echo.
echo 시스템 초기화 대기 중...
timeout /t 10 /nobreak >nul

echo.
echo 시스템 상태:
docker-compose ps

echo.
echo ===================================================
echo    QB Trading System이 시작되었습니다!
echo ===================================================
echo.
echo 유용한 명령어:
echo   - 로그 확인: docker-compose logs -f qb_trading
echo   - 시스템 중지: docker-compose down
echo   - 상태 확인: docker-compose ps
echo.
echo 팁: 새 명령 프롬프트에서 'docker-compose logs -f qb_trading'을
echo     실행하여 실시간 로그를 확인하세요.
echo.
pause