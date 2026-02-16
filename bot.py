import os
from flask import Flask, request, jsonify, render_template_string
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

# ----------------------------
# Load environment variables
load_dotenv()
app = Flask(__name__)

API_KEY = os.environ.get("APCA_API_KEY_ID")
API_SECRET = os.environ.get("APCA_API_SECRET_KEY")
BASE_URL = os.environ.get("APCA_API_BASE_URL")

if not all([API_KEY, API_SECRET, BASE_URL]):
    raise ValueError("Alpaca API keys or base URL not set!")

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

# ----------------------------
# Home route with hacker terminal + chart + stats
@app.route("/", methods=["GET"])
def home():
    # Clock / session
    try:
        clock = api.get_clock()
        session_status = "OPEN 🟢" if clock.is_open else "CLOSED 🔴"
    except Exception as e:
        print("Clock error:", e)
        session_status = "UNKNOWN"

    # Current positions
    try:
        positions = api.list_positions()
        pos_html = ""
        for p in positions:
            side = "LONG" if int(p.qty) > 0 else "SHORT"
            pos_html += f"{p.symbol}: {side} {abs(int(p.qty))} @ ${p.avg_entry_price}<br>"
        if not pos_html:
            pos_html = "No open positions"
    except Exception as e:
        print("Positions error:", e)
        pos_html = "Cannot fetch positions"

    # Example PnL and recent trade
    pnl = "$1,245.33"
    recent_trade = "NFLX BUY 1"

    page = f"""
<!DOCTYPE html>
<html>
<head>
<title>TradeClaw Terminal</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
body {{
    margin: 0;
    overflow: hidden;
    background: black;
    font-family: monospace;
    color: #ff2bd6;
}}
canvas {{
    position: fixed;
    top: 0;
    left: 0;
    z-index: 0;
}}
.container {{
    position: relative;
    z-index: 1;
    padding: 30px;
}}
.title {{
    font-size: 48px;
    color: #ff2bd6;
    text-shadow: 0 0 20px #ff2bd6;
}}
.stats {{
    margin-top: 10px;
    margin-bottom: 20px;
    font-size: 16px;
    padding: 20px;
    border: 2px solid #ff2bd6;
    box-shadow: 0 0 20px #ff2bd6;
    background: rgba(0,0,0,0.8);
}}
.stat-box {{
    display: inline-block;
    margin-right: 25px;
}}
#chart {{
    height:600px;
    border: 2px solid #ff2bd6;
    box-shadow: 0 0 20px #ff2bd6;
    background: rgba(0,0,0,0.9);
}}
</style>
</head>
<body>

<canvas id="matrix"></canvas>

<div class="container">
    <div class="title">TradeClaw</div>

    <div class="stats">
        <div class="stat-box">PnL: {pnl}</div>
        <div class="stat-box">Recent Trade: {recent_trade}</div>
        <div class="stat-box">Trading Session: {session_status}</div>
        <div class="stat-box">Current Positions:<br>{pos_html}</div>
    </div>

    <div id="chart"></div>
</div>

<script>
// MATRIX GREEN RAIN
const canvas = document.getElementById("matrix");
const ctx = canvas.getContext("2d");
canvas.height = window.innerHeight;
canvas.width = window.innerWidth;
const letters = "01ABCDEFGHIJKLMNOPQRSTUVWXYZ$#@%&*";
const fontSize = 16;
const columns = canvas.width / fontSize;
const drops = Array.from({{length: columns}}, () => 1);

function draw() {{
    ctx.fillStyle = "rgba(0, 0, 0, 0.05)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#00ff00";
    ctx.font = fontSize + "px monospace";
    for (let i = 0; i < drops.length; i++) {{
        const text = letters[Math.floor(Math.random() * letters.length)];
        ctx.fillText(text, i * fontSize, drops[i] * fontSize);
        if(drops[i] * fontSize > canvas.height && Math.random() > 0.975) drops[i] = 0;
        drops[i]++;
    }}
}}
setInterval(draw, 35);

// SAMPLE CHART DATA
var trace = {{
    x: ["2024-01-01","2024-01-02","2024-01-03","2024-01-04"],
    open: [140,155,160,165],
    high: [165,170,165,175],
    low: [135,150,150,160],
    close: [150,160,155,170],
    type: "candlestick",
    increasing: {{line: {{color: "black"}}, fillcolor: "#DA70D6"}}, // orchid pink up
    decreasing: {{line: {{color: "black"}}, fillcolor: "black"}},   // black down
    xaxis: "x",
    yaxis: "y"
}};

var volume = {{
    x: ["2024-01-01","2024-01-02","2024-01-03","2024-01-04"],
    y: [1000,2000,1500,2500],
    type: "bar",
    marker: {{color: ["#DA70D6","black","#DA70D6","#DA70D6"]}},
    xaxis: "x",
    yaxis: "y2"
}};

var layout = {{
    dragmode: "zoom",
    showlegend: false,
    margin: {{t:40}},
    xaxis: {{rangeslider: {{visible:false}}}},
    yaxis: {{title:"Price"}},
    yaxis2: {{
        title: "Volume",
        overlaying: "y",
        side: "right",
        showgrid: false,
        position: 0.15
    }},
    plot_bgcolor: "black",
    paper_bgcolor: "black"
}};

Plotly.newPlot("chart", [trace, volume], layout);
</script>
</body>
</html>
    """
    return render_template_string(page)

# ----------------------------
# WEBHOOK
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        print("📩 Webhook received:", data)
        if not data:
            return jsonify({"error": "No JSON received"}), 400

        symbol = data.get("symbol")
        qty = data.get("qty")
        side = data.get("side")

        if not all([symbol, qty, side]):
            return jsonify({"error": "Missing parameters"}), 400

        side = side.lower()

        if side in ["buy","sell"]:
            order = api.submit_order(
                symbol=symbol, qty=qty, side=side,
                type="market", time_in_force="gtc"
            )
            return jsonify({"status":"order_submitted","id":order.id})
        elif side in ["close_long","close_short"]:
            api.close_position(symbol)
            return jsonify({"status":"position_closed"})
        else:
            return jsonify({"error":"Invalid side"}), 400

    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({"error": str(e)}), 500

# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port)






