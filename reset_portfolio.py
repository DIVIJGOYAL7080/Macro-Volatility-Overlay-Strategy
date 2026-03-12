#!/usr/bin/env python3
"""
Reset Trading Portfolio

Resets the real-time trading portfolio to initial state.
Run this script when you want to start fresh.
"""

import json
import os
from datetime import datetime

def reset_portfolio():
    """Reset trading portfolio to initial state"""
    
    print("🔄 RESETTING TRADING PORTFOLIO")
    print("="*50)
    
    # Create fresh results directory
    os.makedirs('paper_trading_results', exist_ok=True)
    
    # Reset portfolio state
    initial_state = {
        'timestamp': datetime.now().isoformat(),
        'capital': 100000,
        'portfolio_value': 100000,
        'open_positions': 0,
        'total_trades': 0,
        'trade_history': [],
        'positions': {},
        'reset_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Save reset state
    files_to_create = [
        'paper_trading_results/latest_results.json',
        'paper_trading_results/portfolio_state.json',
        'paper_trading_results/reset_state.json'
    ]
    
    for filename in files_to_create:
        with open(filename, 'w') as f:
            json.dump(initial_state, f, indent=2, default=str)
    
    # Clear any existing daily results for today
    from datetime import date
    today_str = date.today().strftime('%Y%m%d')
    daily_file = f'paper_trading_results/daily_results_{today_str}.json'
    
    if os.path.exists(daily_file):
        os.remove(daily_file)
        print(f"🗑️  Removed today's daily results: {daily_file}")
    
    print(f"✅ Portfolio reset complete!")
    print(f"💰 Initial Capital: ${initial_state['capital']:,.2f}")
    print(f"📁 State files created:")
    for filename in files_to_create:
        print(f"   - {filename}")
    
    print(f"\n🚀 Now you can run realtime_paper_trader.py to start fresh!")

if __name__ == "__main__":
    reset_portfolio()
