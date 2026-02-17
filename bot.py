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
# Track open positions to prevent instant flip
open_positions = {}  # key: symbol, value: 'long' or 'short'

# ----------------------------
@app.route("/", methods=["GET"])
def home():
    page = """
    <!DOCTYPE html>
    <html>
    <head>
    <title>TradeClaw Premium Terminal</title>
    <style>
    html, body { background-color: #0d0d0d; color: white; font-family: 'Roboto Mono', monospace; }
    .container { max-width: 1300px; margin: 20px auto; padding: 10px; }
    .title { font-size: 60px; font-weight: 900; text-align: center; background: linear-gradient(90deg, #ff2bd6, #ff7f50); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 30px; }
    .card { background: rgba(0,0,0,0.85); border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0 0 40px rgba(255, 43, 214, 0.5); }
    .card h2 { margin-top: 0; font-size: 24px; color: #ff2bd6; }
    .stat { font-size: 18px; margin: 5px 0; }
    .chart-select { display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
    .chart-select input, .chart-select select { padding: 5px 10px; border-radius: 8px; border: none; font-size: 16px; }
    .chart-select button { padding: 5px 12px; border-radius: 8px; border: none; background: #ff2bd6; color: #fff; cursor: pointer; font-weight: bold; transition: 0.2s; }
    .chart-select button:hover { background: #ff7f50; }
    .message-box { text-align: center; font-size: 20px; color: #00ff00; text-shadow: 0 0 10px #00ff00; margin-top: 10px; }
    #chart { width: 100%; height: 500px; border-radius: 15px; overflow: hidden; box-shadow: 0 0 40px rgba(255, 43, 214, 0.5); margin-bottom: 20px; }
    #multi_chart_container { display: none; margin-top: 20px; gap: 10px; }
    </style>
    </head>
    <body>

    <div class="container">
        <div class="title">🤖 TradeClaw Premium</div>

        <div class="card">
            <h2>Account Overview</h2>
            <div class="stat">Balance: <span id="balance">$0.00</span></div>
            <div class="stat">Daily PnL: <span id="pnl">$0.00</span></div>
            <div class="stat">Recent Trade: <span id="recent_trade">N/A</span></div>
            <div class="stat">Trading Session: <span id="session_status">Loading...</span></div>
            <div class="message-box">Automated trades, Proven results.</div>
        </div>

        <div class="card">
            <h2>TradingView Chart</h2>
            <div class="chart-select">
                <input type="text" id="chart_symbol" placeholder="Single Symbol e.g. AAPL" />
                <select id="chart_interval">
                    <option value="1">1 min</option>
                    <option value="5">5 min</option>
                    <option value="15" selected>15 min</option>
                    <option value="60">1 hr</option>
                    <option value="D">Daily</option>
                </select>
                <button onclick="updateChart()">Load Chart</button>
                <button onclick="toggleMultiView()">Show Multi-View</button>
                <label>Charts Count:
                    <input type="number" id="multi_count" value="4" min="1" max="10" style="width:60px"/>
                </label>
            </div>

            <div id="chart">
                <iframe id="chart_iframe" 
                    src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_12345&symbol=NASDAQ%3AAAPL&interval=15&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=000000&studies=[]&theme=dark&style=1&timezone=Etc%2FUTC"
                    style="width:100%; height:500px;" allowtransparency="true" frameborder="0"></iframe>
            </div>

            <div id="multi_chart_container"></div>
        </div>

        <div class="card">
            <h2>Current Positions</h2>
            <div id="positions_box">Loading...</div>
        </div>
    </div>

    <script>
    // Your original dashboard JS here (unchanged)
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
        balance = float(account.portfolio_value)
        pnl = float(account.day_trade_pl)
        balance_str = f"${balance:,.2f}"
        pnl_str = f"${pnl:,.2f}"

        trades = api.list_orders(status='closed', limit=1, order_by='created_at', direction='desc')
        recent_trade = f"{trades[0].symbol} {trades[0].side.upper()} {trades[0].filled_qty}" if trades else "N/A"

    except:
        balance_str = "$0.00"
        pnl_str = "$0.00"
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
        "balance": balance_str,
        "pnl": pnl_str,
        "recent_trade": recent_trade,
        "session_status": session_status,
        "positions": pos_list
    })

# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("Incoming webhook:", data)

        symbol = data.get("symbol")
        qty = int(data.get("qty", 1))
        side = data.get("side", "").lower()

        if not symbol or not side:
            return jsonify({"error": "Missing symbol or side"}), 400

        # Normalize signals
        if side == "long":
            side = "buy"
        elif side == "short":
            side = "sell"

        # ---------------- LONG ENTRY ----------------
        if side == "buy":
            if open_positions.get(symbol) == "long":
                return jsonify({"status": "long_already_open"})
            order = api.submit_order(
                symbol=symbol,
                qty=qty,
                side="buy",
                type="market",
                time_in_force="day"
            )
            open_positions[symbol] = "long"
            return jsonify({"status": "long_opened", "order_id": order.id})

        # ---------------- SHORT ENTRY ----------------
        elif side == "sell":
            if open_positions.get(symbol) == "short":
                return jsonify({"status": "short_already_open"})
            order = api.submit_order(
                symbol=symbol,
                qty=qty,
                side="sell",
                type="market",
                time_in_force="day"
            )
            open_positions[symbol] = "short"
            return jsonify({"status": "short_opened", "order_id": order.id})

        # ---------------- CLOSE LONG ----------------
        elif side == "close_long":
            api.close_position(symbol)
            open_positions.pop(symbol, None)
            return jsonify({"status": "long_closed"})

        # ---------------- CLOSE SHORT ----------------
        elif side == "close_short":
            api.close_position(symbol)
            open_positions.pop(symbol, None)
            return jsonify({"status": "short_closed"})

        else:
            return jsonify({"error": f"Invalid side: {side}"}), 400

    except Exception as e:
        print("WEBHOOK ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port)





