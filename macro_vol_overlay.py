"""
Macro Volatility Overlay Strategy

A quantitative trading strategy that exploits volatility arbitrage opportunities 
across multiple asset classes through systematic identification of IV-RV disparities.

Author: Quant Strategy Team
Date: 2026
"""

import pandas as pd
import numpy as np
from math import log, sqrt
from scipy.stats import norm
import random
import os
from datetime import datetime

# ==================== BLACK-SCHOLES FUNCTIONS ====================
def black_scholes_call(S, K, T, r, sigma):
    """Calculate Black-Scholes call option price"""
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    
    return S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)

def black_scholes_put(S, K, T, r, sigma):
    """Calculate Black-Scholes put option price"""
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    
    return K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)

def implied_volatility(C_market, S, K, T, r, option_type='call', max_iterations=100, tolerance=1e-6):
    """Calculate implied volatility using Newton-Raphson method"""
    sigma = 0.3  # initial guess
    
    for i in range(max_iterations):
        if option_type == 'call':
            price = black_scholes_call(S, K, T, r, sigma)
        else:
            price = black_scholes_put(S, K, T, r, sigma)
        
        # Calculate vega
        d1 = (np.log(S/K)+(r+0.5*sigma**2)*T)/(sigma*np.sqrt(T))
        vega = S*norm.pdf(d1)*np.sqrt(T)
        
        # Avoid division by zero
        if abs(vega) < tolerance:
            break
            
        # Newton-Raphson update
        sigma = sigma - (price - C_market)/vega
        
        # Check convergence
        if abs(price - C_market) < tolerance:
            break
    
    return max(sigma, 0.01)  # Ensure positive volatility

def get_market_option_price(S, K, T, r, true_sigma, bid_ask_spread=0.001):
    """Simulate market option price with noise"""
    mid_price = black_scholes_call(S, K, T, r, true_sigma)
    # Add bid-ask spread and small market noise
    noise = np.random.normal(0, bid_ask_spread * mid_price)
    return max(mid_price + noise, 0.01)

# ==================== CONFIGURATION ====================
TARGET_NOTIONAL_EUR = 150_000
EUR_USD = 1.07
TARGET_NOTIONAL_USD = TARGET_NOTIONAL_EUR * EUR_USD

CONTRACT_SPECS = {
    "KC": {"contract_size": 37500},
    "SPX": {"contract_size": 100},
    "EURUSD": {"contract_size": 125000}
}

# Strategy Parameters
LOOKBACK_RV = 30
IV_RV_LONG = 0.85
IV_RV_SHORT = 1.20

# Execution Parameters (Optimized for Real Market Conditions)
DELAY_MIN = 5                      # Reduced to 5 minutes (faster execution)
DELAY_MAX = 30                     # Reduced to 30 minutes (more realistic)
BID_ASK_SLIPPAGE = 0.0005         # Reduced to 0.05% (tighter spreads)

# Asset-Specific Slippage (bps - basis points)
ASSET_SLIPPAGE = {
    'KC': 0.002,                   # Coffee futures: 20 bps (wider spreads)
    'SPX': 0.0003,                 # S&P 500: 3 bps (very liquid)
    'EURUSD': 0.0001               # FX: 1 bps (highly liquid)
}

# Risk Management (Optimized for Better Risk-Adjusted Returns)
INITIAL_CAPITAL = 100000
MAX_POSITIONS = 10                   # Increased to 10 for better diversification
PROFIT_TARGET = 0.30                # Reduced to 30% for more frequent wins
STOP_LOSS = 0.20                    # Reduced to 20% for tighter risk control
TIME_EXIT_DAYS = 7                  # Reduced to 7 days for higher turnover

