"""
Real-Time Trading Dashboard

Dashboard for monitoring real-time trading performance and analytics.
"""

import pandas as pd
import json
import glob
import os
from datetime import datetime

def create_trading_dashboard():
    """Create dashboard from real-time trading results"""
    
    # Try to load latest results first, then fallback to any results
    latest_file = 'paper_trading_results/latest_results.json'
    result_files = glob.glob('paper_trading_results/*results*.json')
    
    results = None
    
    # Try latest file first
    if os.path.exists(latest_file):
        try:
            with open(latest_file, 'r') as f:
                results = json.load(f)
            print(f"📊 Loaded latest results from {latest_file}")
        except Exception as e:
            print(f"⚠️  Could not load latest file: {e}")
    
    # Fallback to any result file
    if results is None and result_files:
        latest_file = max(result_files, key=os.path.getctime)
        try:
            with open(latest_file, 'r') as f:
                results = json.load(f)
            print(f"📊 Loaded results from {latest_file}")
        except Exception as e:
            print(f"❌ Error loading results: {e}")
            return
    
    if results is None:
        print("❌ No trading results found. Run realtime_paper_trader.py first.")
        return
    
    # Create analysis
    trades = pd.DataFrame(results['trade_history'])
    
    if trades.empty:
        print("📊 No trades executed yet.")
        print(f"\n💰 PORTFOLIO STATUS")
        print(f"   Current Capital: ${results['capital']:,.2f}")
        print(f"   Portfolio Value: ${results['portfolio_value']:,.2f}")
        print(f"   Open Positions: {results['open_positions']}")
        return
    
    print("="*50)
    print("REAL-TIME TRADING DASHBOARD")
    print("="*50)
    
    # Portfolio status
    print(f"\n💰 PORTFOLIO STATUS")
    print(f"   Current Capital: ${results['capital']:,.2f}")
    print(f"   Portfolio Value: ${results['portfolio_value']:,.2f}")
    print(f"   Open Positions: {results['open_positions']}")
    print(f"   Total Trades: {results['total_trades']}")
    
    # Calculate total return
    initial_capital = 100000  # Assuming initial capital
    total_return = (results['portfolio_value'] - initial_capital) / initial_capital * 100
    print(f"   Total Return: {total_return:+.2f}%")
    
    # Trade performance
    closed_trades = trades[trades['action'] == 'CLOSE']
    if not closed_trades.empty:
        total_pnl = closed_trades['final_pnl'].sum()
        win_rate = (closed_trades['final_pnl'] > 0).mean()
        avg_win = closed_trades[closed_trades['final_pnl'] > 0]['final_pnl'].mean()
        avg_loss = closed_trades[closed_trades['final_pnl'] <= 0]['final_pnl'].mean()
        
        # Additional metrics
        total_wins = closed_trades[closed_trades['final_pnl'] > 0]['final_pnl'].sum()
        total_losses = abs(closed_trades[closed_trades['final_pnl'] <= 0]['final_pnl'].sum())
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        print(f"\n📈 PERFORMANCE METRICS")
        print(f"   Total P&L: ${total_pnl:,.2f}")
        print(f"   Win Rate: {win_rate:.1%}")
        print(f"   Average Win: ${avg_win:,.2f}")
        print(f"   Average Loss: ${avg_loss:,.2f}")
        print(f"   Profit Factor: {profit_factor:.2f}")
        
        # Exit reasons
        if 'exit_reason' in closed_trades.columns:
            exit_reasons = closed_trades['exit_reason'].value_counts()
            print(f"\n🎯 EXIT REASONS")
            for reason, count in exit_reasons.items():
                print(f"   {reason}: {count} trades")
    
    # Daily performance if we have timestamps
    if 'timestamp' in trades.columns:
        trades['date'] = pd.to_datetime(trades['timestamp']).dt.date
        daily_pnl = trades[trades['action'] == 'CLOSE'].groupby('date')['final_pnl'].sum()
        if not daily_pnl.empty:
            print(f"\n📅 DAILY PERFORMANCE (Last 5 days)")
            for date, pnl in daily_pnl.tail(5).items():
                pnl_emoji = "🟢" if pnl > 0 else "🔴"
                print(f"   {pnl_emoji} {date}: ${pnl:+,.2f}")
    
    # Signal breakdown
    if 'signal' in trades.columns:
        signal_breakdown = trades[trades['action'] == 'OPEN']['signal'].value_counts()
        print(f"\n📊 SIGNAL BREAKDOWN")
        for signal, count in signal_breakdown.items():
            print(f"   {signal}: {count} trades")
    
    # Open positions
    open_positions = [p for p in results['positions'].values() if p['status'] == 'OPEN']
    if open_positions:
        print(f"\n📋 OPEN POSITIONS")
        for pos in open_positions:
            try:
                entry_time = datetime.fromisoformat(pos['entry_time'].replace('Z', '+00:00')) if isinstance(pos['entry_time'], str) else pos['entry_time']
                days_held = (datetime.now() - entry_time).days
                pnl_emoji = "🟢" if pos['current_pnl'] > 0 else "🔴"
                pnl_pct = (pos['current_pnl'] / pos['margin_used'] * 100) if pos['margin_used'] > 0 else 0
                print(f"   {pnl_emoji} {pos['symbol']} {pos['signal']}: ${pos['current_pnl']:+,.2f} ({pnl_pct:+.1f}%, {days_held} days)")
            except Exception as e:
                print(f"   ⚠️  {pos['symbol']} {pos['signal']}: Data error")
    
    # Recent activity
    if len(trades) > 0:
        print(f"\n📅 RECENT ACTIVITY (Last 10 trades)")
        recent_trades = trades.tail(10)
        for _, trade in recent_trades.iterrows():
            try:
                timestamp = pd.to_datetime(trade['timestamp']).strftime('%Y-%m-%d %H:%M') if isinstance(trade['timestamp'], str) else str(trade['timestamp'])
                action_emoji = "🟢" if trade['action'] == 'OPEN' else "🔴"
                symbol = trade.get('symbol', 'N/A')
                signal = trade.get('signal', 'N/A')
                pnl_info = f" P&L: ${trade.get('final_pnl', 0):+,.2f}" if trade['action'] == 'CLOSE' else ""
                exit_info = f" ({trade.get('exit_reason', '')})" if trade.get('exit_reason') else ""
                print(f"   {action_emoji} {timestamp}: {trade['action']} {symbol} {signal}{pnl_info}{exit_info}")
            except Exception as e:
                print(f"   ⚠️  Trade data error")
    
    # File information
    print(f"\n📁 DATA SOURCE")
    if 'latest_results.json' in str(result_files):
        print(f"   Using latest real-time data")
    else:
        print(f"   Using: {latest_file}")
    
    total_files = len(result_files)
    print(f"   Total result files: {total_files}")

if __name__ == "__main__":
    create_trading_dashboard()
