import os
from flask import Flask, request, jsonify
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

# ----------------------------
# Load environment variables
# ----------------------------
load_dotenv()

app = Flask(__name__)

API_KEY = os.environ.get("APCA_API_KEY_ID")
API_SECRET = os.environ.get("APCA_API_SECRET_KEY")
BASE_URL = os.environ.get("APCA_API_BASE_URL")

if not API_KEY or not API_SECRET or not BASE_URL:
    raise Exception("Missing Alpaca environment variables")

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

# ----------------------------
# HOME ROUTE (Important for Render)
# ----------------------------
@app.route("/")
def home():
    return "TradeClaw is running 🚀"

# ----------------------------
# POSITIONS DASHBOARD
# ----------------------------
@app.route("/positions")
def positions():
    try:
        positions = api.list_positions()

        html = """
        <html>
        <head>
            <title>TradeClaw Positions</title>
            <style>
                body { background:#111; color:white; font-family:Arial; }
                table { width:100%; border-collapse:collapse; margin-top:20px; }
                th, td { padding:10px; text-align:center; border:1px solid #333; }
                th { background:#222; }
                .profit { color:#00ff99; }
                .loss { color:#ff4d4d; }
            </style>
        </head>
        <body>
        <h1>Active Positions</h1>
        <table>
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

        html += "</table></body></html>"
        return html

    except Exception as e:
        return f"Error loading positions: {str(e)}"


# ----------------------------
# WEBHOOK
# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        print("Webhook received:", data)

        if not data:
            return jsonify({"error": "No JSON received"}), 400

        symbol = data.get("symbol")
        qty = data.get("qty")
        side = data.get("side")

        if not symbol or not qty or not side:
            return jsonify({"error": "Missing parameters"}), 400

        side = side.lower()

        # BUY
        if side == "buy":
            order = api.submit_order(
                symbol=symbol,
                qty=qty,
                side="buy",
                type="market",
                time_in_force="gtc"
            )

        # SELL
        elif side == "sell":
            order = api.submit_order(
                symbol=symbol,
                qty=qty,
                side="sell",
                type="market",
                time_in_force="gtc"
            )

        # CLOSE LONG / SHORT
        elif side in ["close_long", "close_short"]:
            try:
                api.close_position(symbol)
                return jsonify({"status": "position_closed"})
            except:
                return jsonify({"status": "no_position"})

        else:
            return jsonify({"error": "Invalid side"}), 400

        return jsonify({
            "status": "success",
            "order_id": order.id
        })

    except Exception as e:
        print("Webhook error:", e)
        return jsonify({"error": str(e)}), 500


# ----------------------------
# IMPORTANT FOR RENDER
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port)