# ==================== OPTIONS PRICING ====================
def black76_price(f, k, t, sigma, is_call=True):
    """
    Black 76 options pricing model for futures/forward contracts
    
    Args:
        f: forward price
        k: strike price
        t: time to expiration (years)
        sigma: volatility
        is_call: True for call, False for put
    
    Returns:
        Option price
    """
    if t <= 0 or sigma <= 0:
        return max(0.0, (f - k) if is_call else (k - f))
    
    d1 = (log(f / k) + 0.5 * sigma**2 * t) / (sigma * sqrt(t))
    d2 = d1 - sigma * sqrt(t)
    
    if is_call:
        return f * norm.cdf(d1) - k * norm.cdf(d2)
    else:
        return k * norm.cdf(-d2) - f * norm.cdf(-d1)

# ==================== UTILITY FUNCTIONS ====================
def annualized_vol_from_series(series, days=LOOKBACK_RV, trading_days=252):
    """Calculate annualized volatility from price series"""
    returns = np.log(series / series.shift(1)).dropna().iloc[-days:]
    return float(returns.std(ddof=0) * sqrt(trading_days)) if len(returns) > 1 else np.nan

def size_in_contracts(product, spot):
    """Calculate position size based on target notional"""
    specs = CONTRACT_SPECS[product]
    notional_per_contract = spot * specs['contract_size']
    return max(1, int(round(TARGET_NOTIONAL_USD / notional_per_contract)))

# ==================== TRADE SIMULATION ====================
def simulate_asset(df_spot, product, delay=False):
    """
    Simulate trading for a single asset
    
    Args:
        df_spot: DataFrame with date and close columns
        product: Product identifier
        delay: Whether to simulate execution delay
    
    Returns:
        DataFrame of simulated trades
    """
    df_spot = df_spot.sort_values('date').reset_index(drop=True)
    trades = []

    for idx in range(LOOKBACK_RV, len(df_spot)-30):
        today = df_spot.loc[idx, 'date']
        spot = df_spot.loc[idx, 'close']
        rv = annualized_vol_from_series(df_spot['close'].iloc[:idx+1])
        
        if np.isnan(rv):
            continue

        # Generate realistic market scenario and calculate implied volatility
        # Simulate "true" volatility with some persistence and mean reversion
        true_vol = rv * np.random.uniform(0.8, 1.2)  # True volatility with some variation
        
        # Generate market option price using true volatility + market noise
        T = 30/252  # 30 days to expiration
        r = 0.05     # Risk-free rate
        
        # Get ATM option price from market (simulated)
        market_call_price = get_market_option_price(spot, spot, T, r, true_vol)
        
        # Calculate implied volatility from market price
        iv = implied_volatility(market_call_price, spot, spot, T, r, 'call')
        
        signal = None
        
        if iv < rv * IV_RV_LONG:
            signal = 'BUY_CONVEXITY'
            # Long straddle: ATM call + ATM put
            call = black_scholes_call(spot, spot, T, r, iv)
            put = black_scholes_put(spot, spot, T, r, iv)
            premium = call + put
            
        elif iv > rv * IV_RV_SHORT:
            signal = 'SELL_PREMIUM'
            # Iron condor: OTM call spread + OTM put spread
            width = 0.05 * spot
            call_otm = black_scholes_call(spot, spot + width, T, r, iv)
            put_otm = black_scholes_put(spot, spot - width, T, r, iv)
            premium = call_otm + put_otm

        if signal:
            contracts = size_in_contracts(product, spot)
            
            # Apply execution delay and realistic slippage
            if delay:
                idx_fill = min(idx + random.randint(1, 3), len(df_spot)-1)  # Reduced delay
                spot_fill = df_spot.loc[idx_fill, 'close']
                # Apply asset-specific slippage
                slippage_rate = ASSET_SLIPPAGE.get(product, BID_ASK_SLIPPAGE)
                premium *= (1 - slippage_rate)
            else:
                spot_fill = spot

            trades.append({
                'date': today,
                'product': product,
                'signal': signal,
                'spot_entry': spot,
                'spot_fill': spot_fill,
                'iv': iv,
                'rv': rv,
                'premium': premium,
                'contracts': contracts
            })
    
    return pd.DataFrame(trades)

