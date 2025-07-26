# Technical Analysis Usage Examples

## 🚀 시작하기

### 기본 설정

```python
import asyncio
import pandas as pd
from datetime import datetime, timedelta

from qb.analysis.technical_analyzer import TechnicalAnalyzer
from qb.analysis.indicators import IndicatorCalculator
from qb.utils.redis_manager import RedisManager
from qb.utils.event_bus import EventBus, EventType
```

### 환경 초기화

```python
async def setup_environment():
    # Redis 및 이벤트 버스 초기화
    redis_manager = RedisManager()
    event_bus = EventBus(redis_manager)
    
    # 기술적 분석기 초기화
    analyzer = TechnicalAnalyzer(redis_manager, event_bus)
    
    return redis_manager, event_bus, analyzer

# 초기화 실행
redis_manager, event_bus, analyzer = await setup_environment()
```

---

## 📊 기본 사용 예제

### 1. 단일 종목 지표 계산

```python
async def basic_indicator_calculation():
    # 샘플 캔들 데이터 생성
    candles = []
    base_price = 50000
    
    for i in range(30):  # 30일 데이터
        price_change = np.random.uniform(-0.05, 0.05)  # ±5% 변동
        open_price = base_price * (1 + price_change)
        high_price = open_price * (1 + abs(np.random.uniform(0, 0.03)))
        low_price = open_price * (1 - abs(np.random.uniform(0, 0.03)))
        close_price = np.random.uniform(low_price, high_price)
        
        candles.append({
            'timestamp': (datetime.now() - timedelta(days=29-i)).isoformat(),
            'open': round(open_price),
            'high': round(high_price),
            'low': round(low_price),
            'close': round(close_price),
            'volume': np.random.randint(1000, 10000)
        })
        
        base_price = close_price
    
    # 지표 계산
    indicators = await analyzer.calculate_indicators("005930", candles, "1d")
    
    print("=== 삼성전자 기술적 지표 ===")
    print(f"현재가: {indicators['current_price']:,}원")
    print(f"SMA(20): {indicators['sma_20']:,.0f}원")
    print(f"EMA(20): {indicators['ema_20']:,.0f}원")
    print(f"RSI: {indicators['rsi']:.1f}")
    print(f"MACD: {indicators['macd']:.2f}")
    print(f"볼린저 상단: {indicators['bb_upper']:,.0f}원")
    print(f"볼린저 하단: {indicators['bb_lower']:,.0f}원")
    print(f"ATR: {indicators['atr']:.0f}원")

# 실행
await basic_indicator_calculation()
```

### 2. 이벤트 기반 실시간 처리

