from dotenv import load_dotenv
import os
<<<<<<< HEAD
=======
from flask import Flask, request, jsonify
>>>>>>> c2e1067 (Fix port binding for Render)
import alpaca_trade_api as tradeapi

load_dotenv()
app = Flask(__name__)

<<<<<<< HEAD
# ----------------------------
# Load Alpaca credentials
# ----------------------------
API_KEY = os.environ.get("APCA_API_KEY_ID")
API_SECRET = os.environ.get("APCA_API_SECRET_KEY")
BASE_URL = os.environ.get("APCA_API_BASE_URL")
=======
API_KEY = os.environ.get("APCA_API_KEY_ID")
API_SECRET = os.environ.get("APCA_API_SECRET_KEY")
BASE_URL = os.environ.get("APCA_API_BASE_URL")

if not all([API_KEY, API_SECRET, BASE_URL]):
    raise ValueError("Alpaca API keys or base URL not set in environment variables!")

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')
>>>>>>> c2e1067 (Fix port binding for Render)

if not API_KEY or not API_SECRET or not BASE_URL:
    raise ValueError("Alpaca API keys or base URL not set in environment variables!")

# Connect to Alpaca
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# ----------------------------
# Home route for testing
# ----------------------------
@app.route("/")
def home():
    return "Trading Bot is Running"

# ----------------------------
# Webhook route for TradingView alerts
# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
<<<<<<< HEAD
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON received"}), 400

        # Extract TradingView alert info
        symbol = data.get("symbol")
        side = data.get("side")  # should be 'buy' or 'sell'
        qty = int(data.get("qty", 1))  # default 1 if not provided

        if not symbol or not side:
            return jsonify({"error": "Missing symbol or side"}), 400

        side = side.lower()
        if side not in ["buy", "sell"]:
            return jsonify({"error": "Side must be 'buy' or 'sell'"}), 400

        # Submit the order to Alpaca
        order = api.submit_order(
            symbol=symbol,
            qty=qty,
            side=side,
            type="market",
            time_in_force="gtc"
        )

        print(f"✅ Order submitted: {side.upper()} {qty} {symbol}")
        return jsonify({"status": "success", "order_id": order.id})

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"error": str(e)}), 400
=======
    data = request.get_json(force=True)
    symbol = data.get("symbol")
    qty = data.get("qty")
    side = data.get("side")

    if not all([symbol, qty, side]):
        return jsonify({"error": "Missing parameters"}), 400

    try:
        order = api.submit_order(symbol=symbol, qty=qty, side=side.lower(),
                                 type="market", time_in_force="gtc")
        print(f"✅ Order submitted: {side.upper()} {qty} {symbol}")
        return jsonify({"status": "success", "order_id": order.id})
    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error": str(e)}), 500
>>>>>>> c2e1067 (Fix port binding for Render)

# ----------------------------
# Run app
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    print(f"🚀 Flask app running on port {port}")
    app.run(host="0.0.0.0", port=port)
