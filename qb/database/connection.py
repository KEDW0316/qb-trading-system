"""
Database connection management for QB Trading System
PostgreSQL/TimescaleDB 연결 풀 관리 및 세션 관리
"""

import os
import logging
from contextlib import contextmanager
from typing import Optional, Generator, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

from .models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """데이터베이스 연결 관리 클래스"""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        DatabaseManager 초기화
        
        Args:
            database_url: PostgreSQL 연결 URL. None이면 환경변수에서 읽음
        """
        self.database_url = database_url or os.getenv(
            'DATABASE_URL', 
            'postgresql://qb_user:qb_pass@localhost:5432/qb_trading_dev'
        )
        self.engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None
        self.logger = logging.getLogger(__name__)
        
    def initialize(self) -> bool:
        """데이터베이스 연결 및 세션 팩토리 초기화"""
        try:
            # SQLAlchemy 엔진 생성 (연결 풀 설정)
            self.engine = create_engine(
                self.database_url,
                poolclass=QueuePool,
                pool_size=5,  # 기본 연결 수
                max_overflow=10,  # 최대 추가 연결 수
                pool_pre_ping=True,  # 연결 전 ping 테스트
                pool_recycle=3600,  # 1시간마다 연결 재생성
                echo=False,  # SQL 쿼리 로깅 (개발시에만 True)
            )
            
            # 세션 팩토리 생성
            self.session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
            
            # 연결 테스트
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                conn.commit()
                
            self.logger.info("Database connection initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database connection: {e}")
            return False
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        데이터베이스 세션 컨텍스트 매니저
        
        Yields:
            Session: SQLAlchemy 세션 객체
        """
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
            
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_engine(self) -> Engine:
        """SQLAlchemy 엔진 반환"""
        if not self.engine:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.engine
    
    def ping(self) -> bool:
        """데이터베이스 연결 상태 확인"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            self.logger.error(f"Database ping failed: {e}")
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """데이터베이스 연결 정보 반환"""
        if not self.engine:
            return {"status": "not_initialized"}
            
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT 
                        version() as version,
                        current_database() as database,
                        current_user as user,
                        inet_server_addr() as host,
                        inet_server_port() as port
                """))
                info = result.fetchone()
                
                # TimescaleDB 확장 확인
                timescale_result = conn.execute(text("""
                    SELECT default_version, installed_version 
                    FROM pg_available_extensions 
                    WHERE name = 'timescaledb'
                """))
                timescale_info = timescale_result.fetchone()
                
                return {
                    "status": "connected",
                    "version": info.version if info else "unknown",
                    "database": info.database if info else "unknown", 
                    "user": info.user if info else "unknown",
                    "host": info.host if info else "unknown",
                    "port": info.port if info else "unknown",
                    "timescaledb": {
                        "available": timescale_info is not None,
                        "version": timescale_info.installed_version if timescale_info else None
                    },
                    "pool_size": self.engine.pool.size(),
                    "checked_in": self.engine.pool.checkedin(),
                    "checked_out": self.engine.pool.checkedout()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get connection info: {e}")
            return {"status": "error", "error": str(e)}
    
    def create_tables(self) -> bool:
        """테이블 생성 (개발용)"""
        try:
            if not self.engine:
                raise RuntimeError("Database not initialized")
                
            Base.metadata.create_all(self.engine)
            self.logger.info("Database tables created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create tables: {e}")
            return False
    
    def get_table_info(self) -> Dict[str, Any]:
        """테이블 정보 조회"""
        try:
            with self.engine.connect() as conn:
                # 일반 테이블 정보
                tables_result = conn.execute(text("""
                    SELECT schemaname, tablename, tableowner 
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    ORDER BY tablename
                """))
                tables = [{"schemaname": row[0], "tablename": row[1], "tableowner": row[2]} 
                         for row in tables_result]
                
                # TimescaleDB 하이퍼테이블 정보
                hypertables_result = conn.execute(text("""
                    SELECT hypertable_name, num_dimensions, num_chunks, compression_enabled
                    FROM timescaledb_information.hypertables
                    WHERE hypertable_schema = 'public'
                """))
                hypertables = [{"hypertable_name": row[0], "num_dimensions": row[1], 
                              "num_chunks": row[2], "compression_enabled": row[3]} 
                             for row in hypertables_result]
                
                return {
                    "tables": tables,
                    "hypertables": hypertables,
                    "total_tables": len(tables)
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get table info: {e}")
            return {"error": str(e)}
    
    def close(self):
        """데이터베이스 연결 종료"""
        if self.engine:
            self.engine.dispose()
            self.logger.info("Database connection closed")


# 전역 데이터베이스 매니저 인스턴스
db_manager = DatabaseManager()


def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency로 사용할 데이터베이스 세션
    
    Yields:
        Session: SQLAlchemy 세션 객체
    """
    with db_manager.get_session() as session:
        yield session


def init_database() -> bool:
    """데이터베이스 초기화 함수"""
    return db_manager.initialize()


def get_database_info() -> Dict[str, Any]:
    """데이터베이스 정보 조회 함수"""
    return db_manager.get_connection_info()