```python
class TradingBot:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.positions = {}  # 포지션 관리
        
    async def setup_listeners(self):
        # 지표 업데이트 이벤트 구독
        self.event_bus.subscribe(
            EventType.INDICATORS_UPDATED, 
            self.on_indicators_updated
        )
        
    async def on_indicators_updated(self, event):
        data = event.data
        symbol = data['symbol']
        indicators = data['indicators']
        
        # RSI 기반 매매 신호
        await self.check_rsi_signals(symbol, indicators)
        
        # MACD 기반 매매 신호
        await self.check_macd_signals(symbol, indicators)
        
        # 볼린저 밴드 기반 매매 신호
        await self.check_bollinger_signals(symbol, indicators)
        
    async def check_rsi_signals(self, symbol, indicators):
        rsi = indicators['rsi']
        current_price = indicators['current_price']
        
        if rsi > 70 and symbol in self.positions:
            print(f"🔴 {symbol} 매도 신호 (RSI: {rsi:.1f}, 과매수)")
            await self.sell_signal(symbol, current_price, "RSI 과매수")
            
        elif rsi < 30 and symbol not in self.positions:
            print(f"🟢 {symbol} 매수 신호 (RSI: {rsi:.1f}, 과매도)")
            await self.buy_signal(symbol, current_price, "RSI 과매도")
            
    async def check_macd_signals(self, symbol, indicators):
        macd = indicators['macd']
        macd_signal = indicators['macd_signal']
        macd_hist = indicators['macd_histogram']
        current_price = indicators['current_price']
        
        # MACD 골든크로스
        if macd > macd_signal and macd_hist > 0:
            if symbol not in self.positions:
                print(f"🟢 {symbol} 매수 신호 (MACD 골든크로스)")
                await self.buy_signal(symbol, current_price, "MACD 골든크로스")
                
        # MACD 데드크로스
        elif macd < macd_signal and macd_hist < 0:
            if symbol in self.positions:
                print(f"🔴 {symbol} 매도 신호 (MACD 데드크로스)")
                await self.sell_signal(symbol, current_price, "MACD 데드크로스")
                
    async def check_bollinger_signals(self, symbol, indicators):
        current_price = indicators['current_price']
        bb_upper = indicators['bb_upper']
        bb_lower = indicators['bb_lower']
        bb_middle = indicators['bb_middle']
        
        # 볼린저 밴드 상단 돌파 (과매수)
        if current_price > bb_upper:
            if symbol in self.positions:
                print(f"🔴 {symbol} 매도 신호 (볼린저 상단 돌파)")
                await self.sell_signal(symbol, current_price, "볼린저 상단 돌파")
                
        # 볼린저 밴드 하단 터치 (과매도)
        elif current_price < bb_lower:
            if symbol not in self.positions:
                print(f"🟢 {symbol} 매수 신호 (볼린저 하단 터치)")
                await self.buy_signal(symbol, current_price, "볼린저 하단 터치")
                
        # 중간선 회귀
        elif abs(current_price - bb_middle) / bb_middle < 0.01:  # 1% 이내
            print(f"ℹ️ {symbol} 중립 (볼린저 중간선 근처)")
            
    async def buy_signal(self, symbol, price, reason):
        self.positions[symbol] = {
            'entry_price': price,
            'entry_time': datetime.now(),
            'reason': reason
        }
        print(f"  💰 매수 실행: {price:,}원 (사유: {reason})")
        
    async def sell_signal(self, symbol, price, reason):
        if symbol in self.positions:
            entry_price = self.positions[symbol]['entry_price']
            profit_pct = (price - entry_price) / entry_price * 100
            
            del self.positions[symbol]
            print(f"  💰 매도 실행: {price:,}원 (수익률: {profit_pct:+.2f}%, 사유: {reason})")

# 트레이딩 봇 설정 및 실행
bot = TradingBot(event_bus)
await bot.setup_listeners()

# 분석기 시작
await analyzer.start()
```

---

## 📈 고급 사용 예제

### 3. 다중 종목 포트폴리오 분석

