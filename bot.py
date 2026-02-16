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
# Home route
@app.route("/", methods=["GET"])
def home():
    return {"status": "TradeClaw running"}

# ----------------------------
# 📊 ACTIVE POSITIONS DASHBOARD
@app.route("/positions", methods=["GET"])
def positions():

    try:
        positions = api.list_positions()

        html = """
        <html>
        <head>
            <title>TradeClaw Active Positions</title>
            <style>
                body { font-family: Arial; background-color: #111; color: white; }
                table { border-collapse: collapse; width: 100%; margin-top: 20px; }
                th, td { padding: 10px; text-align: center; }
                th { background-color: #222; }
                tr:nth-child(even) { background-color: #1a1a1a; }
                .profit { color: #00ff99; }
                .loss { color: #ff4d4d; }
                h1 { text-align: center; }
            </style>
        </head>
        <body>
            <h1>📊 Active Trades</h1>
            <table border="1">
                <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Qty</th>
                    <th>Avg Entry</th>
                    <th>Current Price</th>
                    <th>Unrealized P/L</th>
                </tr>
        """

        for pos in positions:
            pl = float(pos.unrealized_pl)
            pl_class = "profit" if pl >= 0 else "loss"

            html += f"""
                <tr>
                    <td>{pos.symbol}</td>
                    <td>{pos.side.upper()}</td>
                    <td>{pos.qty}</td>
                    <td>${float(pos.avg_entry_price):.2f}</td>
                    <td>${float(pos.current_price):.2f}</td>
                    <td class="{pl_class}">${pl:.2f}</td>
                </tr>
            """

        html += """
            </table>
        </body>
        </html>
        """

        return html

    except Exception as e:
        return f"Error loading positions: {str(e)}"

# ----------------------------
# Webhook route
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

        side_lower = side.lower()
        order = None

        # BUY
        if side_lower == "buy":
            order = api.submit_order(
                symbol=symbol,
                qty=qty,
                side="buy",
                type="market",
                time_in_force="gtc"
            )

        # SELL
        elif side_lower == "sell":
            order = api.submit_order(
                symbol=symbol,
                qty=qty,
                side="sell",
                type="market",
                time_in_force="gtc"
            )

        # SHORT ENTRY
        elif side_lower == "short":
            order = api.submit_order(
                symbol=symbol,
                qty=qty,
                side="sell",
                type="market",
                time_in_force="gtc"
            )

        # CLOSE LONG
        elif side_lower == "close_long":
            try:
                api.close_position(symbol)
                return jsonify({"status": "closed_long"})
            except tradeapi.rest.APIError:
                return jsonify({"status": "no_long_position"})

        # CLOSE SHORT
        elif side_lower == "close_short":
            try:
                api.close_position(symbol)
                return jsonify({"status": "closed_short"})
            except tradeapi.rest.APIError:
                return jsonify({"status": "no_short_position"})

        else:
            return jsonify({"error": "Invalid side"}), 400

        order_id = order.id if hasattr(order, "id") else "N/A"

        print(f"✅ Order placed: {side.upper()} {qty} {symbol} | ID: {order_id}")

        return jsonify({
            "status": "success",
            "order_id": order_id
        })

    except Exception as e:
        print("❌ Webhook error:", e)
        return jsonify({"error": str(e)}), 500

# ----------------------------
# Run server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    print(f"🚀 TradeClaw running on port {port}")
    app.run(host="0.0.0.0", port=port, threaded=True)




