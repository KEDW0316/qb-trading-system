#!/usr/bin/env python3
"""
QB Trading System - 통합 시뮬레이션 테스트
========================================

run_live_trading.py와 event_simulator.py를 함께 실행하여
실제 거래 시스템의 동작을 테스트하는 도구입니다.

사용법:
    # 기본 테스트 (5분간 실행)
    python tools/run_simulation_test.py
    
    # 길게 테스트 (30분간 실행) 
    python tools/run_simulation_test.py --duration 1800
    
    # 빠른 테스트 (10초 간격으로 5분)
    python tools/run_simulation_test.py --interval 10 --duration 300
    
    # 매수 편향 높임 (더 많은 매수 신호)
    python tools/run_simulation_test.py --buy-bias 0.7 --sell-bias 0.2
"""

import asyncio
import argparse
import subprocess
import sys
import os
import time
import signal
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimulationTestRunner:
    """시뮬레이션 테스트 실행기"""
    
    def __init__(self, config: dict):
        self.config = config
        self.trading_process = None
        self.simulator_process = None
        self.running = False
        self.start_time = None
        
    async def run_test(self):
        """통합 시뮬레이션 테스트 실행"""
        self.start_time = datetime.now()
        
        logger.info("🚀 QB Trading System - 통합 시뮬레이션 테스트 시작")
        logger.info("=" * 60)
        logger.info(f"📅 시작 시간: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"🎯 종목: {self.config['symbol']}")
        logger.info(f"⏱️ 이벤트 간격: {self.config['interval']}초")
        logger.info(f"⏰ 실행 시간: {self.config['duration']}초")
        logger.info(f"📈 매수 편향: {self.config['buy_bias']:.1%}")
        logger.info(f"📉 매도 편향: {self.config['sell_bias']:.1%}")
        logger.info("=" * 60)
        
        try:
            # 1. 거래 시스템 시작
            await self._start_trading_system()
            
            # 2. 짧은 대기 (시스템 초기화 완료 대기)
            logger.info("⏳ 거래 시스템 초기화 대기 중...")
            await asyncio.sleep(10)
            
            # 3. 이벤트 시뮬레이터 시작
            await self._start_event_simulator()
            
            # 4. 테스트 모니터링
            await self._monitor_test()
            
        except KeyboardInterrupt:
            logger.info("⚠️ 사용자에 의해 테스트가 중단되었습니다.")
        except Exception as e:
            logger.error(f"❌ 테스트 실행 중 오류: {e}")
        finally:
            await self._cleanup()
    
    async def _start_trading_system(self):
        """거래 시스템 시작"""
        cmd = [
            sys.executable, "run_live_trading.py",
            "--symbol", self.config['symbol'],
            "--max-amount", str(self.config['max_amount']),
            "--stop-loss", str(self.config['stop_loss']),
            "--dry-run"  # 모의 거래 모드
        ]
        
        logger.info(f"🔥 거래 시스템 시작: {' '.join(cmd)}")
        
        # 거래 시스템을 별도 프로세스로 실행
        self.trading_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # 비동기적으로 출력 모니터링
        asyncio.create_task(self._monitor_trading_output())
        
        logger.info("✅ 거래 시스템 프로세스 시작됨")
    
    async def _start_event_simulator(self):
        """이벤트 시뮬레이터 시작"""
        cmd = [
            sys.executable, "tools/event_simulator.py",
            "--symbol", self.config['symbol'],
            "--interval", str(self.config['interval']),
            "--duration", str(self.config['duration']),
            "--buy-bias", str(self.config['buy_bias']),
            "--sell-bias", str(self.config['sell_bias'])
        ]
        
        logger.info(f"🎭 이벤트 시뮬레이터 시작: {' '.join(cmd)}")
        
        # 시뮬레이터를 별도 프로세스로 실행
        self.simulator_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # 비동기적으로 출력 모니터링
        asyncio.create_task(self._monitor_simulator_output())
        
        logger.info("✅ 이벤트 시뮬레이터 프로세스 시작됨")
    
    async def _monitor_trading_output(self):
        """거래 시스템 출력 모니터링"""
        try:
            while self.trading_process and self.trading_process.poll() is None:
                line = await asyncio.to_thread(self.trading_process.stdout.readline)
                if line:
                    # 중요한 로그만 출력
                    if any(keyword in line for keyword in ['🚨', '📋', '✅', '❌', '⚠️', '📊']):
                        logger.info(f"[TRADING] {line.strip()}")
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"거래 시스템 출력 모니터링 오류: {e}")
    
    async def _monitor_simulator_output(self):
        """시뮬레이터 출력 모니터링"""
        try:
            while self.simulator_process and self.simulator_process.poll() is None:
                line = await asyncio.to_thread(self.simulator_process.stdout.readline)
                if line:
                    # 중요한 로그만 출력
                    if any(keyword in line for keyword in ['🎭', '📡', '🚀', '🛑', '❌']):
                        logger.info(f"[SIMULATOR] {line.strip()}")
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"시뮬레이터 출력 모니터링 오류: {e}")
    
    async def _monitor_test(self):
        """테스트 모니터링"""
        self.running = True
        end_time = self.start_time + timedelta(seconds=self.config['duration'])
        last_status_time = time.time()
        
        logger.info("🔍 테스트 모니터링 시작...")
        
        while self.running and datetime.now() < end_time:
            # 30초마다 상태 출력
            if time.time() - last_status_time > 30:
                await self._print_test_status()
                last_status_time = time.time()
            
            # 프로세스 상태 확인
            if self.trading_process and self.trading_process.poll() is not None:
                logger.warning("⚠️ 거래 시스템 프로세스가 종료되었습니다.")
                break
            
            if self.simulator_process and self.simulator_process.poll() is not None:
                logger.info("✅ 이벤트 시뮬레이터가 완료되었습니다.")
                break
            
            await asyncio.sleep(1)
        
        if datetime.now() >= end_time:
            logger.info("⏰ 지정된 테스트 시간이 완료되었습니다.")
    
    async def _print_test_status(self):
        """테스트 상태 출력"""
        runtime = datetime.now() - self.start_time
        remaining = self.config['duration'] - runtime.total_seconds()
        
        logger.info("\n" + "=" * 50)
        logger.info(f"🔍 통합 테스트 상태 (실행시간: {runtime})")
        logger.info(f"⏰ 남은 시간: {max(0, remaining):.0f}초")
        logger.info(f"🔥 거래 시스템: {'실행중' if self.trading_process and self.trading_process.poll() is None else '중지됨'}")
        logger.info(f"🎭 시뮬레이터: {'실행중' if self.simulator_process and self.simulator_process.poll() is None else '중지됨'}")
        logger.info("=" * 50 + "\n")
    
    async def _cleanup(self):
        """정리 작업"""
        logger.info("\n🧹 테스트 정리 중...")
        
        self.running = False
        
        # 시뮬레이터 프로세스 종료
        if self.simulator_process:
            try:
                self.simulator_process.terminate()
                await asyncio.to_thread(self.simulator_process.wait, timeout=5)
                logger.info("✅ 이벤트 시뮬레이터 프로세스 종료")
            except subprocess.TimeoutExpired:
                self.simulator_process.kill()
                logger.warning("⚠️ 이벤트 시뮬레이터 프로세스 강제 종료")
            except Exception as e:
                logger.error(f"❌ 시뮬레이터 종료 오류: {e}")
        
        # 거래 시스템 프로세스 종료
        if self.trading_process:
            try:
                # SIGINT 전송 (Ctrl+C와 동일)
                self.trading_process.send_signal(signal.SIGINT)
                await asyncio.to_thread(self.trading_process.wait, timeout=10)
                logger.info("✅ 거래 시스템 프로세스 정상 종료")
            except subprocess.TimeoutExpired:
                self.trading_process.kill()
                logger.warning("⚠️ 거래 시스템 프로세스 강제 종료")
            except Exception as e:
                logger.error(f"❌ 거래 시스템 종료 오류: {e}")
        
        # 최종 보고서 생성
        await self._generate_test_report()
    
    async def _generate_test_report(self):
        """테스트 보고서 생성"""
        runtime = datetime.now() - self.start_time if self.start_time else timedelta(0)
        
        logger.info("\n" + "=" * 60)
        logger.info("📋 통합 시뮬레이션 테스트 완료 보고서")
        logger.info("=" * 60)
        logger.info(f"⏱️ 총 실행 시간: {runtime}")
        logger.info(f"🎯 테스트 종목: {self.config['symbol']}")
        logger.info(f"📡 이벤트 간격: {self.config['interval']}초")
        logger.info(f"📈 매수 편향: {self.config['buy_bias']:.1%}")
        logger.info(f"📉 매도 편향: {self.config['sell_bias']:.1%}")
        logger.info("=" * 60)
        logger.info("✅ 테스트가 완료되었습니다.")
        logger.info("📄 상세 로그는 logs/ 디렉토리에서 확인하세요.")
        logger.info("=" * 60)

