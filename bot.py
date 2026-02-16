import streamlit as st
import yfinance as yf
from datetime import datetime

# ----------------------------
# PAGE CONFIG
# ----------------------------
st.set_page_config(
    page_title="TRADECLAW Terminal",
    page_icon="📈",
    layout="wide"
)

# ----------------------------
# CUSTOM CSS (NEON + CLEAN)
# ----------------------------
st.markdown("""
<style>
html, body, [class*="css"]  {
    background-color: #0d0d0d;
    color: white;
}
.main-header { text-align:center; padding-top:10px; }
.main-title { font-size:48px; font-weight:700; color:#ff66ff; text-shadow:0 0 20px #ff66ff; margin-bottom:5px; }
.subtitle { font-size:16px; color:#cccccc; margin-bottom:30px; }
.metric-card { background:#111111; padding:18px; border-radius:14px; box-shadow:0 0 14px rgba(255,0,255,0.15); text-align:center; }
.neon-green { color:#ff66ff; text-shadow:0 0 8px #ff66ff; }
.neon-red { color:#ff1a1a; text-shadow:0 0 6px #ff1a1a; }
section[data-testid="stSidebar"] { background-color: #111111; }
iframe { border:none; border-radius:10px; margin-bottom:15px; }
.chart-container { width:100%; height:450px; }
.grid { display:grid; grid-template-columns:repeat(2,1fr); gap:10px; }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# HEADER
# ----------------------------
st.markdown("""
<div class="main-header">
    <div class="main-title">TRADECLAW</div>
    <div class="subtitle">
        Advanced Trading Analytics • Performance Intelligence • Market Visualization
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------------------
# SIDEBAR NAV
# ----------------------------
st.sidebar.title("📊 Navigation")
page = st.sidebar.radio("Select Page", ["Dashboard", "Performance", "Activity / Win Rate"])

single_stock = st.sidebar.text_input("Single Chart Ticker", "AAPL")
multi_stocks = st.sidebar.text_input("Multi Chart Tickers (comma separated)", "AAPL,TSLA,NVDA")

# ----------------------------
# DASHBOARD
# ----------------------------
if page == "Dashboard":
    col1, col2, col3 = st.columns(3)
    equity = 100000
    daily_pnl = 1200  # example
    win_rate = 65.5
    pnl_class = "neon-green" if daily_pnl > 0 else "neon-red"

    col1.markdown(f'<div class="metric-card"><h4>Total Equity</h4><h2 class="neon-green">${equity:,.2f}</h2></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="metric-card"><h4>Daily PnL</h4><h2 class="{pnl_class}">${daily_pnl:,.2f}</h2></div>', unsafe_allow_html=True)
    col3.markdown(f'<div class="metric-card"><h4>Win Rate</h4><h2 class="neon-green">{win_rate:.2f}%</h2></div>', unsafe_allow_html=True)

    st.markdown("### 📈 Single Stock Chart")
    st.markdown(f"""
    <div class="chart-container">
    <iframe src="https://s.tradingview.com/widgetembed/?symbol=NASDAQ:{single_stock.upper()}&interval=15&theme=dark&studies=%5B%5D&toolbarbg=000000" width="100%" height="100%"></iframe>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📊 Multi Stock Comparison")
    tickers = [t.strip().upper() for t in multi_stocks.split(",")]
    st.markdown('<div class="grid">', unsafe_allow_html=True)
    for t in tickers:
        st.markdown(f"""
        <div class="chart-container">
        <iframe src="https://s.tradingview.com/widgetembed/?symbol=NASDAQ:{t}&interval=15&theme=dark&studies=%5B%5D&toolbarbg=000000" width="100%" height="100%"></iframe>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------
# PERFORMANCE
# ----------------------------
elif page == "Performance":
    st.markdown("## 📊 Performance Analytics")
    st.markdown("""
    <div class="metric-card">
    <p>Sharpe Ratio: 1.25</p>
    <p>Max Drawdown: -5.4%</p>
    <p>Total Return: 12.3%</p>
    <p>Total Trades: 128</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📈 Equity Curve")
    st.markdown("""
    <div class="chart-container">
    <iframe src="https://s.tradingview.com/widgetembed/?symbol=NASDAQ:AAPL&interval=60&theme=dark&studies=%5B%5D&toolbarbg=000000" width="100%" height="100%"></iframe>
    </div>
    """, unsafe_allow_html=True)

# ----------------------------
# ACTIVITY / WIN RATE
# ----------------------------
elif page == "Activity / Win Rate":
    st.markdown("## 📈 Activity & Win Rate Trends")
    # Since we’re not using Plotly, just show placeholder TradingView chart (could be replaced with actual performance data)
    st.markdown("""
    <div class="chart-container">
    <iframe src="https://s.tradingview.com/widgetembed/?symbol=NASDAQ:AAPL&interval=1D&theme=dark&studies=%5B%5D&toolbarbg=000000" width="100%" height="100%"></iframe>
    </div>
    """, unsafe_allow_html=True)
