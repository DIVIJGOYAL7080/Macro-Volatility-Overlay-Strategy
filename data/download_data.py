"""
Market Data Downloader for Macro Volatility Strategy

Downloads historical price data for all assets used in the strategy.
"""

import yfinance as yf
from datetime import datetime

def download_market_data():
    """Download market data for all strategy assets"""
    
    print("Downloading market data for Macro Volatility Strategy...")
    print(f"Download date: {datetime.now().strftime('%Y-%m-%d')}")
    
    # Set end date to today
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Asset configurations
    assets = {
        'KC=F': 'kc.csv',           # Coffee futures
        '^GSPC': 'spx.csv',         # S&P 500
        'EURUSD=X': 'eurusd.csv'    # EUR/USD
    }
    
    # Download data for each asset
    for symbol, filename in assets.items():
        try:
            print(f"\nDownloading {symbol}...")
            
            # Download data from 2023 to present
            data = yf.download(symbol, start="2023-01-01", end=end_date)
            
            if not data.empty:
                # Save only close prices with date index
                close_data = data[['Close']].copy()
                close_data.index.name = 'date'
                close_data = close_data.reset_index()
                close_data = close_data.rename(columns={'Close': 'close'})
                # Remove any rows with missing data
                close_data = close_data.dropna()
                close_data.to_csv(filename, index=False)
                
                print(f"  ✓ {len(data)} data points")
                print(f"  ✓ Period: {data.index[0].strftime('%Y-%m-%d')} to {data.index[-1].strftime('%Y-%m-%d')}")
                print(f"  ✓ Saved to {filename}")
            else:
                print(f"  ❌ No data available for {symbol}")
                
        except Exception as e:
            print(f"  ❌ Error downloading {symbol}: {e}")
    
    print(f"\n✅ Data download complete!")
    print(f"Files saved: {', '.join(assets.values())}")
    print(f"Latest data: {end_date}")

if __name__ == "__main__":
    download_market_data()
