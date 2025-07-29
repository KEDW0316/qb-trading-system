# QB Trading System Docker Image
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필수 도구 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libpq-dev \
    curl \
    git \
    redis-tools \
    postgresql-client \
    wget \
    && rm -rf /var/lib/apt/lists/*

# TA-Lib C 라이브러리 설치 (Python ta-lib 패키지의 의존성)
RUN cd /tmp && \
    wget https://github.com/TA-Lib/ta-lib/releases/download/v0.4.0/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd / && \
    rm -rf /tmp/ta-lib*

# UV 설치 (Python 패키지 매니저)
RUN pip install uv

# 프로젝트 파일 복사 (의존성 먼저 복사하여 캐시 최적화)
COPY pyproject.toml uv.lock ./

# UV를 사용해서 의존성 설치
RUN uv sync --frozen

# 나머지 프로젝트 파일 복사
COPY . /app/

# 로그 디렉토리 생성
RUN mkdir -p /app/logs

# 환경 변수 설정
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 실행 명령어 (기본값 설정, docker run에서 override 가능)
CMD ["uv", "run", "python", "run_live_trading.py", "--symbol", "005930", "--max-amount", "100000", "--stop-loss", "3.0"]