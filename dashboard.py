"""
Paper Trading Dashboard

Simple dashboard for monitoring paper trading performance.
"""

import pandas as pd
import json
import glob
from datetime import datetime

def create_paper_trading_dashboard():
    """Create dashboard from paper trading results"""
    
    # Load latest results
    result_files = glob.glob('paper_trading_results/paper_results_*.json')
    if not result_files:
        print("❌ No paper trading results found. Run paper_trader.py first.")
        return
    
    latest_file = max(result_files)
    with open(latest_file, 'r') as f:
        results = json.load(f)
    
    # Create analysis
    trades = pd.DataFrame(results['trade_history'])
    
    if trades.empty:
        print("📊 No trades executed yet.")
        return
    
    print("="*50)
    print("PAPER TRADING DASHBOARD")
    print("="*50)
    
    # Portfolio status
    print(f"\n💰 PORTFOLIO STATUS")
    print(f"   Current Capital: ${results['capital']:,.2f}")
    print(f"   Portfolio Value: ${results['portfolio_value']:,.2f}")
    print(f"   Open Positions: {results['open_positions']}")
    print(f"   Total Trades: {results['total_trades']}")
    
    # Trade performance
    closed_trades = trades[trades['action'] == 'CLOSE']
    if not closed_trades.empty:
        total_pnl = closed_trades['final_pnl'].sum()
        win_rate = (closed_trades['final_pnl'] > 0).mean()
        avg_win = closed_trades[closed_trades['final_pnl'] > 0]['final_pnl'].mean()
        avg_loss = closed_trades[closed_trades['final_pnl'] <= 0]['final_pnl'].mean()
        
        print(f"\n📈 PERFORMANCE METRICS")
        print(f"   Total P&L: ${total_pnl:,.2f}")
        print(f"   Win Rate: {win_rate:.1%}")
        print(f"   Average Win: ${avg_win:,.2f}")
        print(f"   Average Loss: ${avg_loss:,.2f}")
        
        # Exit reasons
        if 'exit_reason' in closed_trades.columns:
            exit_reasons = closed_trades['exit_reason'].value_counts()
            print(f"\n🎯 EXIT REASONS")
            for reason, count in exit_reasons.items():
                print(f"   {reason}: {count} trades")
    
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
            days_held = (datetime.now() - datetime.fromisoformat(pos['entry_time'].replace('Z', '+00:00'))).days
            pnl_emoji = "🟢" if pos['current_pnl'] > 0 else "🔴"
            print(f"   {pnl_emoji} {pos['symbol']} {pos['signal']}: ${pos['current_pnl']:+,.2f} ({days_held} days)")
    
    # Recent activity
    if len(trades) > 0:
        print(f"\n📅 RECENT ACTIVITY")
        recent_trades = trades.tail(5)
        for _, trade in recent_trades.iterrows():
            timestamp = trade['timestamp'] if isinstance(trade['timestamp'], str) else str(trade['timestamp'])
            action_emoji = "🟢" if trade['action'] == 'OPEN' else "🔴"
            print(f"   {action_emoji} {timestamp}: {trade['action']} {trade.get('symbol', 'N/A')} {trade.get('signal', 'N/A')}")

if __name__ == "__main__":
    create_paper_trading_dashboard()