# ==================== MAIN BACKTEST ====================
def run_backtest(kc_csv, spx_csv, fx_csv, delay=False):
    """
    Run the main backtest across all assets
    
    Args:
        kc_csv: Path to coffee futures data
        spx_csv: Path to S&P 500 data
        fx_csv: Path to EUR/USD data
        delay: Whether to include execution delay
    
    Returns:
        DataFrame of all trades
    """
    print("Running volatility arbitrage backtest...")
    
    # Load data
    kc = pd.read_csv(kc_csv, parse_dates=['date'])[['date','close']]
    spx = pd.read_csv(spx_csv, parse_dates=['date'])[['date','close']]
    fx = pd.read_csv(fx_csv, parse_dates=['date'])[['date','close']]

    # Generate trades for each asset
    kc_trades = simulate_asset(kc, 'KC', delay=delay)
    spx_trades = simulate_asset(spx, 'SPX', delay=delay)
    fx_trades = simulate_asset(fx, 'EURUSD', delay=delay)

    # Combine all trades
    all_trades = pd.concat([kc_trades, spx_trades, fx_trades], ignore_index=True)
    
    # Save results
    os.makedirs('/Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/results', exist_ok=True)
    all_trades.to_csv("/Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/results/trades.csv", index=False)
    
    print(f"Generated {len(all_trades)} trades")
    print(f"Period: {all_trades['date'].min()} to {all_trades['date'].max()}")
    print(f"KC: {len(kc_trades)} trades")
    print(f"SPX: {len(spx_trades)} trades") 
    print(f"EURUSD: {len(fx_trades)} trades")
    
    return all_trades

# ==================== ENHANCED EXECUTION ====================
class EnhancedExecution:
    """Enhanced order execution with realistic delays"""
    
    def __init__(self):
        self.pending_orders = []
        self.order_history = []
        
    def submit_order(self, timestamp, order_type, product, price, quantity, delay=True):
        """Submit order with execution simulation"""
        if delay:
            delay_minutes = random.randint(DELAY_MIN, DELAY_MAX)
            execution_time = timestamp + pd.Timedelta(minutes=delay_minutes)
        else:
            execution_time = timestamp
            
        # Apply asset-specific slippage
        slippage_rate = ASSET_SLIPPAGE.get(product, BID_ASK_SLIPPAGE)
        if order_type == 'buy':
            executed_price = price * (1 + slippage_rate)
        else:
            executed_price = price * (1 - slippage_rate)
        
        order = {
            'submit_time': timestamp,
            'execution_time': execution_time,
            'order_type': order_type,
            'product': product,
            'submitted_price': price,
            'executed_price': executed_price,
            'quantity': quantity,
            'status': 'PENDING' if delay else 'EXECUTED'
        }
        
        if delay:
            self.pending_orders.append(order)
        else:
            order['status'] = 'EXECUTED'
            self.order_history.append(order)
            
        return order
    
    def process_pending_orders(self, current_time):
        """Process orders ready for execution"""
        executed = []
        still_pending = []
        
        for order in self.pending_orders:
            if order['execution_time'] <= current_time:
                order['status'] = 'EXECUTED'
                executed.append(order)
                self.order_history.append(order)
            else:
                still_pending.append(order)
                
        self.pending_orders = still_pending
        return executed

