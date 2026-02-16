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
# Home route with hacker terminal + TradingView chart + stats
@app.route("/", methods=["GET"])
def home():
    # Trading session
    try:
        clock = api.get_clock()
        session_status = "OPEN 🟢" if clock.is_open else "CLOSED 🔴"
    except:
        session_status = "UNKNOWN"

    # Example stats
    pnl = "$1,245.33"
    recent_trade = "NFLX BUY 1"

    # Current positions for box under chart
    try:
        positions = api.list_positions()
        pos_html = ""
        for p in positions:
            side = "LONG" if int(p.qty) > 0 else "SHORT"
            pos_html += f"{p.symbol}: {side} {abs(int(p.qty))} @ ${p.avg_entry_price}<br>"
        if not pos_html:
            pos_html = "No open positions"
    except:
        pos_html = "Cannot fetch positions"

    page = f"""
<!DOCTYPE html>
<html>
<head>
<title>TradeClaw Terminal</title>
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
    margin-bottom: 10px;
    font-size: 16px;
}}
.stat-box {{
    display: inline-block;
    margin-right: 25px;
}}
.stats-message {{
    font-size: 18px;
    color: #ff2bd6;
    text-shadow: 0 0 15px #ff2bd6;
    margin-bottom: 20px;
}}
#chart {{
    height: 600px;
}}
#positions-box {{
    margin-top: 20px;
    padding: 15px;
    border: 2px solid #ff2bd6;
    box-shadow: 0 0 20px #ff2bd6;
    background: rgba(0,0,0,0.8);
    font-size: 16px;
}}
</style>
</head>
<body>

<canvas id="matrix"></canvas>

<div class="container">
    <div class="title">TradeClaw</div>

    <!-- TOP STATS -->
    <div class="stats">
        <div class="stat-box">PnL: {pnl}</div>
        <div class="stat-box">Recent Trade: {recent_trade}</div>
        <div class="stat-box">Trading Session: {session_status}</div>
    </div>

    <!-- NEON TAGLINE -->
    <div class="stats-message">Automated trades, proven results.</div>

    <!-- TRADINGVIEW CHART -->
    <div id="chart">
        <iframe 
            src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_12345&symbol=NASDAQ%3ANFLX&interval=15&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=000000&studies=[]&theme=dark&style=1&timezone=Etc%2FUTC&studies_overrides={{'volume.volume.color.0':'#DA70D6','volume.volume.color.1':'#000000','volume.volume.transparency':0,'volume.volume ma.color':'#DA70D6','mainSeriesProperties.candleStyle.upColor':'#DA70D6','mainSeriesProperties.candleStyle.downColor':'#000000','mainSeriesProperties.candleStyle.wickUpColor':'#000000','mainSeriesProperties.candleStyle.wickDownColor':'#000000'}}"
            style="width:100%; height:600px; border:0;" allowtransparency="true" frameborder="0"></iframe>
    </div>

    <!-- CURRENT POSITIONS -->
    <div id="positions-box">
        <strong>Current Positions:</strong><br>
        {pos_html}
    </div>

</div>

<script>
// MATRIX GREEN RAIN
const canvas = document.getElementById("matrix");
const ctx = canvas.getContext("2d");

canvas.height = window.innerHeight;
canvas.width = window.innerWidth;

const letters = "01ABCDEFGHIJKLMNOPQRSTUVWXYZ$#@%&*";
const fontSize = 16;
const columns = Math.floor(canvas.width / fontSize);
const drops = Array(columns).fill(1);

function draw() {{
    ctx.fillStyle = "rgba(0, 0, 0, 0.05)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#00ff00";
    ctx.font = fontSize + "px monospace";
    for (let i = 0; i < drops.length; i++) {{
        const text = letters[Math.floor(Math.random() * letters.length)];
        ctx.fillText(text, i * fontSize, drops[i] * fontSize);
        if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) drops[i] = 0;
        drops[i]++;
    }}
}}
setInterval(draw, 35);
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
        print("❌ Error:", str(e))
        return jsonify({"error": str(e)}), 500

# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port)