async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='QB Trading System - 통합 시뮬레이션 테스트')
    parser.add_argument('--symbol', default='005930', help='테스트할 종목 코드 (기본: 005930)')
    parser.add_argument('--interval', type=int, default=30, help='이벤트 발송 간격 (초, 기본: 30)')
    parser.add_argument('--duration', type=int, default=300, help='테스트 실행 시간 (초, 기본: 300)')
    parser.add_argument('--buy-bias', type=float, default=0.4, help='매수 신호 편향 (기본: 0.4)')
    parser.add_argument('--sell-bias', type=float, default=0.3, help='매도 신호 편향 (기본: 0.3)')
    parser.add_argument('--max-amount', type=int, default=100000, help='최대 거래 금액 (기본: 100,000원)')
    parser.add_argument('--stop-loss', type=float, default=3.0, help='손절매 비율 % (기본: 3.0%)')
    
    args = parser.parse_args()
    
    # 설정 구성
    config = {
        'symbol': args.symbol,
        'interval': args.interval,
        'duration': args.duration,
        'buy_bias': args.buy_bias,
        'sell_bias': args.sell_bias,
        'max_amount': args.max_amount,
        'stop_loss': args.stop_loss
    }
    
    # 설정 검증
    if args.buy_bias + args.sell_bias > 1.0:
        logger.warning(f"⚠️ 매수/매도 편향 합계가 1.0을 초과합니다 ({args.buy_bias + args.sell_bias:.1f})")
    
    # 테스트 실행
    runner = SimulationTestRunner(config)
    await runner.run_test()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️ 테스트가 중단되었습니다.")
    except Exception as e:
        logger.error(f"\n❌ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()