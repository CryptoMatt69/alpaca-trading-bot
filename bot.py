import os
from flask import Flask, request, jsonify, render_template_string
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
from datetime import datetime
import pytz

# ----------------------------
load_dotenv()
app = Flask(__name__)

API_KEY = os.environ.get("APCA_API_KEY_ID")
API_SECRET = os.environ.get("APCA_API_SECRET_KEY")
BASE_URL = os.environ.get("APCA_API_BASE_URL")

if not all([API_KEY, API_SECRET, BASE_URL]):
    raise ValueError("Alpaca API keys or base URL not set!")

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

# ----------------------------
@app.route("/", methods=["GET"])
def home():
    page = """
<!DOCTYPE html>
<html>
<head>
<title>TradeClaw Premium Terminal</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');

body {
    margin: 0;
    font-family: 'Roboto Mono', monospace;
    background: linear-gradient(to right, #0f0c29, #302b63, #24243e);
    color: #fff;
    overflow-x: hidden;
}

.container {
    max-width: 1300px;
    margin: 20px auto;
    padding: 10px;
}

.title {
    font-size: 60px;
    font-weight: 900;
    text-align: center;
    background: linear-gradient(90deg, #ff2bd6, #ff7f50);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 30px;
}

.card {
    background: rgba(0,0,0,0.85);
    border-radius: 15px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 0 40px rgba(255, 43, 214, 0.5);
    transition: transform 0.2s;
}

.card:hover {
    transform: scale(1.01);
}

.card h2 {
    margin-top: 0;
    font-size: 24px;
    color: #ff2bd6;
}

.stat {
    font-size: 18px;
    margin: 5px 0;
    transition: all 0.5s ease;
}

#chart {
    width: 100%;
    height: 500px;
    border-radius: 15px;
    overflow: hidden;
    box-shadow: 0 0 40px rgba(255, 43, 214, 0.5);
    margin-bottom: 20px;
}

.message-box {
    text-align: center;
    font-size: 20px;
    color: #00ff00;
    text-shadow: 0 0 10px #00ff00;
    margin-top: 10px;
}

.chart-select {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
}

.chart-select input {
    padding: 5px 10px;
    border-radius: 8px;
    border: none;
    font-size: 16px;
}

.chart-select button {
    padding: 5px 12px;
    border-radius: 8px;
    border: none;
    background: #ff2bd6;
    color: #fff;
    cursor: pointer;
    font-weight: bold;
    transition: 0.2s;
}
.chart-select button:hover {
    background: #ff7f50;
}
</style>
</head>
<body>

<div class="container">
    <div class="title">🤖 TradeClaw Premium</div>

    <div class="card">
        <h2>Account Overview</h2>
        <div class="stat">PnL: <span id="pnl">$0.00</span></div>
        <div class="stat">Recent Trade: <span id="recent_trade">N/A</span></div>
        <div class="stat">Trading Session: <span id="session_status">Loading...</span></div>
        <div class="message-box">Automated trades, Proven results.</div>
    </div>

    <div class="card">
        <h2>TradingView Chart</h2>
        <div class="chart-select">
            <input type="text" id="chart_symbol" placeholder="Symbol e.g. AAPL" />
            <select id="chart_interval">
                <option value="1">1 min</option>
                <option value="5" selected>5 min</option>
                <option value="15">15 min</option>
                <option value="60">1 hr</option>
                <option value="D">Daily</option>
            </select>
            <button onclick="updateChart()">Load Chart</button>
        </div>
        <div id="chart">
            <iframe id="chart_iframe" 
                src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_12345&symbol=NASDAQ%3AAAPL&interval=5&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=000000&studies=[]&theme=dark&style=1&timezone=Etc%2FUTC&studies_overrides={'mainSeriesProperties.candleStyle.upColor':'#DA70D6','mainSeriesProperties.candleStyle.downColor':'#000000','mainSeriesProperties.candleStyle.wickUpColor':'#DA70D6','mainSeriesProperties.candleStyle.wickDownColor':'#000000','mainSeriesProperties.candleStyle.borderUpColor':'#DA70D6','mainSeriesProperties.candleStyle.borderDownColor':'#000000','paneProperties.background':'#000000'}"
                style="width:100%; height:100%;" allowtransparency="true" frameborder="0"></iframe>
        </div>
    </div>

    <div class="card">
        <h2>Current Positions</h2>
        <div id="positions_box">Loading...</div>
    </div>
</div>

<script>
// ------------------- Dynamic Chart Swap -------------------
function updateChart() {
    const symbol = document.getElementById('chart_symbol').value.toUpperCase() || "AAPL";
    const interval = document.getElementById('chart_interval').value;
    const iframe = document.getElementById('chart_iframe');
    iframe.src = `https://s.tradingview.com/widgetembed/?frameElementId=tradingview_12345&symbol=NASDAQ%3A${symbol}&interval=${interval}&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=000000&studies=[]&theme=dark&style=1&timezone=Etc%2FUTC&studies_overrides={'mainSeriesProperties.candleStyle.upColor':'#DA70D6','mainSeriesProperties.candleStyle.downColor':'#000000','mainSeriesProperties.candleStyle.wickUpColor':'#DA70D6','mainSeriesProperties.candleStyle.wickDownColor':'#000000','mainSeriesProperties.candleStyle.borderUpColor':'#DA70D6','mainSeriesProperties.candleStyle.borderDownColor':'#000000','paneProperties.background':'#000000'}`;
}

// ------------------- Live Stats -------------------
let lastPnl = 0;

async function fetchData() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();

        // Animate PnL
        const pnlEl = document.getElementById('pnl');
        const pnlValue = parseFloat(data.pnl.replace('$','').replace(',','')) || 0;
        const color = pnlValue >= 0 ? "#DA70D6" : "#ff3b3b";
        pnlEl.style.color = color;
        animateNumber(pnlEl, lastPnl, pnlValue);
        lastPnl = pnlValue;

        document.getElementById('recent_trade').innerText = data.recent_trade;
        document.getElementById('session_status').innerText = data.session_status;

        const posBox = document.getElementById('positions_box');
        if(data.positions.length === 0){
            posBox.innerHTML = "No open positions";
        } else {
            posBox.innerHTML = data.positions.map(p => {
                const color = p.side === "LONG" ? "#00ff00" : "#ff3b3b";
                return `<span style="color:${color}; font-weight:bold">${p.symbol}: ${p.side} ${p.qty} @ $${p.avg_entry_price}</span>`;
            }).join('<br>');
        }
    } catch (e) {
        console.error(e);
    }
}

// ------------------- Animate Numbers -------------------
function animateNumber(element, start, end) {
    const duration = 500;
    const range = end - start;
    const startTime = performance.now();
    function step(currentTime) {
        const progress = Math.min((currentTime - startTime)/duration,1);
        element.innerText = "$" + (start + range * progress).toFixed(2);
        if(progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

// Fetch every 3 seconds for smooth live update
fetchData();
setInterval(fetchData, 3000);
</script>
</body>
</html>
    """
    return render_template_string(page)

