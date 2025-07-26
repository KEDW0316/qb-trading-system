import time
import json
import logging
from datetime import datetime, timedelta
import asyncio
import os
from pathlib import Path
import sqlite3
from collections import deque

class APIMonitor:
    def __init__(self, db_path="logs/api_monitor.db", max_memory_logs=1000):
        self.logger = logging.getLogger("APIMonitor")
        self.db_path = Path(db_path)
        self.memory_logs = deque(maxlen=max_memory_logs)  # 최근 로그 메모리 캐시
        self.daily_stats = {}  # 일일 통계
        self.endpoint_stats = {}  # 엔드포인트별 통계
        self.error_counts = {}  # 오류 카운트
        
        # 로그 디렉토리 생성
        os.makedirs(self.db_path.parent, exist_ok=True)
        
        # DB 초기화
        self._init_db()
        
        # 통계 로딩
        self._load_stats()
    
    def _init_db(self):
        """SQLite DB 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # API 요청 로그 테이블
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            method TEXT,
            endpoint TEXT,
            tr_id TEXT,
            status_code INTEGER,
            response_time REAL,
            success INTEGER,
            error_message TEXT,
            request_data TEXT,
            response_data TEXT
        )
        """)
        
        # 일일 통계 테이블
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY,
            total_requests INTEGER,
            successful_requests INTEGER,
            failed_requests INTEGER,
            avg_response_time REAL
        )
        """)
        
        # 엔드포인트 통계 테이블
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS endpoint_stats (
            endpoint TEXT PRIMARY KEY,
            total_requests INTEGER,
            successful_requests INTEGER,
            failed_requests INTEGER,
            avg_response_time REAL,
            last_used TEXT
        )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_stats(self):
        """DB에서 통계 로드"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 오늘 날짜
            today = datetime.now().strftime("%Y-%m-%d")
            
            # 일일 통계 로드
            cursor.execute("SELECT * FROM daily_stats WHERE date = ?", (today,))
            row = cursor.fetchone()
            if row:
                self.daily_stats = {
                    "total_requests": row[1],
                    "successful_requests": row[2],
                    "failed_requests": row[3],
                    "avg_response_time": row[4]
                }
            else:
                self.daily_stats = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "avg_response_time": 0.0
                }
            
            # 엔드포인트 통계 로드
            cursor.execute("SELECT * FROM endpoint_stats")
            rows = cursor.fetchall()
            for row in rows:
                self.endpoint_stats[row[0]] = {
                    "total_requests": row[1],
                    "successful_requests": row[2],
                    "failed_requests": row[3],
                    "avg_response_time": row[4],
                    "last_used": row[5]
                }
            
            conn.close()
        except Exception as e:
            self.logger.error(f"Failed to load stats: {str(e)}")
    
    def _save_stats(self):
        """통계 DB에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 오늘 날짜
            today = datetime.now().strftime("%Y-%m-%d")
            
            # 일일 통계 저장
            cursor.execute("""
            INSERT OR REPLACE INTO daily_stats 
            (date, total_requests, successful_requests, failed_requests, avg_response_time)
            VALUES (?, ?, ?, ?, ?)
            """, (
                today,
                self.daily_stats["total_requests"],
                self.daily_stats["successful_requests"],
                self.daily_stats["failed_requests"],
                self.daily_stats["avg_response_time"]
            ))
            
            # 엔드포인트 통계 저장
            for endpoint, stats in self.endpoint_stats.items():
                cursor.execute("""
                INSERT OR REPLACE INTO endpoint_stats
                (endpoint, total_requests, successful_requests, failed_requests, avg_response_time, last_used)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    endpoint,
                    stats["total_requests"],
                    stats["successful_requests"],
                    stats["failed_requests"],
                    stats["avg_response_time"],
                    stats["last_used"]
                ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Failed to save stats: {str(e)}")
    
    async def log_request(self, method, endpoint, tr_id=None, request_data=None, response_data=None, 
                         status_code=None, response_time=None, success=True, error_message=None):
        """API 요청 로깅"""
        timestamp = datetime.now().isoformat()
        
        # 로그 데이터 생성
        log_data = {
            "timestamp": timestamp,
            "method": method,
            "endpoint": endpoint,
            "tr_id": tr_id,
            "status_code": status_code,
            "response_time": response_time,
            "success": success,
            "error_message": error_message,
            "request_data": json.dumps(request_data) if request_data else None,
            "response_data": json.dumps(response_data) if response_data else None
        }
        
        # 메모리 캐시에 추가
        self.memory_logs.append(log_data)
        
        # 통계 업데이트
        self._update_stats(log_data)
        
        # DB에 로그 저장 (비동기로 처리)
        asyncio.create_task(self._save_log_to_db(log_data))
    
    def _update_stats(self, log_data):
        """통계 업데이트"""
        # 일일 통계 업데이트
        self.daily_stats["total_requests"] += 1
        if log_data["success"]:
            self.daily_stats["successful_requests"] += 1
        else:
            self.daily_stats["failed_requests"] += 1
        
        # 평균 응답 시간 업데이트
        if log_data["response_time"] is not None:
            current_avg = self.daily_stats["avg_response_time"]
            current_total = self.daily_stats["total_requests"]
            self.daily_stats["avg_response_time"] = (
                (current_avg * (current_total - 1) + log_data["response_time"]) / current_total
            )
        
        # 엔드포인트 통계 업데이트
        endpoint = log_data["endpoint"]
        if endpoint not in self.endpoint_stats:
            self.endpoint_stats[endpoint] = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "avg_response_time": 0.0,
                "last_used": log_data["timestamp"]
            }
        
        self.endpoint_stats[endpoint]["total_requests"] += 1
        if log_data["success"]:
            self.endpoint_stats[endpoint]["successful_requests"] += 1
        else:
            self.endpoint_stats[endpoint]["failed_requests"] += 1
        
        # 평균 응답 시간 업데이트
        if log_data["response_time"] is not None:
            current_avg = self.endpoint_stats[endpoint]["avg_response_time"]
            current_total = self.endpoint_stats[endpoint]["total_requests"]
            self.endpoint_stats[endpoint]["avg_response_time"] = (
                (current_avg * (current_total - 1) + log_data["response_time"]) / current_total
            )
        
        self.endpoint_stats[endpoint]["last_used"] = log_data["timestamp"]
        
        # 오류 카운트 업데이트
        if not log_data["success"] and log_data["error_message"]:
            error_key = log_data["error_message"][:100]  # 오류 메시지 앞부분만 키로 사용
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # 주기적으로 통계 저장
        if self.daily_stats["total_requests"] % 100 == 0:
            self._save_stats()
    
    async def _save_log_to_db(self, log_data):
        """로그를 DB에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
            INSERT INTO api_logs 
            (timestamp, method, endpoint, tr_id, status_code, response_time, success, error_message, request_data, response_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_data["timestamp"],
                log_data["method"],
                log_data["endpoint"],
                log_data["tr_id"],
                log_data["status_code"],
                log_data["response_time"],
                1 if log_data["success"] else 0,
                log_data["error_message"],
                log_data["request_data"],
                log_data["response_data"]
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Failed to save log to DB: {str(e)}")
    
    def get_recent_logs(self, limit=50):
        """최근 로그 조회"""
        return list(self.memory_logs)[-limit:]
    
    def get_daily_stats(self):
        """일일 통계 조회"""
        return self.daily_stats
    
    def get_endpoint_stats(self):
        """엔드포인트별 통계 조회"""
        return self.endpoint_stats
    
    def get_error_stats(self):
        """오류 통계 조회"""
        return self.error_counts
    
    def get_logs_by_endpoint(self, endpoint, limit=50):
        """특정 엔드포인트의 로그 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT * FROM api_logs 
        WHERE endpoint = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
        """, (endpoint, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return rows
    
    def get_logs_by_timerange(self, start_time, end_time=None, limit=100):
        """특정 시간 범위의 로그 조회"""
        if end_time is None:
            end_time = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT * FROM api_logs 
        WHERE timestamp BETWEEN ? AND ? 
        ORDER BY timestamp DESC 
        LIMIT ?
        """, (start_time, end_time, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return rows
    
    def get_error_logs(self, limit=50):
        """오류 로그 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT * FROM api_logs 
        WHERE success = 0 
        ORDER BY timestamp DESC 
        LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return rows