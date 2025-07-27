-- TimescaleDB 확장 활성화
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 시계열 주가 데이터
CREATE TABLE IF NOT EXISTS market_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    open DECIMAL(12,2),
    high DECIMAL(12,2),
    low DECIMAL(12,2),
    close DECIMAL(12,2),
    volume BIGINT,
    interval_type VARCHAR(5), -- '1m', '5m', '1d'
    PRIMARY KEY (time, symbol, interval_type)
);

-- TimescaleDB 하이퍼테이블 생성
SELECT create_hypertable('market_data', 'time', if_not_exists => TRUE);

-- 거래 기록
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(4) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL,
    price DECIMAL(12,2) NOT NULL,
    commission DECIMAL(10,2),
    strategy_name VARCHAR(100),
    order_type VARCHAR(20),
    status VARCHAR(20) CHECK (status IN ('FILLED', 'PARTIAL', 'CANCELLED')),
    profit_loss DECIMAL(12,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 포지션 정보
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    average_price DECIMAL(12,2),
    current_price DECIMAL(12,2),
    unrealized_pnl DECIMAL(12,2),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol)
);

-- 전략 성과
CREATE TABLE IF NOT EXISTS strategy_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    total_return DECIMAL(8,4),
    trades_count INTEGER,
    win_rate DECIMAL(5,2),
    max_drawdown DECIMAL(8,4),
    sharpe_ratio DECIMAL(6,3),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(strategy_name, date)
);

-- 종목 메타데이터
CREATE TABLE IF NOT EXISTS stocks_metadata (
    symbol VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    sector VARCHAR(50),
    market VARCHAR(20), -- 'KOSPI', 'KOSDAQ'
    market_cap BIGINT,
    shares_outstanding BIGINT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 리스크 지표
CREATE TABLE IF NOT EXISTS risk_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    portfolio_value DECIMAL(15,2),
    daily_pnl DECIMAL(12,2),
    var_95 DECIMAL(12,2), -- Value at Risk
    max_drawdown DECIMAL(8,4),
    sharpe_ratio DECIMAL(6,3),
    beta DECIMAL(6,3),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 시스템 로그
CREATE TABLE IF NOT EXISTS system_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    level VARCHAR(10) CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    component VARCHAR(50),
    message TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스 생성
CREATE INDEX idx_market_data_symbol ON market_data(symbol, time DESC);
CREATE INDEX idx_trades_symbol ON trades(symbol, timestamp DESC);
CREATE INDEX idx_trades_strategy ON trades(strategy_name, timestamp DESC);
CREATE INDEX idx_system_logs_level ON system_logs(level, timestamp DESC);
CREATE INDEX idx_system_logs_component ON system_logs(component, timestamp DESC);

-- 압축 정책 설정 (7일 이상 된 데이터 압축)
ALTER TABLE market_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol,interval_type'
);

SELECT add_compression_policy('market_data', INTERVAL '7 days');

-- 데이터 보존 정책 (1년 이상 된 데이터 삭제)
SELECT add_retention_policy('market_data', INTERVAL '1 year');
SELECT add_retention_policy('system_logs', INTERVAL '30 days');