# ----------------------------
@app.route("/api/stats", methods=["GET"])
def api_stats():
    try:
        clock = api.get_clock()
        est_now = datetime.now(pytz.timezone("US/Eastern")).strftime("%I:%M:%S %p EST")
        session_status = f"{'OPEN 🟢' if clock.is_open else 'CLOSED 🔴'} {est_now}"
    except:
        session_status = "UNKNOWN"

    try:
        account = api.get_account()
        pnl = f"${float(account.equity) - float(account.cash):,.2f}"
        trades = api.list_orders(status='closed', limit=1, order_by='created_at', direction='desc')
        recent_trade = f"{trades[0].symbol} {trades[0].side.upper()} {trades[0].filled_qty}" if trades else "N/A"
    except:
        pnl = "$0.00"
        recent_trade = "N/A"

    pos_list = []
    try:
        positions = api.list_positions()
        for p in positions:
            side = "LONG" if float(p.qty) > 0 else "SHORT"
            pos_list.append({
                "symbol": p.symbol,
                "qty": abs(float(p.qty)),
                "avg_entry_price": p.avg_entry_price,
                "side": side
            })
    except:
        pos_list = []

    return jsonify({
        "pnl": pnl,
        "recent_trade": recent_trade,
        "session_status": session_status,
        "positions": pos_list
    })

# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON received"}), 400

        symbol = data.get("symbol")
        qty = data.get("qty")
        side = data.get("side")

        if not all([symbol, qty, side]):
            return jsonify({"error": "Missing parameters"}), 400

        side = side.lower()
        if side in ["buy", "sell"]:
            order = api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type="market",
                time_in_force="gtc"
            )
            return jsonify({"status": "order_submitted", "id": order.id})

        elif side in ["close_long", "close_short"]:
            api.close_position(symbol)
            return jsonify({"status": "position_closed"})

        else:
            return jsonify({"error": "Invalid side"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port)
