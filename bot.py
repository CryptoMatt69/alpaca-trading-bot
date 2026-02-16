import os
import datetime
from flask import Flask, request, jsonify
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
    raise ValueError("Alpaca API keys not set!")

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

# ----------------------------
trade_log = []
last_trade_side = None

ORCHID = "#DA70D6"  # Orchid Pink
BLACK = "#000000"
LIGHT_GRAY = "#f2f2f2"

# ----------------------------
@app.route("/", methods=["GET"])
def home():
    global last_trade_side

    try:
        account = api.get_account()
        equity = float(account.equity)
        buying_power = float(account.buying_power)
        pnl = float(account.unrealized_pl)
    except:
        equity = 0
        buying_power = 0
        pnl = 0

    flash_color = "transparent"
    if last_trade_side == "buy":
        flash_color = "#00ff99"
    elif last_trade_side in ["sell", "short"]:
        flash_color = "#ff3b3b"

    last_trade_display = trade_log[-1] if trade_log else "No trades yet"

    return f"""
<html>
<head>
<title>TradeClaw</title>

<style>
body {{
    margin:0;
    font-family:Arial, sans-serif;
    color:white;
    overflow-x:hidden;
    background:black;
}}

canvas {{
    position:fixed;
    top:0;
    left:0;
    z-index:-1;
}}

.container {{
    padding:40px;
    text-align:center;
}}

.card {{
    margin:auto;
    padding:30px;
    width:550px;
    border-radius:20px;
    background:#111;
    animation:glow 2s infinite alternate;
    box-shadow:0 0 20px {ORCHID};
}}

@keyframes glow {{
    from {{ box-shadow: 0 0 15px {ORCHID}; }}
    to {{ box-shadow: 0 0 35px {ORCHID}; }}
}}

.flash {{
    animation:flash 0.6s;
}}

@keyframes flash {{
    0% {{ background:{flash_color}; }}
    100% {{ background:#111; }}
}}

.metric {{
    font-size:18px;
    margin:8px 0;
}}

.positive {{ color:#00ff99; }}
.negative {{ color:#ff3b3b; }}

iframe {{
    margin-top:30px;
    border-radius:20px;
    box-shadow:0 0 30px {ORCHID};
}}
</style>
</head>

<body>

<canvas id="matrix"></canvas>

<div class="container">
    <div class="card flash">
        <h1 style="color:{ORCHID};">🤖 TradeClaw</h1>
        <div style="color:#00ff99; font-size:20px;">LIVE & READY</div>

        <div class="metric">💰 Equity: ${equity:,.2f}</div>
        <div class="metric">⚡ Buying Power: ${buying_power:,.2f}</div>

        <div class="metric">
            📈 Live PnL:
            <span class="{ 'positive' if pnl >= 0 else 'negative' }">
                ${pnl:,.2f}
            </span>
        </div>

        <div class="metric">🔔 Last Trade: {last_trade_display}</div>
        <div class="metric" style="opacity:0.6;">
            Server Time: {datetime.datetime.utcnow()} UTC
        </div>
    </div>

    <iframe
        src="https://s.tradingview.com/widgetembed/?symbol=NASDAQ:TSLA&interval=15&theme=light&style=1&toolbarbg=f2f2f2&studies=[]&hide_side_toolbar=false&allow_symbol_change=true&save_image=false&hideideas=true&overrides=%7B
        %22paneProperties.background%22%3A%22{LIGHT_GRAY.replace('#','%23')}%22%2C
        %22paneProperties.vertGridProperties.color%22%3A%22transparent%22%2C
        %22paneProperties.horzGridProperties.color%22%3A%22transparent%22%2C
        %22mainSeriesProperties.candleStyle.upColor%22%3A%22%23DA70D6%22%2C
        %22mainSeriesProperties.candleStyle.downColor%22%3A%22%23000000%22%2C
        %22mainSeriesProperties.candleStyle.wickUpColor%22%3A%22%23000000%22%2C
        %22mainSeriesProperties.candleStyle.wickDownColor%22%3A%22%23000000%22%2C
        %22mainSeriesProperties.candleStyle.borderUpColor%22%3A%22%23DA70D6%22%2C
        %22mainSeriesProperties.candleStyle.borderDownColor%22%3A%22%23000000%22%2C
        %22volume.volume.color.0%22%3A%22%23DA70D6%22%2C
        %22volume.volume.color.1%22%3A%22%23000000%22
        %7D"
        width="950"
        height="550"
        frameborder="0"
        allowtransparency="true"
        scrolling="no">
    </iframe>
</div>

<script>
// MATRIX BACKGROUND EFFECT
var canvas = document.getElementById("matrix");
var ctx = canvas.getContext("2d");

canvas.height = window.innerHeight;
canvas.width = window.innerWidth;

var letters = "01TRADECLAWBOT";
letters = letters.split("");

var fontSize = 14;
var columns = canvas.width/fontSize;
var drops = [];

for(var x = 0; x < columns; x++)
    drops[x] = 1;

function draw() {{
    ctx.fillStyle = "rgba(0, 0, 0, 0.05)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = "#00ff00";
    ctx.font = fontSize + "px monospace";

    for(var i = 0; i < drops.length; i++) {{
        var text = letters[Math.floor(Math.random()*letters.length)];
        ctx.fillText(text, i*fontSize, drops[i]*fontSize);

        if(drops[i]*fontSize > canvas.height && Math.random() > 0.975)
            drops[i] = 0;

        drops[i]++;
    }}
}}

setInterval(draw, 33);
</script>

</body>
</html>
"""

# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    global last_trade_side
    try:
        data = request.get_json()

        symbol = data.get("symbol")
        qty = data.get("qty")
        side = data.get("side")

        if not all([symbol, qty, side]):
            return jsonify({"error": "Missing parameters"}), 400

        side_lower = side.lower()
        order = None

        if side_lower == "buy":
            order = api.submit_order(symbol=symbol, qty=qty, side="buy", type="market", time_in_force="gtc")
            last_trade_side = "buy"

        elif side_lower == "sell":
            order = api.submit_order(symbol=symbol, qty=qty, side="sell", type="market", time_in_force="gtc")
            last_trade_side = "sell"

        elif side_lower == "short":
            order = api.submit_order(symbol=symbol, qty=qty, side="sell", type="market", time_in_force="gtc")
            last_trade_side = "short"

        elif side_lower == "close_long":
            api.close_position(symbol)
            last_trade_side = "sell"
            return jsonify({"status": "closed_long"})

        elif side_lower == "close_short":
            api.close_position(symbol)
            last_trade_side = "buy"
            return jsonify({"status": "closed_short"})

        else:
            return jsonify({"error": "Invalid side"}), 400

        trade_log.append(f"{symbol} {side.upper()} {qty}")
        return jsonify({"status": "success", "order_id": order.id})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------
@app.route("/health")
def health():
    return jsonify({"status": "running"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port, threaded=True)




