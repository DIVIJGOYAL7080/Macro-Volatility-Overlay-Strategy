# Contributing to Macro Volatility Overlay Strategy

## 🤝 How to Contribute

Contributions are welcome! This is a quantitative trading strategy project focused on volatility arbitrage.

### 🚀 Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/macro-volatility-overlay.git`
3. Create a virtual environment: `python -m venv venv && source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Download data: `cd data && python download_data.py`

### 📝 Types of Contributions

- **Bug fixes** and error handling
- **Performance optimizations**
- **New asset classes** or indicators
- **Documentation improvements**
- **Risk management enhancements**

### 🧪 Testing

- Test your changes with the backtest: `python macro_vol_overlay.py`
- Verify paper trading functionality: `python paper_trader.py`
- Check performance analysis: `python analyze_strategy.py`

### 📤 Submitting Changes

1. Create a new branch: `git checkout -b feature/your-feature`
2. Commit your changes: `git commit -m "Add your feature"`
3. Push to your fork: `git push origin feature/your-feature`
4. Create a Pull Request

### ⚠️ Important Notes

- This is a **simulated trading strategy** - not for live trading without extensive testing
- Always backtest thoroughly before making changes
- Maintain realistic market assumptions
- Follow quantitative finance best practices

## 📄 License

This project is for educational and research purposes. Use at your own risk.
