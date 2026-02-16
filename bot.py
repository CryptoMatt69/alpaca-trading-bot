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
    raise ValueError("Alpaca API keys or base URL not set in environment variables!")

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

# ----------------------------
# Trade memory
trade_log = []
last_trade_side = None

# ----------------------------
# Neon Dashboard Homepage
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
                background:#000;
                font-family:Arial, sans-serif;
                color:white;
                text-align:center;
            }}

            .container {{
                padding:40px;
            }}

            .card {{
                margin:auto;
                padding:30px;
                width:550px;
                border-radius:20px;
                background:#111;
                animation:glow 2s infinite alternate;
                box-shadow:0 0 20px #ff00ff;
            }}

            @keyframes glow {{
                from {{ box-shadow: 0 0 15px #ff00ff; }}
                to {{ box-shadow: 0 0 35px #ff00ff; }}
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
                box-shadow:0 0 20px #ff00ff;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card flash">
                <h1 style="color:#ff00ff;">🦅 TradeClaw</h1>
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

            <!-- TradingView Embed -->
            <iframe
                src="https://s.tradingview.com/widgetembed/?symbol=NASDAQ:TSLA&interval=15&theme=dark&style=1&toolbarbg=000000&studies=[]&hide_side_toolbar=false&allow_symbol_change=true&save_image=false&hideideas=true&overrides=%7B%22mainSeriesProperties.candleStyle.upColor%22%3A%22%23ff00ff%22%2C%22mainSeriesProperties.candleStyle.downColor%22%3A%22%23000000%22%7D"
                width="900"
                height="550"
                frameborder="0"
                allowtransparency="true"
                scrolling="no">
            </iframe>
        </div>
    </body>
    </html>
    """

# ----------------------------
# Webhook route
@app.route("/webhook", methods=["POST"])
def webhook():
    global last_trade_side

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
            try:
                position = api.get_position(symbol)
                if int(position.qty) > 0:
                    api.close_position(symbol)
                    last_trade_side = "sell"
                    return jsonify({"status": "closed_long"})
                else:
                    return jsonify({"status": "no_long_position"})
            except tradeapi.rest.APIError:
                return jsonify({"status": "no_long_position"})

        elif side_lower == "close_short":
            try:
                position = api.get_position(symbol)
                if int(position.qty) < 0:
                    api.close_position(symbol)
                    last_trade_side = "buy"
                    return jsonify({"status": "closed_short"})
                else:
                    return jsonify({"status": "no_short_position"})
            except tradeapi.rest.APIError:
                return jsonify({"status": "no_short_position"})

        else:
            return jsonify({"error": "Invalid side"}), 400

        order_id = order.id if hasattr(order, "id") else "N/A"

        trade_log.append(f"{symbol} {side_upper := side_upper if False else side.upper()} {qty}")

        print(f"✅ Order placed: {side.upper()} {qty} {symbol} | ID: {order_id}")

        return jsonify({
            "status": "success",
            "order_id": order_id
        })

    except Exception as e:
        print("❌ Webhook error:", e)
        return jsonify({"error": str(e)}), 500


# ----------------------------
# Health endpoint
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "running",
        "timestamp": datetime.datetime.utcnow().isoformat()
    })


# ----------------------------
# Run server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    print(f"🚀 TradeClaw running on port {port}")
    app.run(host="0.0.0.0", port=port, threaded=True)