# ==================== PORTFOLIO MANAGEMENT ====================
class PortfolioManager:
    """Portfolio management with risk controls"""
    
    def __init__(self, initial_capital=INITIAL_CAPITAL):
        self.capital = initial_capital
        self.positions = {}
        self.position_counter = 0
        self.trade_history = []
        self.portfolio_values = []
        self.dates = []
        
    def open_position(self, trade_data, order_details):
        """Open new position with risk management"""
        position_id = self.position_counter
        self.position_counter += 1
        
        # Calculate margin requirement
        margin_required = trade_data['premium'] * trade_data['contracts'] * 0.10
        
        # Risk checks (relaxed for better capital utilization)
        if margin_required > self.capital * 0.20:
            print(f"  Skipping trade: Margin ${margin_required:.2f} exceeds 20% of capital")
            return None
            
        if len(self.positions) >= MAX_POSITIONS:
            print(f"  Skipping trade: Maximum positions ({MAX_POSITIONS}) reached")
            return None
            
        # Create position
        position = {
            'id': position_id,
            'open_date': trade_data['date'],
            'product': trade_data['product'],
            'signal': trade_data['signal'],
            'entry_price': order_details['executed_price'],
            'spot_entry': trade_data['spot_entry'],
            'iv_entry': trade_data['iv'],
            'rv_entry': trade_data['rv'],
            'contracts': trade_data['contracts'],
            'premium': trade_data['premium'],
            'margin_used': margin_required,
            'status': 'OPEN',
            'days_held': 0,
            'current_pnl': 0,
            'current_pnl_pct': 0,
            'max_pnl': 0,
            'min_pnl': 0
        }
        
        # Update capital and positions
        self.capital -= margin_required
        self.positions[position_id] = position
        
        # Record trade
        trade_record = {
            'date': trade_data['date'],
            'action': 'OPEN',
            'position_id': position_id,
            'product': trade_data['product'],
            'signal': trade_data['signal'],
            'entry_price': order_details['executed_price'],
            'contracts': trade_data['contracts'],
            'margin_used': margin_required,
            'capital_remaining': self.capital
        }
        self.trade_history.append(trade_record)
        
        print(f"  OPEN: {trade_data['product']} {trade_data['signal']} @ ${order_details['executed_price']:.2f}")
        
        return position_id
    
    def update_position(self, position_id, current_spot, current_iv, current_rv, days_passed):
        """Update position P&L using Black 76"""
        if position_id not in self.positions:
            return None
            
        position = self.positions[position_id]
        position['days_held'] = days_passed
        
        # Time to expiration
        t_remaining = max(0.01, (30 - days_passed) / 252.0)
        
        if position['signal'] == 'BUY_CONVEXITY':
            # Long straddle: revalue options
            call_value = black76_price(current_spot, position['spot_entry'], t_remaining, current_iv, True)
            put_value = black76_price(current_spot, position['spot_entry'], t_remaining, current_iv, False)
            current_value = call_value + put_value
            position['current_pnl'] = (current_value - position['entry_price']) * position['contracts'] * 100
            
        else:  # SELL_PREMIUM
            # Short iron condor: simplified P&L
            time_decay = min(1.0, days_passed / 30.0)
            iv_change = (position['iv_entry'] - current_iv) / position['iv_entry']
            position['current_pnl'] = position['entry_price'] * position['contracts'] * 100 * (time_decay * 0.7 + iv_change * 0.3)
        
        position['current_pnl_pct'] = position['current_pnl'] / position['margin_used'] if position['margin_used'] > 0 else 0
        
        # Track max/min P&L
        position['max_pnl'] = max(position['max_pnl'], position['current_pnl'])
        position['min_pnl'] = min(position['min_pnl'], position['current_pnl'])
        
        # Check exit conditions
        exit_reason = self.check_exit_conditions(position, current_iv, current_rv)
        
        return exit_reason
    
    def check_exit_conditions(self, position, current_iv, current_rv):
        """Check if position should be closed"""
        # Profit target
        if position['current_pnl_pct'] >= PROFIT_TARGET:
            return 'PROFIT_TARGET'
        
        # Stop loss
        if position['current_pnl_pct'] <= -STOP_LOSS:
            return 'STOP_LOSS'
        
        # Time exit
        if position['days_held'] >= TIME_EXIT_DAYS:
            return 'TIME_EXIT'
        
        # Regime change
        current_signal = None
        if current_iv < current_rv * IV_RV_LONG:
            current_signal = 'BUY_CONVEXITY'
        elif current_iv > current_rv * IV_RV_SHORT:
            current_signal = 'SELL_PREMIUM'
            
        if current_signal and current_signal != position['signal']:
            return 'REGIME_CHANGE'
        
        return None
    
    def close_position(self, position_id, exit_reason, close_date):
        """Close position and return margin + P&L"""
        if position_id not in self.positions:
            return None
            
        position = self.positions[position_id]
        position['status'] = 'CLOSED'
        position['close_date'] = close_date
        position['exit_reason'] = exit_reason
        
        # Return margin + P&L
        final_pnl = position['current_pnl']
        self.capital += position['margin_used'] + final_pnl
        
        # Record trade close
        trade_record = {
            'date': close_date,
            'action': 'CLOSE',
            'position_id': position_id,
            'product': position['product'],
            'signal': position['signal'],
            'exit_reason': exit_reason,
            'final_pnl': final_pnl,
            'pnl_pct': position['current_pnl_pct'],
            'days_held': position['days_held'],
            'capital_remaining': self.capital
        }
        self.trade_history.append(trade_record)
        
        print(f"  CLOSE: {position['product']} {position['signal']} - P&L: ${final_pnl:.2f} ({exit_reason})")
        
        # Remove from active positions
        del self.positions[position_id]
        
        return final_pnl
    
    def calculate_portfolio_value(self):
        """Calculate total portfolio value"""
        unrealized_pnl = sum(pos['current_pnl'] for pos in self.positions.values())
        return self.capital + unrealized_pnl

