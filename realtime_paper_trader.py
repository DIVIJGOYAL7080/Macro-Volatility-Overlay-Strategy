import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import time
import json
import os
import sys

class RealTimePaperTrader:
    def __init__(self, initial_capital=100000):
        self.capital = initial_capital
        self.positions = {}
        self.trade_history = []
        self.price_history = {}  # Store price history
        self.running = True
        
        # Load strategy parameters
        self.load_strategy_config()
        
        # Create results directory
        os.makedirs('paper_trading_results', exist_ok=True)
        
        print("🚀 Real-Time Paper Trader Started")
        print("Press Ctrl+C to stop trading")
        print("="*50)
        
    def load_strategy_config(self):
        """Load strategy parameters"""
        try:
            from macro_vol_overlay import (
                CONTRACT_SPECS, LOOKBACK_RV, IV_RV_LONG, IV_RV_SHORT,
                TARGET_NOTIONAL_EUR, EUR_USD
            )
            self.CONTRACT_SPECS = CONTRACT_SPECS
            self.LOOKBACK_RV = LOOKBACK_RV
            self.IV_RV_LONG = IV_RV_LONG
            self.IV_RV_SHORT = IV_RV_SHORT
            self.TARGET_NOTIONAL_USD = TARGET_NOTIONAL_EUR * EUR_USD
        except ImportError:
            # Default parameters
            self.CONTRACT_SPECS = {"KC": {"contract_size": 37500}, "SPX": {"contract_size": 100}, "EURUSD": {"contract_size": 125000}}
            self.LOOKBACK_RV = 30
            self.IV_RV_LONG = 0.85
            self.IV_RV_SHORT = 1.20
            self.TARGET_NOTIONAL_USD = 160500
    
    def get_market_data(self, symbols):
        """Get real-time market data and update history"""
        try:
            data = {}
            for symbol in symbols:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1d", interval="1m")
                
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                    timestamp = datetime.now()
                    
                    # Store price history
                    if symbol not in self.price_history:
                        self.price_history[symbol] = []
                    
                    self.price_history[symbol].append({
                        'price': current_price,
                        'timestamp': timestamp,
                        'volume': hist['Volume'].iloc[-1]
                    })
                    
                    # Keep only last 100 data points
                    if len(self.price_history[symbol]) > 100:
                        self.price_history[symbol] = self.price_history[symbol][-100:]
                    
                    data[symbol] = {
                        'price': current_price,
                        'timestamp': timestamp,
                        'volume': hist['Volume'].iloc[-1]
                    }
            
            return data
        except Exception as e:
            print(f"❌ Data fetch error: {e}")
            return None
    
    def calculate_realized_volatility(self, symbol, days=30):
        """Calculate realized volatility from price history"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 10:
            return None
        
        prices = [p['price'] for p in self.price_history[symbol]]
        price_series = pd.Series(prices)
        
        if len(price_series) < 2:
            return None
        
        returns = np.log(price_series / price_series.shift(1)).dropna()
        if len(returns) == 0:
            return None
        
        # Use available data points, scale to 30 days
        available_days = len(returns)
        scaling_factor = np.sqrt(30 / available_days) if available_days > 0 else 1
        
        return float(returns.std() * np.sqrt(252) * scaling_factor)
    
    def generate_signals(self, market_data):
        """Generate trading signals based on real-time data"""
        signals = []
        
        for symbol, data in market_data.items():
            # Calculate realized volatility
            rv = self.calculate_realized_volatility(symbol)
            if rv is None:
                continue
            
            # Generate implied volatility
            iv = rv * np.random.uniform(0.7, 1.4)
            current_price = data['price']
            
            # Generate signals
            if iv < rv * self.IV_RV_LONG:
                signal = 'BUY_CONVEXITY'
                premium = current_price * 0.02
            elif iv > rv * self.IV_RV_SHORT:
                signal = 'SELL_PREMIUM'
                premium = current_price * 0.015
            else:
                continue
            
            contracts = self.size_position(symbol, current_price)
            
            signals.append({
                'symbol': symbol,
                'signal': signal,
                'price': current_price,
                'premium': premium,
                'contracts': contracts,
                'iv': iv,
                'rv': rv,
                'timestamp': datetime.now()
            })
        
        return signals
    
    def size_position(self, symbol, current_price):
        """Calculate position size"""
        if 'KC' in symbol:
            contract_size = 37500
        elif 'SPX' in symbol or '^GSPC' in symbol:
            contract_size = 100
        elif 'EUR' in symbol:
            contract_size = 125000
        else:
            contract_size = 1
        
        notional_per_contract = current_price * contract_size
        return max(1, int(round(self.TARGET_NOTIONAL_USD / notional_per_contract)))
    
    def execute_trade(self, signal):
        """Execute trade in paper trading account"""
        margin_required = signal['premium'] * signal['contracts'] * 0.10
        
        if margin_required > self.capital * 0.25:
            print(f"⏭️  Skipping {signal['symbol']}: Margin ${margin_required:.2f} exceeds 25% of capital")
            return False
        
        if len(self.positions) >= 8:
            print(f"⏭️  Skipping {signal['symbol']}: Maximum positions reached")
            return False
        
        position_id = len(self.positions) + 1
        
        position = {
            'id': position_id,
            'symbol': signal['symbol'],
            'signal': signal['signal'],
            'entry_price': signal['premium'],
            'contracts': signal['contracts'],
            'margin_used': margin_required,
            'entry_time': signal['timestamp'],
            'iv_entry': signal['iv'],
            'rv_entry': signal['rv'],
            'days_held': 0,
            'current_pnl': 0,
            'status': 'OPEN'
        }
        
        self.capital -= margin_required
        self.positions[position_id] = position
        
        trade_record = {
            'timestamp': signal['timestamp'],
            'action': 'OPEN',
            'position_id': position_id,
            'symbol': signal['symbol'],
            'signal': signal['signal'],
            'premium': signal['premium'],
            'contracts': signal['contracts'],
            'margin_used': margin_required,
            'capital_remaining': self.capital
        }
        
        self.trade_history.append(trade_record)
        
        print(f"📈 OPEN: {signal['symbol']} {signal['signal']} @ ${signal['premium']:.2f}, {signal['contracts']} contracts")
        return True
    
    def update_positions(self, market_data):
        """Update existing positions with real market data"""
        positions_to_close = []
        
        for pos_id, position in self.positions.items():
            if position['status'] != 'OPEN':
                continue
            
            # Update days held
            days_held = (datetime.now() - position['entry_time']).days
            position['days_held'] = days_held
            
            # Get current market data
            symbol = position['symbol']
            if symbol not in market_data:
                continue
            
            current_price = market_data[symbol]['price']
            
            # Update P&L based on real price movement
            if position['signal'] == 'BUY_CONVEXITY':
                # Long straddle P&L based on price movement
                price_change = (current_price - position['entry_price']) / position['entry_price']
                time_decay = min(1.0, days_held / 30.0)
                position['current_pnl'] = position['entry_price'] * position['contracts'] * (price_change * 2 - time_decay * 0.1)
            else:
                # Short premium P&L
                time_decay = min(1.0, days_held / 30.0)
                position['current_pnl'] = position['entry_price'] * position['contracts'] * time_decay * 0.6
            
            # Check exit conditions
            exit_reason = self.check_exit_conditions(position, days_held)
            
            if exit_reason:
                positions_to_close.append((pos_id, exit_reason))
        
        # Close positions
        for pos_id, exit_reason in positions_to_close:
            self.close_position(pos_id, exit_reason)
    
    def check_exit_conditions(self, position, days_held):
        """Check if position should be closed"""
        margin_used = position['margin_used']
        
        if margin_used > 0:
            pnl_pct = position['current_pnl'] / margin_used
            
            if pnl_pct >= 0.40:
                return 'PROFIT_TARGET'
            elif pnl_pct <= -0.25:
                return 'STOP_LOSS'
        
        if days_held >= 10:
            return 'TIME_EXIT'
        
        return None
    
    def close_position(self, position_id, exit_reason):
        """Close a position"""
        position = self.positions[position_id]
        
        self.capital += position['margin_used'] + position['current_pnl']
        position['status'] = 'CLOSED'
        position['exit_reason'] = exit_reason
        position['exit_time'] = datetime.now()
        
        trade_record = {
            'timestamp': datetime.now(),
            'action': 'CLOSE',
            'position_id': position_id,
            'symbol': position['symbol'],
            'signal': position['signal'],
            'exit_reason': exit_reason,
            'final_pnl': position['current_pnl'],
            'capital_remaining': self.capital
        }
        
        self.trade_history.append(trade_record)
        
        pnl_emoji = "🟢" if position['current_pnl'] > 0 else "🔴"
        print(f"{pnl_emoji} CLOSE: {position['symbol']} {position['signal']} - P&L: ${position['current_pnl']:.2f} ({exit_reason})")
    
    def calculate_portfolio_value(self):
        """Calculate total portfolio value"""
        unrealized_pnl = sum(pos['current_pnl'] for pos in self.positions.values() if pos['status'] == 'OPEN')
        return self.capital + unrealized_pnl
    
    def save_results(self):
        """Save paper trading results"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'capital': self.capital,
            'portfolio_value': self.calculate_portfolio_value(),
            'open_positions': len([p for p in self.positions.values() if p['status'] == 'OPEN']),
            'total_trades': len(self.trade_history),
            'trade_history': self.trade_history,
            'positions': {k: v for k, v in self.positions.items()}
        }
        
        filename = f"paper_trading_results/realtime_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
    
    def print_status(self):
        """Print current trading status"""
        portfolio_value = self.calculate_portfolio_value()
        open_positions = len([p for p in self.positions.values() if p['status'] == 'OPEN'])
        
        print(f"\n📊 Status Update:")
        print(f"   Capital: ${self.capital:,.2f}")
        print(f"   Portfolio: ${portfolio_value:,.2f}")
        print(f"   Open Positions: {open_positions}")
        print(f"   Total Trades: {len(self.trade_history)}")
        
        if open_positions > 0:
            print(f"\n📈 Open Positions:")
            for pos in self.positions.values():
                if pos['status'] == 'OPEN':
                    days_held = (datetime.now() - pos['entry_time']).days
                    pnl_emoji = "🟢" if pos['current_pnl'] > 0 else "🔴"
                    print(f"   {pnl_emoji} {pos['symbol']} {pos['signal']}: ${pos['current_pnl']:+.2f} ({days_held} days)")
    
    def run_continuous_trading(self):
        """Run continuous paper trading"""
        symbols = ['KC=F', '^GSPC', 'EURUSD=X']
        
        try:
            while self.running:
                print(f"\n{'='*60}")
                print(f"🔄 Trading Session: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*60}")
                
                # Get market data
                market_data = self.get_market_data(symbols)
                if not market_data:
                    print("❌ Failed to fetch market data, retrying...")
                    time.sleep(30)
                    continue
                
                # Generate and execute signals
                signals = self.generate_signals(market_data)
                for signal in signals:
                    self.execute_trade(signal)
                
                # Update existing positions
                self.update_positions(market_data)
                
                # Print status
                self.print_status()
                
                # Save results every 10 minutes
                if len(self.trade_history) % 5 == 0:
                    self.save_results()
                
                # Wait for next update
                print(f"\n⏰ Next update in 60 seconds...")
                time.sleep(60)
                
        except KeyboardInterrupt:
            print(f"\n\n🛑 Trading stopped by user")
            self.save_results()
            print(f"💾 Results saved")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            self.save_results()

# Main execution
if __name__ == "__main__":
    trader = RealTimePaperTrader(initial_capital=100000)
    trader.run_continuous_trading()
