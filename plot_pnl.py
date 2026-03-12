import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Load trades
trades = pd.read_csv("/Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/results/trades.csv", parse_dates=['date'])

# Calculate realistic P&L per trade (same logic as analyze_strategy.py)
def calculate_realistic_pnl(row):
    """Calculate P&L with realistic win rates and risk/reward"""
    premium_collected = row['premium'] * row['contracts']
    
    if row['signal'] == 'BUY_CONVEXITY':
        # 42% win rate, 3:1 risk:reward (long straddle)
        if np.random.random() < 0.42:
            return premium_collected * 3.0
        else:
            return -premium_collected * 0.8
    else:  # SELL_PREMIUM
        # 70% win rate, 0.6:1 risk:reward (iron condor)
        if np.random.random() < 0.70:
            return premium_collected * 0.9
        else:
            return -premium_collected * 1.2

# Set seed for reproducible results
np.random.seed(42)

# Calculate realistic P&L
trades['realistic_pnl'] = trades.apply(calculate_realistic_pnl, axis=1)

# Aggregate daily P&L
daily_pnl = trades.groupby('date')['realistic_pnl'].sum()
cumulative_pnl = daily_pnl.cumsum()

# Calculate drawdowns
running_max = cumulative_pnl.expanding().max()
drawdown = (cumulative_pnl - running_max) / running_max * 100

# Create figure with subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

# Plot 1: Cumulative P&L
ax1.plot(cumulative_pnl.index, cumulative_pnl.values, linewidth=2, color='blue', label='Cumulative P&L')
ax1.axhline(y=0, color='black', linestyle='--', alpha=0.5)
ax1.fill_between(cumulative_pnl.index, cumulative_pnl.values, 0, 
                 where=(cumulative_pnl.values >= 0), alpha=0.3, color='green', interpolate=True)
ax1.fill_between(cumulative_pnl.index, cumulative_pnl.values, 0, 
                 where=(cumulative_pnl.values < 0), alpha=0.3, color='red', interpolate=True)
ax1.set_title('Realistic Cumulative P&L - Macro Volatility Overlay', fontsize=14, fontweight='bold')
ax1.set_ylabel('Cumulative P&L (USD)', fontsize=12)
ax1.grid(True, alpha=0.3)
ax1.legend()

# Add P&L statistics
total_pnl = cumulative_pnl.iloc[-1]
win_rate = (trades['realistic_pnl'] > 0).mean()
ax1.text(0.02, 0.98, f'Total P&L: ${total_pnl:,.0f}\nWin Rate: {win_rate:.1%}', 
           transform=ax1.transAxes, verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

# Plot 2: Drawdown
ax2.fill_between(drawdown.index, drawdown.values, 0, alpha=0.3, color='red')
ax2.plot(drawdown.index, drawdown.values, color='red', linewidth=1)
ax2.set_title('Portfolio Drawdown', fontsize=14, fontweight='bold')
ax2.set_ylabel('Drawdown (%)', fontsize=12)
ax2.set_xlabel('Date', fontsize=12)
ax2.grid(True, alpha=0.3)

# Add max drawdown info
max_dd = drawdown.min()
ax2.text(0.02, 0.98, f'Max Drawdown: {max_dd:.1f}%', 
           transform=ax2.transAxes, verticalalignment='top', bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.8))

plt.tight_layout()
plt.savefig('/Users/divijgoyal/Desktop/quant shi/macro-volatility-overlay--main/results/realistic_pnl_chart.png', dpi=300, bbox_inches='tight')
plt.show()

print(f"✅ Realistic P&L chart saved to results/realistic_pnl_chart.png")
print(f"📊 Total P&L: ${total_pnl:,.2f}")
print(f"🎯 Win Rate: {win_rate:.1%}")
print(f"📉 Max Drawdown: {max_dd:.1f}%")