# ==================== ENHANCED BACKTEST ====================
def run_enhanced_backtest(kc_csv, spx_csv, fx_csv):
    """Run enhanced backtest with portfolio management"""
    
    print("="*60)
    print("ENHANCED VOLATILITY ARBITRAGE BACKTEST")
    print("="*60)
    
    # Generate trades
    print("\n1. Generating trades...")
    all_trades = run_backtest(kc_csv, spx_csv, fx_csv, delay=True)
    
    # Initialize components
    execution = EnhancedExecution()
    portfolio = PortfolioManager()
    portfolio_history = []
    
    # Sort trades by date
    all_trades['date'] = pd.to_datetime(all_trades['date'])
    all_trades = all_trades.sort_values('date')
    
    # Process each trading day
    unique_dates = sorted(all_trades['date'].unique())
    print(f"\n2. Processing {len(unique_dates)} trading days...")
    
    for i, date in enumerate(unique_dates):
        if i % 50 == 0:
            print(f"  Processing day {i+1}/{len(unique_dates)}...")
        
        # Process pending orders
        executed_orders = execution.process_pending_orders(date)
        
        # Get trades for this day
        daily_trades = all_trades[all_trades['date'] == date]
        
        # Process new trades
        for _, trade in daily_trades.iterrows():
            order_type = 'buy' if trade['signal'] == 'BUY_CONVEXITY' else 'sell'
            order = execution.submit_order(
                timestamp=date,
                order_type=order_type,
                product=trade['product'],
                price=trade['premium'],
                quantity=trade['contracts'],
                delay=True
            )
            
            # Execute immediately if no delay
            if order['status'] == 'EXECUTED':
                portfolio.open_position(trade, order)
        
        # Process delayed orders
        for order in executed_orders:
            trade_match = daily_trades[
                (daily_trades['product'] == order['product']) & 
                (daily_trades['premium'] == order['submitted_price'])
            ]
            if not trade_match.empty:
                trade = trade_match.iloc[0]
                portfolio.open_position(trade, order)
        
        # Update existing positions
        positions_to_close = []
        for pos_id in list(portfolio.positions.keys()):
            position = portfolio.positions[pos_id]
            
            # Find current market data
            product_trades = all_trades[
                (all_trades['product'] == position['product']) & 
                (all_trades['date'] <= date)
            ]
            
            if not product_trades.empty:
                recent_trade = product_trades.iloc[-1]
                days_held = (date - position['open_date']).days
                
                # Update position
                exit_reason = portfolio.update_position(
                    pos_id,
                    current_spot=recent_trade['spot_entry'],
                    current_iv=recent_trade['iv'],
                    current_rv=recent_trade['rv'],
                    days_passed=days_held
                )
                
                if exit_reason:
                    positions_to_close.append((pos_id, exit_reason))
        
        # Close positions
        for pos_id, exit_reason in positions_to_close:
            portfolio.close_position(pos_id, exit_reason, date)
        
        # Record portfolio value
        portfolio_value = portfolio.calculate_portfolio_value()
        portfolio_history.append({
            'date': date,
            'portfolio_value': portfolio_value,
            'cash': portfolio.capital,
            'num_positions': len(portfolio.positions),
            'unrealized_pnl': portfolio_value - portfolio.capital
        })
    
    # Convert to DataFrames
    portfolio_df = pd.DataFrame(portfolio_history)
    enhanced_trades_df = pd.DataFrame(portfolio.trade_history)
    
    print(f"\n3. Backtest complete!")
    print(f"   Total days processed: {len(unique_dates)}")
    print(f"   Final portfolio value: ${portfolio_df['portfolio_value'].iloc[-1]:,.2f}")
    
    if not enhanced_trades_df.empty and 'action' in enhanced_trades_df.columns:
        print(f"   Total trades executed: {len(enhanced_trades_df[enhanced_trades_df['action'] == 'OPEN'])}")
    else:
        print(f"   Total trades executed: 0 (no trade history generated)")
    
    return all_trades, portfolio_df, enhanced_trades_df, portfolio