```python
class PortfolioAnalyzer:
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.portfolio = ['005930', '000660', '035420', '005380', '051910']  # 대형주 5종목
        
    async def analyze_portfolio(self, candles_data):
        """포트폴리오 전체 분석"""
        portfolio_indicators = {}
        
        # 각 종목별 지표 계산
        for symbol in self.portfolio:
            if symbol in candles_data:
                indicators = await self.analyzer.calculate_indicators(
                    symbol, candles_data[symbol], "1d"
                )
                portfolio_indicators[symbol] = indicators
                
        # 포트폴리오 전체 분석
        analysis = self.analyze_portfolio_signals(portfolio_indicators)
        return analysis
        
    def analyze_portfolio_signals(self, portfolio_indicators):
        """포트폴리오 시그널 분석"""
        signals = {
            'strong_buy': [],
            'buy': [],
            'hold': [],
            'sell': [],
            'strong_sell': []
        }
        
        for symbol, indicators in portfolio_indicators.items():
            score = self.calculate_signal_score(indicators)
            
            if score >= 8:
                signals['strong_buy'].append((symbol, score))
            elif score >= 6:
                signals['buy'].append((symbol, score))
            elif score >= 4:
                signals['hold'].append((symbol, score))
            elif score >= 2:
                signals['sell'].append((symbol, score))
            else:
                signals['strong_sell'].append((symbol, score))
                
        return signals
        
    def calculate_signal_score(self, indicators):
        """종합 신호 점수 계산 (0-10점)"""
        score = 5  # 중립 기준점
        
        # RSI 점수 (0-2점)
        rsi = indicators['rsi']
        if rsi < 30:
            score += 2  # 과매도 (매수 신호)
        elif rsi < 40:
            score += 1
        elif rsi > 70:
            score -= 2  # 과매수 (매도 신호)
        elif rsi > 60:
            score -= 1
            
        # MACD 점수 (0-2점)
        macd_hist = indicators['macd_histogram']
        if macd_hist > 0:
            score += 1  # 상승 모멘텀
        else:
            score -= 1  # 하락 모멘텀
            
        # 볼린저 밴드 점수 (0-2점)
        current_price = indicators['current_price']
        bb_upper = indicators['bb_upper']
        bb_lower = indicators['bb_lower']
        bb_middle = indicators['bb_middle']
        
        if current_price < bb_lower:
            score += 2  # 과매도
        elif current_price < bb_middle:
            score += 1
        elif current_price > bb_upper:
            score -= 2  # 과매수
        elif current_price > bb_middle:
            score -= 1
            
        # 이동평균 점수 (0-1점)
        if indicators['current_price'] > indicators['sma_20']:
            score += 1  # 상승 추세
        else:
            score -= 1  # 하락 추세
            
        return max(0, min(10, score))  # 0-10 범위로 제한
        
    def print_portfolio_analysis(self, signals):
        """포트폴리오 분석 결과 출력"""
        print("=== 포트폴리오 분석 결과 ===")
        
        for signal_type, items in signals.items():
            if items:
                print(f"\n{signal_type.upper()}:")
                for symbol, score in sorted(items, key=lambda x: x[1], reverse=True):
                    print(f"  {symbol}: {score}/10점")

# 사용 예제
portfolio_analyzer = PortfolioAnalyzer(analyzer)

# 샘플 데이터로 분석 실행
sample_candles_data = {
    '005930': generate_sample_candles(50000, 30),  # 삼성전자
    '000660': generate_sample_candles(30000, 30),  # SK하이닉스
    '035420': generate_sample_candles(400000, 30), # NAVER
    '005380': generate_sample_candles(80000, 30),  # 현대차
    '051910': generate_sample_candles(60000, 30),  # LG화학
}

signals = await portfolio_analyzer.analyze_portfolio(sample_candles_data)
portfolio_analyzer.print_portfolio_analysis(signals)
```

### 4. 커스텀 지표 개발 및 활용

