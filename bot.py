import os
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
# Health check route (optional but useful)
@app.route("/", methods=["GET"])
def home():
    return {"status": "TradeClaw running"}

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

        # ----------------------------
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
                position = api.get_position(symbol)
                if int(position.qty) > 0:
                    api.close_position(symbol)
                    return jsonify({"status": "closed_long"})
                else:
                    return jsonify({"status": "no_long_position"})
            except tradeapi.rest.APIError:
                return jsonify({"status": "no_long_position"})

        # CLOSE SHORT
        elif side_lower == "close_short":
            try:
                position = api.get_position(symbol)
                if int(position.qty) < 0:
                    api.close_position(symbol)
                    return jsonify({"status": "closed_short"})
                else:
                    return jsonify({"status": "no_short_position"})
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



