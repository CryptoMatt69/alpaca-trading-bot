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
body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #0f0c29;
    color: white;
}
.container {
    max-width: 1400px;
    margin: auto;
    padding: 20px;
}
.title {
    font-size: 50px;
    text-align: center;
    margin-bottom: 20px;
    color: #DA70D6;
}
.card {
    background: #1a1a1a;
    padding: 20px;
    border-radius: 15px;
    margin-bottom: 20px;
}
button {
    padding: 8px 14px;
    border: none;
    border-radius: 6px;
    background: #DA70D6;
    color: white;
    cursor: pointer;
}
#chartContainer iframe {
    width: 100%;
    height: 500px;
    border: none;
}
.grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
}
.grid iframe {
    height: 300px;
}
</style>
</head>
<body>

<div class="container">
    <div class="title">🤖 TradeClaw Premium</div>

    <div class="card">
        <h2>Portfolio</h2>
        <div>Total Equity: <span id="equity">$0</span></div>
        <div>Daily PnL: <span id="daily_pnl">$0</span></div>
        <div>Recent Trade: <span id="recent_trade">N/A</span></div>
        <div>Session: <span id="session_status">Loading...</span></div>
    </div>

    <div class="card">
        <h2>Charts</h2>
        <button onclick="singleView()">Single Chart</button>
        <button onclick="multiView()">Multi Chart</button>
        <div id="chartContainer"></div>
    </div>

    <div class="card">
        <h2>Positions</h2>
        <div id="positions_box">Loading...</div>
    </div>
</div>

<script>

const symbols = ["TSLA","NVDA","SPY","QQQ","AAPL","PLTR","UNH","RIVN"];

function singleView(){
    document.getElementById("chartContainer").innerHTML =
        `<iframe src="https://s.tradingview.com/widgetembed/?symbol=NASDAQ:AAPL&interval=15&theme=dark"></iframe>`;
}

function multiView(){
    let html = '<div class="grid">';
    symbols.forEach(sym=>{
        html += `<iframe src="https://s.tradingview.com/widgetembed/?symbol=NASDAQ:${sym}&interval=15&theme=dark"></iframe>`;
    });
    html += '</div>';
    document.getElementById("chartContainer").innerHTML = html;
}

singleView();

async function fetchData(){
    const res = await fetch('/api/stats');
    const data = await res.json();

    document.getElementById("equity").innerText = data.equity;
    document.getElementById("daily_pnl").innerText = data.daily_pnl;
    document.getElementById("recent_trade").innerText = data.recent_trade;
    document.getElementById("session_status").innerText = data.session_status;

    const posBox = document.getElementById('positions_box');
    if(data.positions.length === 0){
        posBox.innerHTML = "No open positions";
    } else {
        posBox.innerHTML = data.positions.map(p =>
            `${p.symbol} ${p.side} ${p.qty} @ $${p.avg_entry_price}`
        ).join("<br>");
    }
}

setInterval(fetchData,3000);
fetchData();

</script>
</body>
</html>
"""
    return render_template_string(page)

# ----------------------------
@app.route("/api/stats", methods=["GET"])
def api_stats():
    try:
        account = api.get_account()
        equity = f"${float(account.equity):,.2f}"
        daily_pnl = f"${float(account.equity) - float(account.last_equity):,.2f}"
        trades = api.list_orders(status='closed', limit=1)
        recent_trade = f"{trades[0].symbol} {trades[0].side.upper()} {trades[0].filled_qty}" if trades else "N/A"
    except:
        equity = "$0"
        daily_pnl = "$0"
        recent_trade = "N/A"

    try:
        clock = api.get_clock()
        session_status = "OPEN 🟢" if clock.is_open else "CLOSED 🔴"
    except:
        session_status = "UNKNOWN"

    pos_list = []
    try:
        positions = api.list_positions()
        for p in positions:
            pos_list.append({
                "symbol": p.symbol,
                "qty": abs(float(p.qty)),
                "avg_entry_price": p.avg_entry_price,
                "side": "LONG" if float(p.qty) > 0 else "SHORT"
            })
    except:
        pass

    return jsonify({
        "equity": equity,
        "daily_pnl": daily_pnl,
        "recent_trade": recent_trade,
        "session_status": session_status,
        "positions": pos_list
    })

# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    symbol = data.get("symbol")
    qty = data.get("qty")
    side = data.get("side")

    if side in ["buy","sell"]:
        order = api.submit_order(
            symbol=symbol,
            qty=qty,
            side=side,
            type="market",
            time_in_force="gtc"
        )
        return jsonify({"status":"submitted","id":order.id})

    elif side in ["close_long","close_short"]:
        api.close_position(symbol)
        return jsonify({"status":"closed"})

    return jsonify({"error":"invalid side"}),400

# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port)