```python
class AdvancedIndicators:
    def __init__(self, calculator):
        self.calculator = calculator
        self.setup_custom_indicators()
        
    def setup_custom_indicators(self):
        """고급 커스텀 지표 등록"""
        
        # 1. 변동성 비율 지표
        def volatility_ratio(data, period=10):
            """일일 변동성 비율"""
            daily_range = (data['high'] - data['low']) / data['close'] * 100
            return daily_range.rolling(window=period).mean()
            
        self.calculator.register_custom_indicator(
            'volatility_ratio',
            volatility_ratio,
            'Average daily volatility ratio over period',
            ['high', 'low', 'close'],
            {'period': 10}
        )
        
        # 2. 모멘텀 지표
        def price_momentum(data, period=10):
            """가격 모멘텀"""
            return (data['close'] / data['close'].shift(period) - 1) * 100
            
        self.calculator.register_custom_indicator(
            'price_momentum',
            price_momentum,
            'Price momentum over specified period',
            ['close'],
            {'period': 10}
        )
        
        # 3. 거래량 가중 평균가
        def vwap(data, period=20):
            """거래량 가중 평균가"""
            typical_price = (data['high'] + data['low'] + data['close']) / 3
            volume_price = typical_price * data['volume']
            return volume_price.rolling(window=period).sum() / data['volume'].rolling(window=period).sum()
            
        self.calculator.register_custom_indicator(
            'vwap',
            vwap,
            'Volume Weighted Average Price',
            ['high', 'low', 'close', 'volume'],
            {'period': 20}
        )
        
        # 4. 지지/저항 레벨 (단순화된 버전)
        def support_resistance(data, period=20, threshold=0.02):
            """지지/저항 레벨 계산"""
            high_max = data['high'].rolling(window=period).max()
            low_min = data['low'].rolling(window=period).min()
            
            current_price = data['close'].iloc[-1]
            resistance = high_max.iloc[-1]
            support = low_min.iloc[-1]
            
            # 현재가 기준 거리 계산
            resistance_distance = (resistance - current_price) / current_price
            support_distance = (current_price - support) / current_price
            
            return {
                'resistance': resistance,
                'support': support,
                'resistance_distance': resistance_distance,
                'support_distance': support_distance
            }
            
        self.calculator.register_custom_indicator(
            'support_resistance',
            support_resistance,
            'Support and Resistance levels',
            ['high', 'low', 'close'],
            {'period': 20, 'threshold': 0.02}
        )
        
    async def calculate_advanced_analysis(self, symbol, candles):
        """고급 분석 실행"""
        # 기본 지표 계산
        basic_indicators = await self.calculator.calculate_all_indicators(candles)
        
        # 커스텀 지표 계산
        custom_indicators = {}
        
        # 변동성 비율
        volatility = self.calculator.calculate_custom_indicator(
            'volatility_ratio', candles, period=10
        )
        custom_indicators['volatility_ratio'] = volatility.iloc[-1] if hasattr(volatility, 'iloc') else volatility
        
        # 가격 모멘텀
        momentum_5d = self.calculator.calculate_custom_indicator(
            'price_momentum', candles, period=5
        )
        momentum_20d = self.calculator.calculate_custom_indicator(
            'price_momentum', candles, period=20
        )
        custom_indicators['momentum_5d'] = momentum_5d.iloc[-1] if hasattr(momentum_5d, 'iloc') else momentum_5d
        custom_indicators['momentum_20d'] = momentum_20d.iloc[-1] if hasattr(momentum_20d, 'iloc') else momentum_20d
        
        # VWAP
        vwap = self.calculator.calculate_custom_indicator(
            'vwap', candles, period=20
        )
        custom_indicators['vwap'] = vwap.iloc[-1] if hasattr(vwap, 'iloc') else vwap
        
        # 지지/저항 레벨
        sr_levels = self.calculator.calculate_custom_indicator(
            'support_resistance', candles, period=20
        )
        custom_indicators.update(sr_levels)
        
        # 종합 분석
        analysis = self.generate_comprehensive_analysis(
            symbol, basic_indicators, custom_indicators
        )
        
        return analysis
        
    def generate_comprehensive_analysis(self, symbol, basic, custom):
        """종합 분석 리포트 생성"""
        current_price = basic['current_price']
        
        analysis = {
            'symbol': symbol,
            'current_price': current_price,
            'basic_indicators': basic,
            'custom_indicators': custom,
            'signals': [],
            'risk_level': 'medium',
            'recommendation': 'hold'
        }
        
        # 신호 분석
        signals = []
        
        # RSI 신호
        rsi = basic['rsi']
        if rsi > 70:
            signals.append(f"RSI 과매수 구간 ({rsi:.1f})")
        elif rsi < 30:
            signals.append(f"RSI 과매도 구간 ({rsi:.1f})")
            
        # MACD 신호
        if basic['macd_histogram'] > 0:
            signals.append("MACD 상승 모멘텀")
        else:
            signals.append("MACD 하락 모멘텀")
            
        # 볼린저 밴드 신호
        bb_position = (current_price - basic['bb_lower']) / (basic['bb_upper'] - basic['bb_lower'])
        if bb_position > 0.8:
            signals.append("볼린저 밴드 상단 근접")
        elif bb_position < 0.2:
            signals.append("볼린저 밴드 하단 근접")
            
        # 변동성 분석
        volatility = custom['volatility_ratio']
        if volatility > 5:
            signals.append(f"높은 변동성 ({volatility:.1f}%)")
            analysis['risk_level'] = 'high'
        elif volatility < 2:
            signals.append(f"낮은 변동성 ({volatility:.1f}%)")
            analysis['risk_level'] = 'low'
            
        # 모멘텀 분석
        momentum_5d = custom['momentum_5d']
        momentum_20d = custom['momentum_20d']
        
        if momentum_5d > 5 and momentum_20d > 0:
            signals.append("강한 상승 모멘텀")
            analysis['recommendation'] = 'buy'
        elif momentum_5d < -5 and momentum_20d < 0:
            signals.append("강한 하락 모멘텀")
            analysis['recommendation'] = 'sell'
            
        # VWAP 분석
        vwap = custom['vwap']
        if current_price > vwap * 1.02:
            signals.append("VWAP 상회 (매수 우세)")
        elif current_price < vwap * 0.98:
            signals.append("VWAP 하회 (매도 우세)")
            
        # 지지/저항 분석
        resistance_distance = custom['resistance_distance']
        support_distance = custom['support_distance']
        
        if resistance_distance < 0.02:  # 2% 이내
            signals.append(f"저항선 근접 ({custom['resistance']:,.0f})")
        if support_distance < 0.02:  # 2% 이내
            signals.append(f"지지선 근접 ({custom['support']:,.0f})")
            
        analysis['signals'] = signals
        return analysis
        
    def print_analysis_report(self, analysis):
        """분석 리포트 출력"""
        print(f"=== {analysis['symbol']} 종합 기술적 분석 ===")
        print(f"현재가: {analysis['current_price']:,}원")
        print(f"추천: {analysis['recommendation'].upper()}")
        print(f"위험도: {analysis['risk_level'].upper()}")
        
        print("\n📊 주요 지표:")
        basic = analysis['basic_indicators']
        custom = analysis['custom_indicators']
        
        print(f"  RSI: {basic['rsi']:.1f}")
        print(f"  MACD: {basic['macd']:.2f}")
        print(f"  ATR: {basic['atr']:.0f}")
        print(f"  변동성: {custom['volatility_ratio']:.1f}%")
        print(f"  5일 모멘텀: {custom['momentum_5d']:+.1f}%")
        print(f"  20일 모멘텀: {custom['momentum_20d']:+.1f}%")
        print(f"  VWAP: {custom['vwap']:,.0f}원")
        print(f"  지지선: {custom['support']:,.0f}원")
        print(f"  저항선: {custom['resistance']:,.0f}원")
        
        print("\n🔍 기술적 신호:")
        for signal in analysis['signals']:
            print(f"  • {signal}")

# 사용 예제
advanced = AdvancedIndicators(analyzer.indicator_calculator)

# 고급 분석 실행
sample_candles = generate_sample_candles(50000, 50)  # 50일 데이터
analysis = await advanced.calculate_advanced_analysis("005930", sample_candles)
advanced.print_analysis_report(analysis)
```

