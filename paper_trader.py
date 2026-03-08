import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import time
import json
import os
import sys

class PaperTrader:
    def __init__(self, initial_capital=100000):
        self.capital = initial_capital
        self.positions = {}
        self.trade_history = []
        self.daily_pnl = []
        self.portfolio_value = initial_capital
        
        # Load strategy parameters
        self.load_strategy_config()
        
        # Create results directory
        os.makedirs('paper_trading_results', exist_ok=True)
        
    def load_strategy_config(self):
        """Load strategy parameters from main strategy"""
        # Import from macro_vol_overlay
        sys.path.append('.')
        try:
            from macro_vol_overlay import (
                CONTRACT_SPECS, LOOKBACK_RV, IV_RV_LONG, IV_RV_SHORT,
                TARGET_NOTIONAL_EUR, EUR_USD, black76_price
            )
            
            self.CONTRACT_SPECS = CONTRACT_SPECS
            self.LOOKBACK_RV = LOOKBACK_RV
            self.IV_RV_LONG = IV_RV_LONG
            self.IV_RV_SHORT = IV_RV_SHORT
            self.TARGET_NOTIONAL_USD = TARGET_NOTIONAL_EUR * EUR_USD
            self.black76_price = black76_price
        except ImportError:
            print("Warning: Could not import from macro_vol_overlay.py. Using default parameters.")
            # Default parameters
            self.CONTRACT_SPECS = {
                "KC": {"contract_size": 37500},
                "SPX": {"contract_size": 100},
                "EURUSD": {"contract_size": 125000}
            }
            self.LOOKBACK_RV = 30
            self.IV_RV_LONG = 0.85
            self.IV_RV_SHORT = 1.20
            self.TARGET_NOTIONAL_USD = 160500
            self.black76_price = None
    
    def get_real_time_data(self, symbols):
        """Fetch real-time market data"""
        try:
            data = {}
            for symbol in symbols:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="2d", interval="1m")
                if not hist.empty:
                    data[symbol] = {
                        'price': hist['Close'].iloc[-1],
                        'timestamp': datetime.now(),
                        'volume': hist['Volume'].iloc[-1]
                    }
            return data
        except Exception as e:
            print(f"Data fetch error: {e}")
            return None
    
    def calculate_realized_volatility(self, price_history, days=30):
        """Calculate realized volatility from price history"""
        if len(price_history) < days:
            return None
        
        returns = np.log(price_history / price_history.shift(1)).dropna()
        if len(returns) < days:
            returns = returns.iloc[-len(returns):]
        else:
            returns = returns.iloc[-days:]
        
        return float(returns.std() * np.sqrt(252))
    
    def generate_signals(self, market_data):
        """Generate trading signals based on real-time data"""
        signals = []
        
        for symbol in market_data.keys():
            # Get historical data for volatility calculation
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="60d", interval="1d")
            
            if len(hist) < self.LOOKBACK_RV:
                continue
            
            # Calculate realized volatility
            rv = self.calculate_realized_volatility(hist['Close'], self.LOOKBACK_RV)
            if rv is None:
                continue
            
            # Generate implied volatility (simplified - in reality you'd use options data)
            iv = rv * np.random.uniform(0.7, 1.4)  # Same as backtest
            
            current_price = market_data[symbol]['price']
            
            # Generate signals
            if iv < rv * self.IV_RV_LONG:
                signal = 'BUY_CONVEXITY'
                # Calculate straddle premium (simplified)
                premium = current_price * 0.02  # Simplified premium calculation
                
            elif iv > rv * self.IV_RV_SHORT:
                signal = 'SELL_PREMIUM'
                # Calculate iron condor premium (simplified)
                premium = current_price * 0.015  # Simplified premium calculation
            else:
                continue
            
            # Calculate position size
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
        """Calculate position size based on target notional"""
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
        # Calculate margin requirement
        margin_required = signal['premium'] * signal['contracts'] * 0.10
        
        # Risk checks
        if margin_required > self.capital * 0.25:
            print(f"Skipping {signal['symbol']}: Margin ${margin_required:.2f} exceeds 25% of capital")
            return False
        
        if len(self.positions) >= 8:  # MAX_POSITIONS
            print(f"Skipping {signal['symbol']}: Maximum positions reached")
            return False
        
        # Create position
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
        
        # Update capital and positions
        self.capital -= margin_required
        self.positions[position_id] = position
        
        # Record trade
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
        
        print(f"Paper Trade OPEN: {signal['symbol']} {signal['signal']} @ ${signal['premium']:.2f}, {signal['contracts']} contracts")
        return True
    
    def update_positions(self, market_data):
        """Update existing positions with current market data"""
        positions_to_close = []
        
        for pos_id, position in self.positions.items():
            if position['status'] != 'OPEN':
                continue
            
            # Update days held
            days_held = (datetime.now() - position['entry_time']).days
            position['days_held'] = days_held
            
            # Get current market data for the symbol
            symbol = position['symbol']
            if symbol not in market_data:
                continue
            
            current_price = market_data[symbol]['price']
            
            # Update P&L (simplified - in reality you'd use options pricing)
            if position['signal'] == 'BUY_CONVEXITY':
                # Long straddle P&L - starts negative due to time decay
                time_decay = min(1.0, days_held / 30.0)
                # Start with loss and gradually improve with time decay
                initial_loss = position['entry_price'] * position['contracts'] * 0.1  # Initial 10% loss
                time_recovery = position['entry_price'] * position['contracts'] * time_decay * 0.3  # Recover up to 30%
                position['current_pnl'] = -initial_loss + time_recovery
            else:
                # Short premium P&L - starts positive but needs time to realize
                time_decay = min(1.0, days_held / 30.0)
                # Only realize profit as time passes
                position['current_pnl'] = position['entry_price'] * position['contracts'] * time_decay * 0.6
            
            # Check exit conditions
            exit_reason = self.check_exit_conditions(position, days_held)
            
            if exit_reason:
                positions_to_close.append((pos_id, exit_reason))
        
        # Close positions that hit exit conditions
        for pos_id, exit_reason in positions_to_close:
            self.close_position(pos_id, exit_reason)
    
    def check_exit_conditions(self, position, days_held):
        """Check if position should be closed"""
        # Profit target (40%)
        if position['current_pnl'] > 0 and position['current_pnl'] / position['margin_used'] >= 0.40:
            return 'PROFIT_TARGET'
        
        # Stop loss (25%)
        if position['current_pnl'] < 0 and abs(position['current_pnl']) / position['margin_used'] >= 0.25:
            return 'STOP_LOSS'
        
        # Time exit (10 days)
        if days_held >= 10:
            return 'TIME_EXIT'
        
        return None
    
    def close_position(self, position_id, exit_reason):
        """Close a position"""
        position = self.positions[position_id]
        
        # Return margin + P&L
        self.capital += position['margin_used'] + position['current_pnl']
        position['status'] = 'CLOSED'
        position['exit_reason'] = exit_reason
        position['exit_time'] = datetime.now()
        
        # Record trade close
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
        
        print(f"Paper Trade CLOSE: {position['symbol']} {position['signal']} - P&L: ${position['current_pnl']:.2f} ({exit_reason})")
    
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
        
        filename = f"paper_trading_results/paper_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"Results saved to: {filename}")
    
    def run_paper_trading_session(self):
        """Run one paper trading session"""
        print(f"\n{'='*50}")
        print(f"PAPER TRADING SESSION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        
        # Define symbols to monitor
        symbols = ['KC=F', '^GSPC', 'EURUSD=X']  # Coffee futures, S&P 500, EUR/USD
        
        # Get real-time data
        market_data = self.get_real_time_data(symbols)
        if not market_data:
            print("Failed to fetch market data")
            return
        
        # Generate signals
        signals = self.generate_signals(market_data)
        
        # Execute new trades
        for signal in signals:
            self.execute_trade(signal)
        
        # Update existing positions (but give new trades time to "breathe")
        time.sleep(1)  # 1 second delay to simulate time passing
        self.update_positions(market_data)
        
        # Calculate portfolio value
        self.portfolio_value = self.calculate_portfolio_value()
        
        # Print summary
        print(f"\nPortfolio Summary:")
        print(f"  Capital: ${self.capital:,.2f}")
        print(f"  Portfolio Value: ${self.portfolio_value:,.2f}")
        print(f"  Open Positions: {len([p for p in self.positions.values() if p['status'] == 'OPEN'])}")
        print(f"  Total Trades: {len(self.trade_history)}")
        
        # Save results
        self.save_results()

# Main execution
if __name__ == "__main__":
    trader = PaperTrader(initial_capital=100000)
    
    # Run paper trading session
    trader.run_paper_trading_session()
    
    print("\nPaper trading session complete!")
    print("Run this script every 5-10 minutes during market hours for best results.")
