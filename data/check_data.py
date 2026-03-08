import yfinance as yf
from datetime import datetime

print('=== YAHOO FINANCE DATA AVAILABILITY ===')
print('Current date:', datetime.now().strftime("%Y-%m-%d"))

# Check latest available data for each symbol
symbols = ['KC=F', '^GSPC', 'EURUSD=X']
for symbol in symbols:
    try:
        data = yf.download(symbol, period="5d")
        if not data.empty:
            latest_date = data.index[-1].strftime('%Y-%m-%d')
            latest_price = data['Close'].iloc[-1].values[0]
            print(symbol + ': Latest data ' + latest_date + ', Price $' + str(round(latest_price, 2)))
        else:
            print(symbol + ': No data available')
    except Exception as e:
        print(symbol + ': Error - ' + str(e))