---

## 🎯 실전 활용 시나리오

### 5. 실시간 알림 시스템

```python
class AlertSystem:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.alert_rules = {}
        self.alert_history = []
        
    def add_alert_rule(self, symbol, rule_name, condition_func, message_template):
        """알림 규칙 추가"""
        if symbol not in self.alert_rules:
            self.alert_rules[symbol] = {}
            
        self.alert_rules[symbol][rule_name] = {
            'condition': condition_func,
            'message': message_template,
            'last_triggered': None
        }
        
    async def setup_listeners(self):
        """이벤트 리스너 설정"""
        self.event_bus.subscribe(
            EventType.INDICATORS_UPDATED,
            self.check_alerts
        )
        
    async def check_alerts(self, event):
        """알림 조건 확인"""
        data = event.data
        symbol = data['symbol']
        indicators = data['indicators']
        
        if symbol in self.alert_rules:
            for rule_name, rule in self.alert_rules[symbol].items():
                if rule['condition'](indicators):
                    await self.trigger_alert(symbol, rule_name, indicators, rule)
                    
    async def trigger_alert(self, symbol, rule_name, indicators, rule):
        """알림 발생"""
        now = datetime.now()
        
        # 중복 알림 방지 (5분 이내 같은 알림 제한)
        if rule['last_triggered']:
            time_diff = now - rule['last_triggered']
            if time_diff.total_seconds() < 300:  # 5분
                return
                
        # 알림 메시지 생성
        message = rule['message'].format(
            symbol=symbol,
            current_price=indicators['current_price'],
            rsi=indicators['rsi'],
            macd=indicators['macd'],
            **indicators
        )
        
        # 알림 기록
        alert_record = {
            'timestamp': now,
            'symbol': symbol,
            'rule_name': rule_name,
            'message': message,
            'indicators': indicators.copy()
        }
        
        self.alert_history.append(alert_record)
        rule['last_triggered'] = now
        
        # 알림 출력 (실제로는 메일, SMS, 슬랙 등으로 전송)
        print(f"🚨 [{now.strftime('%H:%M:%S')}] {message}")
        
        # 중요한 알림은 로그 파일에도 기록
        if rule_name in ['strong_buy', 'strong_sell']:
            await self.log_important_alert(alert_record)
            
    async def log_important_alert(self, alert_record):
        """중요 알림 로그 기록"""
        log_entry = f"{alert_record['timestamp'].isoformat()} - {alert_record['message']}\n"
        
        with open('logs/important_alerts.log', 'a', encoding='utf-8') as f:
            f.write(log_entry)

# 알림 시스템 설정
alert_system = AlertSystem(event_bus)

# 알림 규칙 정의
def rsi_oversold(indicators):
    return indicators['rsi'] < 30

def rsi_overbought(indicators):
    return indicators['rsi'] > 70

def strong_buy_signal(indicators):
    return (indicators['rsi'] < 35 and 
            indicators['macd_histogram'] > 0 and
            indicators['current_price'] < indicators['bb_lower'])

def strong_sell_signal(indicators):
    return (indicators['rsi'] > 65 and 
            indicators['macd_histogram'] < 0 and
            indicators['current_price'] > indicators['bb_upper'])

def volume_spike(indicators):
    # 실제로는 평균 거래량과 비교해야 함
    return indicators.get('volume', 0) > 10000

# 삼성전자 알림 규칙 등록
alert_system.add_alert_rule(
    "005930", 
    "rsi_oversold",
    rsi_oversold,
    "💡 {symbol} RSI 과매도 (RSI: {rsi:.1f}, 현재가: {current_price:,}원)"
)

alert_system.add_alert_rule(
    "005930",
    "rsi_overbought", 
    rsi_overbought,
    "⚠️ {symbol} RSI 과매수 (RSI: {rsi:.1f}, 현재가: {current_price:,}원)"
)

alert_system.add_alert_rule(
    "005930",
    "strong_buy",
    strong_buy_signal,
    "🚀 {symbol} 강한 매수 신호! (RSI: {rsi:.1f}, MACD: {macd:.2f}, 현재가: {current_price:,}원)"
)

alert_system.add_alert_rule(
    "005930",
    "strong_sell",
    strong_sell_signal,
    "🔥 {symbol} 강한 매도 신호! (RSI: {rsi:.1f}, MACD: {macd:.2f}, 현재가: {current_price:,}원)"
)

# 알림 시스템 시작
await alert_system.setup_listeners()
```

