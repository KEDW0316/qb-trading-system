"""
거래 모드 관리 모듈
Trading Mode Manager Module

모의투자와 실전투자 모드 간 안전한 전환 기능 및 모드별 설정 관리
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class TradingModeManager:
    """거래 모드 관리 클래스"""
    
    def __init__(self, config_path: str = "config/trading_mode.json"):
        """
        거래 모드 관리자 초기화
        
        Args:
            config_path: 설정 파일 경로
        """
        self.logger = logging.getLogger(__name__)
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        # 모드 전환 로그 기록
        self.logger.info(f"TradingModeManager initialized with mode: {self.get_current_mode()}")
    
    def _load_config(self) -> Dict[str, Any]:
        """
        설정 파일 로드
        
        Returns:
            설정 딕셔너리
        """
        if not self.config_path.exists():
            # 기본 설정 생성
            default_config = {
                "mode": "paper",  # 기본값은 모의투자
                "last_updated": datetime.now().isoformat(),
                "modes": {
                    "paper": {
                        "name": "모의투자",
                        "base_url": "https://openapivts.koreainvestment.com:29443",
                        "tr_id_prefix": "V",
                        "description": "가상 계좌를 이용한 모의투자 환경"
                    },
                    "prod": {
                        "name": "실전투자", 
                        "base_url": "https://openapi.koreainvestment.com:9443",
                        "tr_id_prefix": "T",
                        "description": "실제 계좌를 이용한 실전투자 환경"
                    }
                },
                "safety_checks": {
                    "confirm_real_mode": True,           # 실전 모드 전환 시 확인 프롬프트
                    "max_order_amount": 1000000,         # 실전 모드 최대 주문 금액 (원)
                    "max_daily_orders": 20,              # 실전 모드 일일 최대 주문 수
                    "require_confirmation_keywords": True,  # 확인 키워드 요구
                    "confirmation_keyword": "CONFIRM",    # 확인 키워드
                    "enable_order_limits": True           # 주문 제한 활성화
                },
                "audit_log": {
                    "enable_logging": True,              # 감사 로그 활성화
                    "log_file": "logs/trading_mode_audit.log",  # 로그 파일 경로
                    "max_log_entries": 1000              # 최대 로그 항목 수
                }
            }
            
            # 설정 디렉토리 생성
            os.makedirs(self.config_path.parent, exist_ok=True)
            
            # 설정 파일 저장
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"Created default trading mode config at {self.config_path}")
            return default_config
        
        # 기존 설정 파일 로드
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.logger.debug(f"Loaded trading mode config from {self.config_path}")
                return config
        except Exception as e:
            self.logger.error(f"Failed to load config: {str(e)}")
            # 오류 시 기본 설정 반환
            return {"mode": "paper", "modes": {}}
    
    def save_config(self) -> bool:
        """
        설정 파일 저장
        
        Returns:
            저장 성공 여부
        """
        try:
            # 마지막 업데이트 시간 기록
            self.config["last_updated"] = datetime.now().isoformat()
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Saved trading mode config to {self.config_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save config: {str(e)}")
            return False
    
    def get_current_mode(self) -> str:
        """
        현재 거래 모드 반환
        
        Returns:
            현재 모드 ("paper" 또는 "prod")
        """
        return self.config.get("mode", "paper")
    
    def get_mode_name(self, mode: Optional[str] = None) -> str:
        """
        모드의 한글 이름 반환
        
        Args:
            mode: 모드 ("paper" 또는 "prod"), None일 경우 현재 모드
            
        Returns:
            모드의 한글 이름
        """
        if mode is None:
            mode = self.get_current_mode()
        
        return self.config.get("modes", {}).get(mode, {}).get("name", mode)
    
    def is_paper_trading(self) -> bool:
        """
        모의투자 모드인지 확인
        
        Returns:
            모의투자 모드 여부
        """
        return self.get_current_mode() == "paper"
    
    def is_prod_trading(self) -> bool:
        """
        실전투자 모드인지 확인
        
        Returns:
            실전투자 모드 여부
        """
        return self.get_current_mode() == "prod"
    
    def switch_to_paper_mode(self) -> bool:
        """
        모의투자 모드로 전환
        
        Returns:
            전환 성공 여부
        """
        old_mode = self.get_current_mode()
        self.config["mode"] = "paper"
        success = self.save_config()
        
        if success:
            self.logger.info(f"Switched from {old_mode} to PAPER trading mode")
            self._log_mode_change(old_mode, "paper", "Manual switch to paper mode")
        else:
            self.logger.error("Failed to switch to paper mode")
        
        return success
    
    def switch_to_prod_mode(self, force: bool = False, reason: str = "Manual switch") -> bool:
        """
        실전투자 모드로 전환
        
        Args:
            force: 확인 프롬프트 생략 여부
            reason: 전환 사유
            
        Returns:
            전환 성공 여부
        """
        old_mode = self.get_current_mode()
        safety_settings = self.get_safety_settings()
        
        # 안전 확인 절차
        if not force and safety_settings.get("confirm_real_mode", True):
            if safety_settings.get("require_confirmation_keywords", True):
                keyword = safety_settings.get("confirmation_keyword", "CONFIRM")
                
                print(f"\n{'='*60}")
                print("⚠️  경고: 실전투자 모드로 전환하려고 합니다!")
                print("⚠️  WARNING: You are switching to REAL trading mode!")
                print(f"{'='*60}")
                print("실전투자 모드에서는 실제 자금으로 거래가 이루어집니다.")
                print("Real money will be used for trading in production mode.")
                print(f"확인하려면 '{keyword}'를 정확히 입력하세요.")
                print(f"Type '{keyword}' to confirm:")
                print(f"{'='*60}")
                
                confirmation = input("확인: ")
                if confirmation != keyword:
                    self.logger.warning("Real mode switch cancelled - incorrect confirmation")
                    print("실전투자 모드 전환이 취소되었습니다.")
                    return False
        
        self.config["mode"] = "prod"
        success = self.save_config()
        
        if success:
            self.logger.warning(f"Switched from {old_mode} to REAL trading mode - {reason}")
            self._log_mode_change(old_mode, "prod", reason)
        else:
            self.logger.error("Failed to switch to real mode")
        
        return success
    
    def get_base_url(self, mode: Optional[str] = None) -> Optional[str]:
        """
        현재 모드에 맞는 base_url 반환
        
        Args:
            mode: 모드 ("paper" 또는 "prod"), None일 경우 현재 모드
            
        Returns:
            base_url
        """
        if mode is None:
            mode = self.get_current_mode()
        
        return self.config.get("modes", {}).get(mode, {}).get("base_url")
    
    def get_tr_id_prefix(self, mode: Optional[str] = None) -> Optional[str]:
        """
        현재 모드에 맞는 TR ID 접두사 반환
        
        Args:
            mode: 모드 ("paper" 또는 "prod"), None일 경우 현재 모드
            
        Returns:
            TR ID 접두사
        """
        if mode is None:
            mode = self.get_current_mode()
        
        return self.config.get("modes", {}).get(mode, {}).get("tr_id_prefix")
    
    def get_safety_settings(self) -> Dict[str, Any]:
        """
        안전 설정 반환
        
        Returns:
            안전 설정 딕셔너리
        """
        return self.config.get("safety_checks", {})
    
    def get_mode_config(self, mode: Optional[str] = None) -> Dict[str, Any]:
        """
        특정 모드의 설정 반환
        
        Args:
            mode: 모드 ("paper" 또는 "prod"), None일 경우 현재 모드
            
        Returns:
            모드 설정 딕셔너리
        """
        if mode is None:
            mode = self.get_current_mode()
        
        return self.config.get("modes", {}).get(mode, {})
    
    def _log_mode_change(self, from_mode: str, to_mode: str, reason: str):
        """
        모드 변경 감사 로그 기록
        
        Args:
            from_mode: 이전 모드
            to_mode: 변경된 모드  
            reason: 변경 사유
        """
        audit_config = self.config.get("audit_log", {})
        
        if not audit_config.get("enable_logging", True):
            return
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "from_mode": from_mode,
            "to_mode": to_mode,
            "reason": reason,
            "user": os.getenv("USER", "unknown")
        }
        
        # 로그 파일 경로
        log_file = Path(audit_config.get("log_file", "logs/trading_mode_audit.log"))
        
        try:
            # 로그 디렉토리 생성
            os.makedirs(log_file.parent, exist_ok=True)
            
            # 로그 항목 추가
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                
        except Exception as e:
            self.logger.error(f"Failed to write audit log: {str(e)}")
    
    def get_audit_log(self, limit: int = 10) -> list:
        """
        감사 로그 조회
        
        Args:
            limit: 조회할 로그 항목 수
            
        Returns:
            로그 항목 리스트
        """
        audit_config = self.config.get("audit_log", {})
        log_file = Path(audit_config.get("log_file", "logs/trading_mode_audit.log"))
        
        if not log_file.exists():
            return []
        
        try:
            entries = []
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # 최근 항목부터 반환
            for line in reversed(lines[-limit:]):
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
                    
            return entries
            
        except Exception as e:
            self.logger.error(f"Failed to read audit log: {str(e)}")
            return []
    
    def __str__(self) -> str:
        """문자열 표현"""
        current_mode = self.get_current_mode()
        mode_name = self.get_mode_name(current_mode)
        return f"TradingModeManager(mode={current_mode}, name={mode_name})"
    
    def __repr__(self) -> str:
        """객체 표현"""
        return self.__str__()