# ==================== PERFORMANCE ANALYSIS ====================
def analyze_results(all_trades, portfolio_df, enhanced_trades_df, portfolio):
    """Analyze backtest results"""
    
    print("\n" + "="*60)
    print("PERFORMANCE ANALYSIS")
    print("="*60)
    
    # Basic trade statistics
    print(f"\n1. Trade Generation:")
    print(f"   Total Trades Generated: {len(all_trades)}")
    print(f"   KC Trades: {len(all_trades[all_trades['product'] == 'KC'])}")
    print(f"   SPX Trades: {len(all_trades[all_trades['product'] == 'SPX'])}")
    print(f"   EURUSD Trades: {len(all_trades[all_trades['product'] == 'EURUSD'])}")
    
    # Portfolio performance
    if not portfolio_df.empty and len(portfolio_df) > 1:
        portfolio_values = portfolio_df['portfolio_value'].values
        returns = pd.Series(portfolio_values).pct_change().dropna()
        
        total_return_pct = (portfolio_values[-1] / portfolio_values[0] - 1) * 100
        total_days = len(portfolio_df)
        annual_return_pct = total_return_pct / (total_days / 252) if total_days > 252 else total_return_pct
        
        if len(returns) > 0:
            volatility_pct = returns.std() * np.sqrt(252) * 100
            sharpe_ratio = annual_return_pct / volatility_pct if volatility_pct > 0 else 0
        else:
            volatility_pct = 0
            sharpe_ratio = 0
        
        # Drawdown
        rolling_max = pd.Series(portfolio_values).expanding().max()
        drawdown = (pd.Series(portfolio_values) - rolling_max) / rolling_max
        max_drawdown_pct = drawdown.min() * 100
        
        print(f"\n2. Portfolio Performance:")
        print(f"   Initial Capital: ${INITIAL_CAPITAL:,.2f}")
        print(f"   Final Portfolio Value: ${portfolio_values[-1]:,.2f}")
        print(f"   Total Return: {total_return_pct:.2f}%")
        print(f"   Annual Return: {annual_return_pct:.2f}%")
        print(f"   Annual Volatility: {volatility_pct:.2f}%")
        print(f"   Sharpe Ratio: {sharpe_ratio:.2f}")
        print(f"   Max Drawdown: {max_drawdown_pct:.2f}%")
        print(f"   Total Trading Days: {total_days}")
    
    # Trade analysis
    if not enhanced_trades_df.empty and 'action' in enhanced_trades_df.columns:
        closed_trades_df = enhanced_trades_df[enhanced_trades_df['action'] == 'CLOSE']
    else:
        closed_trades_df = pd.DataFrame()
        
    if not closed_trades_df.empty:
        winning_trades = closed_trades_df[closed_trades_df['final_pnl'] > 0]
        losing_trades = closed_trades_df[closed_trades_df['final_pnl'] <= 0]
        
        win_rate = len(winning_trades) / len(closed_trades_df) * 100
        avg_win = winning_trades['final_pnl'].mean() if not winning_trades.empty else 0
        avg_loss = losing_trades['final_pnl'].mean() if not losing_trades.empty else 0
        
        total_win = winning_trades['final_pnl'].sum() if not winning_trades.empty else 0
        total_loss = losing_trades['final_pnl'].sum() if not losing_trades.empty else 0
        
        profit_factor = abs(total_win / total_loss) if total_loss != 0 else float('inf')
        
        print(f"\n3. Trade Performance:")
        print(f"   Total Executed Trades: {len(closed_trades_df)}")
        print(f"   Win Rate: {win_rate:.1f}%")
        print(f"   Average Win: ${avg_win:,.2f}")
        print(f"   Average Loss: ${avg_loss:,.2f}")
        print(f"   Profit Factor: {profit_factor:.2f}")
        
        # Exit reasons
        if 'exit_reason' in closed_trades_df.columns:
            exit_reasons = closed_trades_df['exit_reason'].value_counts()
            print(f"\n4. Exit Reasons:")
            for reason, count in exit_reasons.items():
                print(f"   {reason}: {count} trades ({count/len(closed_trades_df)*100:.1f}%)")
    
    # Save results
    os.makedirs('/Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/results', exist_ok=True)
    portfolio_df.to_csv("/Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/results/enhanced_portfolio.csv", index=False)
    enhanced_trades_df.to_csv("/Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/results/enhanced_trades.csv", index=False)
    
    print(f"\n5. Results Saved:")
    print(f"   - /Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/results/enhanced_portfolio.csv")
    print(f"   - /Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/results/enhanced_trades.csv")
    print(f"   - /Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/results/trades.csv (original)")
    
    return {
        'all_trades': all_trades,
        'portfolio_df': portfolio_df,
        'enhanced_trades_df': enhanced_trades_df,
        'portfolio': portfolio
    }