### 6. 백테스팅 시스템

```python
class BacktestingEngine:
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.results = []
        
    async def run_backtest(self, symbol, historical_data, strategy_func, initial_capital=1000000):
        """백테스트 실행"""
        capital = initial_capital
        position = 0  # 보유 주식 수
        trades = []
        
        print(f"=== {symbol} 백테스트 시작 ===")
        print(f"초기 자본: {initial_capital:,}원")
        print(f"데이터 기간: {len(historical_data)}일")
        
        for i in range(20, len(historical_data)):  # 최소 20일 데이터 필요
            # 현재까지 데이터로 지표 계산
            current_data = historical_data[:i+1]
            indicators = await self.analyzer.calculate_indicators(
                symbol, current_data, "1d"
            )
            
            current_price = indicators['current_price']
            
            # 전략 실행
            signal = strategy_func(indicators)
            
            if signal == 'BUY' and position == 0 and capital > current_price:
                # 매수
                shares = int(capital // current_price)
                if shares > 0:
                    position = shares
                    cost = shares * current_price
                    capital -= cost
                    
                    trade = {
                        'date': historical_data[i]['timestamp'],
                        'action': 'BUY',
                        'price': current_price,
                        'shares': shares,
                        'cost': cost,
                        'capital': capital,
                        'indicators': indicators.copy()
                    }
                    trades.append(trade)
                    print(f"📈 매수: {shares}주 @ {current_price:,}원 (잔고: {capital:,}원)")
                    
            elif signal == 'SELL' and position > 0:
                # 매도
                revenue = position * current_price
                capital += revenue
                
                trade = {
                    'date': historical_data[i]['timestamp'],
                    'action': 'SELL',
                    'price': current_price,
                    'shares': position,
                    'revenue': revenue,
                    'capital': capital,
                    'indicators': indicators.copy()
                }
                trades.append(trade)
                
                # 수익률 계산
                last_buy = next(t for t in reversed(trades[:-1]) if t['action'] == 'BUY')
                profit = revenue - last_buy['cost']
                profit_pct = (profit / last_buy['cost']) * 100
                
                print(f"📉 매도: {position}주 @ {current_price:,}원 (수익: {profit:+,}원, {profit_pct:+.2f}%)")
                position = 0
                
        # 최종 결과 계산
        final_value = capital + (position * historical_data[-1]['close'])
        total_return = (final_value - initial_capital) / initial_capital * 100
        
        result = {
            'symbol': symbol,
            'initial_capital': initial_capital,
            'final_value': final_value,
            'total_return_pct': total_return,
            'total_trades': len(trades),
            'winning_trades': len([t for t in trades if t['action'] == 'SELL' and self.calculate_trade_profit(t, trades) > 0]),
            'trades': trades
        }
        
        self.results.append(result)
        self.print_backtest_results(result)
        
        return result
        
    def calculate_trade_profit(self, sell_trade, all_trades):
        """매매 수익 계산"""
        # 해당 매도 이전의 마지막 매수 찾기
        sell_index = all_trades.index(sell_trade)
        
        for i in range(sell_index - 1, -1, -1):
            if all_trades[i]['action'] == 'BUY':
                buy_trade = all_trades[i]
                return sell_trade['revenue'] - buy_trade['cost']
                
        return 0
        
    def print_backtest_results(self, result):
        """백테스트 결과 출력"""
        print(f"\n=== 백테스트 결과 ===")
        print(f"종목: {result['symbol']}")
        print(f"초기 자본: {result['initial_capital']:,}원")
        print(f"최종 자산: {result['final_value']:,}원")
        print(f"총 수익률: {result['total_return_pct']:+.2f}%")
        print(f"총 거래 수: {result['total_trades']}회")
        print(f"승률: {result['winning_trades']}/{result['total_trades']} ({result['winning_trades']/max(result['total_trades'],1)*100:.1f}%)")

# 전략 함수 정의
def rsi_strategy(indicators):
    """RSI 기반 전략"""
    rsi = indicators['rsi']
    
    if rsi < 30:  # 과매도
        return 'BUY'
    elif rsi > 70:  # 과매수
        return 'SELL'
    else:
        return 'HOLD'

def combined_strategy(indicators):
    """복합 전략"""
    rsi = indicators['rsi']
    macd_hist = indicators['macd_histogram']
    current_price = indicators['current_price']
    bb_lower = indicators['bb_lower']
    bb_upper = indicators['bb_upper']
    
    # 강한 매수 신호
    if (rsi < 35 and 
        macd_hist > 0 and 
        current_price < bb_lower):
        return 'BUY'
        
    # 강한 매도 신호
    if (rsi > 65 and 
        macd_hist < 0 and 
        current_price > bb_upper):
        return 'SELL'
        
    return 'HOLD'

# 백테스트 실행
backtester = BacktestingEngine(analyzer)

# 샘플 데이터로 백테스트
historical_data = generate_sample_candles(50000, 100)  # 100일 데이터

# RSI 전략 백테스트
result1 = await backtester.run_backtest("005930", historical_data, rsi_strategy)

# 복합 전략 백테스트
result2 = await backtester.run_backtest("005930", historical_data, combined_strategy)
```

