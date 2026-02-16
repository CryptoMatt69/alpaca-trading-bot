import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# ----------------------------
# PAGE CONFIG (Fix Untitled)
# ----------------------------
st.set_page_config(
    page_title="TRADECLAW Terminal",
    page_icon="📈",
    layout="wide"
)

# ----------------------------
# CUSTOM CSS (Neon + Clean)
# ----------------------------
st.markdown("""
<style>

html, body, [class*="css"]  {
    background-color: #0d0d0d;
    color: white;
}

/* HEADER */
.main-header {
    text-align: center;
    padding-top: 10px;
}

.main-title {
    font-size: 48px;
    font-weight: 700;
    color: #ff66ff;
    text-shadow: 0 0 20px #ff66ff;
    margin-bottom: 5px;
}

.subtitle {
    font-size: 16px;
    color: #cccccc;
    margin-bottom: 30px;
}

/* Metric Cards */
.metric-card {
    background: #111111;
    padding: 18px;
    border-radius: 14px;
    box-shadow: 0 0 14px rgba(255,0,255,0.15);
    text-align: center;
}

.neon-green {
    color: #ff66ff;
    text-shadow: 0 0 8px #ff66ff;
}

.neon-red {
    color: #ff1a1a;
    text-shadow: 0 0 6px #ff1a1a;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #111111;
}

</style>
""", unsafe_allow_html=True)

# ----------------------------
# HEADER (RESTORED)
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

page = st.sidebar.radio(
    "Select Page",
    ["Dashboard", "Performance", "Activity / Win Rate"]
)

single_stock = st.sidebar.text_input("Single Chart Ticker", "AAPL")
multi_stocks = st.sidebar.text_input("Multi Chart Tickers (comma separated)", "AAPL,TSLA,NVDA")

# ----------------------------
# DATA
# ----------------------------
def get_stock_data(ticker):
    return yf.download(ticker, period="6mo", interval="1d")

# ============================
# DASHBOARD
# ============================
if page == "Dashboard":

    col1, col2, col3 = st.columns(3)

    equity = 100000
    daily_pnl = np.random.uniform(-1500, 2000)
    win_rate = np.random.uniform(45, 75)

    pnl_class = "neon-green" if daily_pnl > 0 else "neon-red"

    col1.markdown(f"""
        <div class="metric-card">
            <h4>Total Equity</h4>
            <h2 class="neon-green">${equity:,.2f}</h2>
        </div>
    """, unsafe_allow_html=True)

    col2.markdown(f"""
        <div class="metric-card">
            <h4>Daily PnL</h4>
            <h2 class="{pnl_class}">${daily_pnl:,.2f}</h2>
        </div>
    """, unsafe_allow_html=True)

    col3.markdown(f"""
        <div class="metric-card">
            <h4>Win Rate</h4>
            <h2 class="neon-green">{win_rate:.2f}%</h2>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📈 Single Stock Chart")

    df = get_stock_data(single_stock)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["Close"],
        mode="lines",
        line=dict(color="#ff66ff", width=2),
        name=single_stock.upper()
    ))

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#0d0d0d",
        paper_bgcolor="#0d0d0d",
        height=400,
        margin=dict(l=20, r=20, t=40, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 📊 Multi Stock Comparison")

    tickers = [t.strip().upper() for t in multi_stocks.split(",")]

    multi_fig = go.Figure()

    for ticker in tickers:
        data = get_stock_data(ticker)
        multi_fig.add_trace(go.Scatter(
            x=data.index,
            y=data["Close"],
            mode="lines",
            name=ticker
        ))

    multi_fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#0d0d0d",
        paper_bgcolor="#0d0d0d",
        height=400
    )

    st.plotly_chart(multi_fig, use_container_width=True)

# ============================
# PERFORMANCE
# ============================
elif page == "Performance":

    st.markdown("## 📊 Performance Analytics")

    returns = np.random.normal(0.001, 0.02, 120)
    cumulative = np.cumsum(returns)
    drawdown = cumulative - np.maximum.accumulate(cumulative)

    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
    max_dd = np.min(drawdown) * 100
    total_return = cumulative[-1] * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sharpe Ratio", f"{sharpe:.2f}")
    col2.metric("Max Drawdown", f"{max_dd:.2f}%")
    col3.metric("Total Return", f"{total_return:.2f}%")
    col4.metric("Total Trades", "128")

    perf_fig = go.Figure()
    perf_fig.add_trace(go.Scatter(
        y=cumulative,
        mode="lines",
        line=dict(color="#ff66ff"),
        name="Equity Curve"
    ))

    perf_fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#0d0d0d",
        paper_bgcolor="#0d0d0d",
        height=420
    )

    st.plotly_chart(perf_fig, use_container_width=True)

# ============================
# ACTIVITY
# ============================
elif page == "Activity / Win Rate":

    st.markdown("## 📈 Activity & Win Rate Trends")

    days = pd.date_range(end=datetime.today(), periods=60)

    activity = np.random.randint(1, 10, 60)
    winrate = np.random.uniform(40, 80, 60)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=days,
        y=activity,
        mode="lines",
        name="Trades Per Day",
        line=dict(color="#ff66ff")
    ))

    fig.add_trace(go.Scatter(
        x=days,
        y=winrate,
        mode="lines",
        name="Win Rate %",
        line=dict(color="#ff1a1a")
    ))

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#0d0d0d",
        paper_bgcolor="#0d0d0d",
        height=450
    )

    st.plotly_chart(fig, use_container_width=True)