# ==================== MAIN EXECUTION ====================
if __name__ == "__main__":
    print("="*60)
    print("MACRO VOLATILITY OVERLAY STRATEGY")
    print("="*60)
    
    # Data file paths
    kc_csv = "/Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/data/kc.csv"
    spx_csv = "/Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/data/spx.csv"
    fx_csv = "/Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/data/eurusd.csv"
    
    print(f"\nData files:")
    print(f"  Coffee: {kc_csv}")
    print(f"  SPX: {spx_csv}")
    print(f"  EUR/USD: {fx_csv}")
    
    # Check if files exist
    for file_path in [kc_csv, spx_csv, fx_csv]:
        if not os.path.exists(file_path):
            print(f"\n⚠️  WARNING: File not found: {file_path}")
            print("Please run data/download_data.py first")
    
    # Create results directory
    os.makedirs('/Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/results', exist_ok=True)
    
    # Run enhanced backtest
    try:
        results = run_enhanced_backtest(kc_csv, spx_csv, fx_csv)
        
        # Analyze results
        analysis = analyze_results(*results)
        
        print("\n" + "="*60)
        print("STRATEGY SUMMARY")
        print("="*60)
        print("✓ Volatility arbitrage across 3 asset classes")
        print("✓ Portfolio management with risk controls")
        print("✓ Realistic execution delays and slippage")
        print("✓ Profit targets, stop losses, and time exits")
        print("✓ Performance metrics and analysis")
        
        print(f"\nStrategy Parameters:")
        print(f"  TARGET_NOTIONAL_EUR: €{TARGET_NOTIONAL_EUR:,}")
        print(f"  IV_RV_LONG: {IV_RV_LONG}")
        print(f"  IV_RV_SHORT: {IV_RV_SHORT}")
        print(f"  LOOKBACK_RV: {LOOKBACK_RV} days")
        
    except Exception as e:
        print(f"\n❌ Error during backtest: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure data files exist in data/ directory")
        print("2. Check data files have 'date' and 'close' columns")
        print("3. Verify data has sufficient history (60+ days)")
        import traceback
        traceback.print_exc()