---

## 🛠️ 유틸리티 함수

### 샘플 데이터 생성기

```python
def generate_sample_candles(start_price, days, volatility=0.02):
    """샘플 캔들 데이터 생성"""
    import numpy as np
    from datetime import datetime, timedelta
    
    candles = []
    current_price = start_price
    
    for i in range(days):
        # 랜덤 워크로 가격 생성
        price_change = np.random.normal(0, volatility)
        open_price = current_price
        
        # 일중 변동 생성
        intraday_volatility = volatility * 0.5
        high_change = abs(np.random.normal(0, intraday_volatility))
        low_change = abs(np.random.normal(0, intraday_volatility))
        
        high_price = open_price * (1 + high_change)
        low_price = open_price * (1 - low_change)
        close_price = open_price * (1 + price_change)
        
        # 종가가 고가/저가 범위 내에 있도록 조정
        close_price = max(low_price, min(high_price, close_price))
        
        # 거래량 생성 (변동성에 따라 증가)
        base_volume = 1000
        volume_multiplier = 1 + abs(price_change) * 10
        volume = int(base_volume * volume_multiplier * np.random.uniform(0.5, 2.0))
        
        candle = {
            'timestamp': (datetime.now() - timedelta(days=days-1-i)).isoformat(),
            'open': round(open_price),
            'high': round(high_price),
            'low': round(low_price),
            'close': round(close_price),
            'volume': volume
        }
        
        candles.append(candle)
        current_price = close_price
        
    return candles

def print_candle_summary(candles):
    """캔들 데이터 요약 출력"""
    if not candles:
        return
        
    prices = [c['close'] for c in candles]
    volumes = [c['volume'] for c in candles]
    
    print(f"=== 캔들 데이터 요약 ===")
    print(f"데이터 기간: {len(candles)}일")
    print(f"시작가: {candles[0]['open']:,}원")
    print(f"종료가: {candles[-1]['close']:,}원")
    print(f"최고가: {max(c['high'] for c in candles):,}원")
    print(f"최저가: {min(c['low'] for c in candles):,}원")
    print(f"평균 거래량: {np.mean(volumes):,.0f}주")
    print(f"총 수익률: {(prices[-1] - prices[0]) / prices[0] * 100:+.2f}%")
```

이 예제들을 통해 QB Trading System의 기술적 분석 라이브러리를 다양한 방식으로 활용할 수 있습니다. 실제 운영 환경에서는 실시간 데이터와 연동하여 더욱 강력한 분석 시스템을 구축할 수 있습니다.