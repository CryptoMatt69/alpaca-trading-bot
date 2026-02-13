from dotenv import load_dotenv
import os
from flask import Flask, request, jsonify
import alpaca_trade_api as tradeapi

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# ----------------------------
# Load Alpaca credentials
# ----------------------------
API_KEY = os.environ.get("APCA_API_KEY_ID")
API_SECRET = os.environ.get("APCA_API_SECRET_KEY")
BASE_URL = os.environ.get("APCA_API_BASE_URL")

if not all([API_KEY, API_SECRET, BASE_URL]):
    raise ValueError("Alpaca API keys or base URL not set in environment variables!")

# Initialize Alpaca API
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    symbol = data.get("symbol")  
    qty = data.get("qty")
    side = data.get("side")

    if not all([symbol, qty, side]):
        return jsonify({"error": "Missing parameters"}), 400

    try:
        if side.lower() == "buy":
            order = api.submit_order(symbol=symbol, qty=qty, side="buy", type="market", time_in_force="gtc")
        elif side.lower() == "sell":
            order = api.submit_order(symbol=symbol, qty=qty, side="sell", type="market", time_in_force="gtc")
        else:
            return jsonify({"error": "Invalid side"}), 400

        print(f"✅ Order submitted: {side.upper()} {qty} {symbol}")
        return jsonify({"status": "success", "order_id": order.id})
    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))  # Use Render-assigned port or 5100 locally
    app.run(host="0.0.0.0", port=port)
