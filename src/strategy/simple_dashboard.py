import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

class SimpleDashboard:
    """깔끔한 터미널 대시보드"""
    
    def __init__(self):
        self.screen_width = 100
        self.check_count = 0
        self.buy_signals = 0
        self.sell_signals = 0
        self.start_time = time.time()
        self.last_update = None
        
    def clear_screen(self):
        """화면 클리어 (Windows/Linux 호환)"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self, title: str = "자동매매 모니터링"):
        """헤더 출력"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n{'='*self.screen_width}")
        print(f"🚀 {title} - {current_time}")
        print(f"{'='*self.screen_width}")
    
    def print_market_summary(self, market_data: Dict[str, Any]):
        """시장 요약 정보"""
        print(f"\n📈 시장 현황")
        print(f"   현재가: {market_data.get('current_price', 0):,}원")
        print(f"   변동률: {market_data.get('change_rate', 0):+.2f}%")
        print(f"   거래량: {market_data.get('volume', 0):,}")
        print(f"   거래대금: {market_data.get('trade_value', 0):,}원")
    
    def print_conditions(self, conditions: Dict[str, bool]):
        """매수 조건 체크"""
        print(f"\n🔍 매수 조건 체크")
        for condition, status in conditions.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {condition}")
    
    def print_orders(self, orders: List[Dict[str, Any]]):
        """주문 현황"""
        if not orders:
            print(f"\n📋 주문 현황: 없음")
            return
            
        print(f"\n📋 주문 현황 ({len(orders)}개)")
        for order in orders:
            side_icon = "🟢" if order.get('side') == 'bid' else "🔴"
            print(f"   {side_icon} {order.get('side', 'unknown')} | {order.get('volume', 0)} | {order.get('price', 0):,}원 | {order.get('status', 'unknown')}")
    
    def print_statistics(self):
        """통계 정보"""
        elapsed_time = time.time() - self.start_time
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
        seconds = int(elapsed_time % 60)
        
        print(f"\n📊 통계")
        print(f"   모니터링 시간: {hours:02d}:{minutes:02d}:{seconds:02d}")
        print(f"   체크 횟수: {self.check_count}")
        print(f"   매수 신호: {self.buy_signals}회")
        print(f"   매도 신호: {self.sell_signals}회")
        print(f"   마지막 업데이트: {self.last_update or '없음'}")
    
    def print_volume_explosions(self, explosions: List[Dict[str, Any]]):
        """거래량 폭발 현황"""
        if not explosions:
            print(f"\n💥 거래량 폭발: 없음")
            return
            
        print(f"\n💥 거래량 폭발 ({len(explosions)}개)")
        for exp in explosions[-5:]:  # 최근 5개만 표시
            print(f"   {exp.get('market', 'unknown')}: {exp.get('multiplier', 0):.1f}배 ({exp.get('timestamp', 'unknown')})")
    
    def update_dashboard(self, data: Dict[str, Any]):
        """대시보드 전체 업데이트"""
        self.clear_screen()
        self.print_header()
        
        # 시장 현황
        if 'market' in data:
            self.print_market_summary(data['market'])
        
        # 매수 조건
        if 'conditions' in data:
            self.print_conditions(data['conditions'])
            
            # 매수 신호 체크
            if all(data['conditions'].values()):
                self.buy_signals += 1
                print(f"\n🚨 매수 신호 발생! (총 {self.buy_signals}회)")
        
        # 주문 현황
        if 'orders' in data:
            self.print_orders(data['orders'])
        
        # 거래량 폭발
        if 'explosions' in data:
            self.print_volume_explosions(data['explosions'])
        
        # 통계
        self.print_statistics()
        
        # 다음 체크 안내
        print(f"\n⏰ 다음 체크까지 5초...")
        
        self.check_count += 1
        self.last_update = datetime.now().strftime('%H:%M:%S')
    
    def print_simple_status(self, market: str, price: float, change_rate: float, 
                          volume: float, conditions: Dict[str, bool], 
                          volume_ratio: float = 0.0):
        """간단한 상태 출력 (한 줄)"""
        # 매수 조건 체크
        buy_signal = all(conditions.values())
        signal_icon = "🚨" if buy_signal else "⏳"
        
        # 변동률 색상 (간단한 텍스트)
        change_icon = "📈" if change_rate > 0 else "📉" if change_rate < 0 else "➡️"
        
        print(f"{signal_icon} {market}: {price:,}원 {change_icon}{change_rate:+.2f}% | "
              f"거래량: {volume:,} ({volume_ratio:.1f}배) | "
              f"조건: {sum(conditions.values())}/{len(conditions)}")
        
        if buy_signal:
            self.buy_signals += 1
            print(f"   🎯 매수 신호! (총 {self.buy_signals}회)")
        
        self.check_count += 1
        self.last_update = datetime.now().strftime('%H:%M:%S')
    
    def print_error(self, error_msg: str):
        """에러 메시지 출력"""
        print(f"\n❌ 에러: {error_msg}")
    
    def print_success(self, success_msg: str):
        """성공 메시지 출력"""
        print(f"\n✅ {success_msg}")
    
    def print_warning(self, warning_msg: str):
        """경고 메시지 출력"""
        print(f"\n⚠️ {warning_msg}")
    
    def get_summary(self) -> Dict[str, Any]:
        """요약 정보 반환"""
        elapsed_time = time.time() - self.start_time
        return {
            "monitoring_time": f"{int(elapsed_time // 3600):02d}:{int((elapsed_time % 3600) // 60):02d}:{int(elapsed_time % 60):02d}",
            "check_count": self.check_count,
            "buy_signals": self.buy_signals,
            "sell_signals": self.sell_signals,
            "last_update": self.last_update
        }
