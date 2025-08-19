#!/usr/bin/env python3
"""
로그 정리 및 포맷팅 도구
========================

장황한 시스템 로그를 깔끔하게 정리해서 보여주는 도구
"""

import re
import sys
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class TradingEvent:
    """거래 이벤트 정보"""
    timestamp: str
    symbol: str
    action: str  # BUY, SELL, HOLD
    price: float
    ma_price: float
    confidence: float
    has_position: bool
    event_type: str  # SIGNAL, REALTIME, HOLD
    
class LogFormatter:
    """로그 포맷터"""
    
    def __init__(self):
        self.events: List[TradingEvent] = []
        self.stats = defaultdict(int)
        
    def parse_log_line(self, line: str) -> Optional[TradingEvent]:
        """로그 라인을 파싱해서 거래 이벤트로 변환"""
        
        # 타임스탬프 추출
        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        if not timestamp_match:
            return None
        timestamp = timestamp_match.group(1)
        
        # BUY 신호 파싱
        if "BUY SIGNAL" in line:
            price_match = re.search(r'at ₩([\d,]+)', line)
            symbol_match = re.search(r'005930', line)
            if price_match and symbol_match:
                return TradingEvent(
                    timestamp=timestamp,
                    symbol="005930",
                    action="BUY",
                    price=float(price_match.group(1).replace(',', '')),
                    ma_price=0,  # 다음 라인에서 추출 필요
                    confidence=0.9,
                    has_position=False,
                    event_type="SIGNAL"
                )
        
        # SELL 신호 파싱
        elif "SELL SIGNAL" in line or "REALTIME SELL" in line:
            price_match = re.search(r'₩([\d,]+)', line)
            ma_match = re.search(r'MA ₩([\d,]+)', line)
            if price_match:
                return TradingEvent(
                    timestamp=timestamp,
                    symbol="005930",
                    action="SELL",
                    price=float(price_match.group(1).replace(',', '')),
                    ma_price=float(ma_match.group(1).replace(',', '')) if ma_match else 0,
                    confidence=0.9,
                    has_position=True,
                    event_type="REALTIME" if "REALTIME" in line else "SIGNAL"
                )
        
        # HOLD 상태 파싱
        elif "no position to sell" in line:
            return TradingEvent(
                timestamp=timestamp,
                symbol="005930",
                action="HOLD",
                price=0,
                ma_price=0,
                confidence=0,
                has_position=False,
                event_type="HOLD"
            )
        
        return None
    
    def format_trading_summary(self) -> str:
        """거래 요약 포맷팅"""
        if not self.events:
            return "📊 거래 이벤트 없음"
        
        summary = []
        summary.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        summary.append("🎯 QB Trading Summary")
        summary.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        for event in self.events[-10:]:  # 최근 10개만
            icon = self._get_action_icon(event.action, event.event_type)
            time_str = event.timestamp.split()[1][:8]  # HH:MM:SS만
            
            if event.action == "SELL" and event.ma_price > 0:
                summary.append(f"{icon} {time_str} {event.action:4} {event.symbol} @ ₩{event.price:,.0f} ≤ MA₩{event.ma_price:,.0f}")
            elif event.action == "BUY":
                summary.append(f"{icon} {time_str} {event.action:4} {event.symbol} @ ₩{event.price:,.0f} (신뢰도 {event.confidence:.0%})")
            else:
                summary.append(f"{icon} {time_str} {event.action:4} {event.symbol} (포지션 없음)")
        
        # 통계
        buy_count = sum(1 for e in self.events if e.action == "BUY")
        sell_count = sum(1 for e in self.events if e.action == "SELL")
        hold_count = sum(1 for e in self.events if e.action == "HOLD")
        
        summary.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        summary.append(f"📊 총 이벤트: {len(self.events)}개 (🟢BUY:{buy_count} 🔴SELL:{sell_count} ⏸️HOLD:{hold_count})")
        summary.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        return "\n".join(summary)
    
    def _get_action_icon(self, action: str, event_type: str) -> str:
        """액션별 아이콘 반환"""
        if action == "BUY":
            return "🟢"
        elif action == "SELL":
            return "🔴" if event_type == "REALTIME" else "🟠"
        else:
            return "⏸️"
    
    def format_live_status(self, current_price: float, ma_price: float, has_position: bool) -> str:
        """실시간 상태 포맷팅"""
        status_icon = "🟢" if current_price > ma_price else "🔴"
        position_text = "보유중" if has_position else "없음"
        signal_text = "매수권장" if current_price > ma_price and not has_position else \
                     "매도권장" if current_price <= ma_price and has_position else "관망"
        
        return f"""
┌─────────────────────────────────────────────────────┐
│ 🎯 실시간 거래 상태 [{datetime.now().strftime('%H:%M:%S')}]                     │
├─────────────────────────────────────────────────────┤
│ {status_icon} 005930: ₩{current_price:,.0f} | MA: ₩{ma_price:,.0f}           │
│ 📊 포지션: {position_text} | 권장: {signal_text}                      │
│ ⚡ 실시간체크: 정상 작동중 (3초 간격)                      │
└─────────────────────────────────────────────────────┘
"""

def main():
    """메인 함수 - stdin에서 로그를 읽어서 정리"""
    formatter = LogFormatter()
    
    print("📊 로그 정리 도구 시작 (Ctrl+C로 중단)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    try:
        for line in sys.stdin:
            event = formatter.parse_log_line(line.strip())
            if event:
                formatter.events.append(event)
                
                # 실시간으로 중요한 이벤트만 출력
                if event.action in ["BUY", "SELL"]:
                    icon = formatter._get_action_icon(event.action, event.event_type)
                    time_str = event.timestamp.split()[1][:8]
                    print(f"{icon} {time_str} {event.action} {event.symbol} @ ₩{event.price:,.0f}")
    
    except KeyboardInterrupt:
        print(f"\n{formatter.format_trading_summary()}")

if __name__ == "__main__":
    main()