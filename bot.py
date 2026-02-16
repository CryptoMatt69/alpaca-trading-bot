import os
from flask import Flask, request, jsonify, render_template_string
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
from datetime import datetime
import pytz

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
# Home route
@app.route("/", methods=["GET"])
def home():
    # ---------------- Dynamic session (Market open/close + EST time)
    try:
        clock = api.get_clock()
        est_now = datetime.now(pytz.timezone("US/Eastern")).strftime("%I:%M:%S %p EST")
        session_status = f"{'OPEN 🟢' if clock.is_open else 'CLOSED 🔴'} ({est_now})"
    except:
        session_status = "UNKNOWN"

    # ---------------- Dynamic stats (PnL + Recent Trade)
    try:
        account = api.get_account()
        pnl_value = float(account.equity) - float(account.cash)
        pnl = f"${pnl_value:,.2f}"
        recent_trade = "N/A"
        trades = api.list_orders(status='closed', limit=1, order_by='created_at', direction='desc')
        if trades:
            t = trades[0]
            recent_trade = f"{t.symbol} {t.side.upper()} {t.filled_qty}"
    except:
        pnl_value = 0.00
        pnl = "$0.00"
        recent_trade = "N/A"

    # ---------------- Current positions
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

    # ---------------- HTML Page
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
    padding: 10px;
    max-width: 1400px;
    margin: auto;
}}
.title {{
    font-size: 56px;
    font-weight: 900;
    color: #ff2bd6;
    text-shadow: 0 0 30px #ff2bd6, 0 0 60px #ff2bd6;
    margin-bottom: 15px;
    transition: 0.3s;
}}
.title:hover {{
    text-shadow: 0 0 50px #ff2bd6, 0 0 100px #ff2bd6;
}}
.glow-box {{
    border: 2px solid #ff2bd6;
    box-shadow: 0 0 25px #ff2bd6, 0 0 50px #ff2bd6 inset;
    padding: 15px;
    margin-bottom: 15px;
    background: rgba(0,0,0,0.85);
    transition: box-shadow 0.5s ease;
}}
.glow-box:hover {{
    box-shadow: 0 0 50px #ff2bd6, 0 0 100px #ff2bd6 inset;
}}
.stat-box {{
    display: block;
    margin: 5px 0;
    font-size: 16px;
    transition: all 0.3s ease;
}}
.stat-box.pulse {{
    animation: pulseStat 1.5s infinite;
}}
@keyframes pulseStat {{
    0% {{ text-shadow: 0 0 5px #00ff00; }}
    50% {{ text-shadow: 0 0 15px #00ff00; }}
    100% {{ text-shadow: 0 0 5px #00ff00; }}
}}
#chart {{
    height: 500px;
    border: 2px solid #ff2bd6;
    box-shadow: 0 0 25px #ff2bd6;
}}
#positions-box {{
    margin-top: 15px;
    padding: 15px;
    border: 2px solid #ff2bd6;
    box-shadow: 0 0 25px #ff2bd6;
    background: rgba(0,0,0,0.85);
    font-size: 16px;
}}
.message-box {{
    margin-top: 10px;
    font-size: 20px;
    text-align: center;
    color: #00ff00;
    text-shadow: 0 0 15px #00ff00, 0 0 30px #00ff00;
    animation: pulse 2s infinite;
}}
@keyframes pulse {{
    0% {{ text-shadow: 0 0 15px #00ff00, 0 0 30px #00ff00; }}
    50% {{ text-shadow: 0 0 25px #00ff00, 0 0 50px #00ff00; }}
    100% {{ text-shadow: 0 0 15px #00ff00, 0 0 30px #00ff00; }}
}}
</style>
</head>
<body>

<audio id="ding" src="https://www.soundjay.com/button/sounds/button-3.mp3"></audio>

<canvas id="matrix"></canvas>

<div class="container">
    <div class="title">🤖 TradeClaw</div>

    <div class="glow-box">
        <div class="stat-box" id="pnl">PnL: {pnl}</div>
        <div class="stat-box">Recent Trade: {recent_trade}</div>
        <div class="stat-box">Trading Session: {session_status}</div>
        <div class="message-box">Automated trades, Proven results.</div>
    </div>

    <!-- TRADINGVIEW CHART -->
    <div id="chart" class="glow-box"></div>

    <!-- CURRENT POSITIONS -->
    <div id="positions-box" class="glow-box">
        <strong>Current Positions:</strong><br>
        {pos_html}
    </div>
</div>

<script src="https://s3.tradingview.com/tv.js"></script>
<script>
new TradingView.widget({{
  "width": "100%",
  "height": 500,
  "symbol": "NASDAQ:NFLX",
  "interval": "15",
  "timezone": "Etc/UTC",
  "theme": "dark",
  "style": "1",
  "locale": "en",
  "container_id": "chart",
  "hide_side_toolbar": true,
  "allow_symbol_change": true,
  "studies": [],
  "overrides": {{
    "mainSeriesProperties.candleStyle.upColor": "#DA70D6",
    "mainSeriesProperties.candleStyle.downColor": "#000000",
    "mainSeriesProperties.candleStyle.wickUpColor": "#000000",
    "mainSeriesProperties.candleStyle.wickDownColor": "#000000",
    "volume.volume.color.0": "#DA70D6",
    "volume.volume.color.1": "#000000",
    "volume.volume.transparency": 0
  }}
}});
</script>

<script>
// MATRIX GREEN RAIN
const canvas = document.getElementById("matrix");
const ctx = canvas.getContext("2d");
canvas.height = window.innerHeight;
canvas.width = window.innerWidth;
const letters = "01ABCDEFGHIJKLMNOPQRSTUVWXYZ$#@%&*";
const fontSize = 14;
const columns = Math.floor(canvas.width / fontSize);
const drops = Array.from({length: columns}, () => 1);
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

