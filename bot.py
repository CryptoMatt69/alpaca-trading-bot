from dotenv import load_dotenv
import os
from flask import Flask, request, jsonify
import alpaca_trade_api as tradeapi

# Load .env locally (ignored on Render)
load_dotenv()
app = Flask(__name__)

# Alpaca credentials
API_KEY = os.environ.get("APCA_API_KEY_ID")
API_SECRET = os.environ.get("APCA_API_SECRET_KEY")
BASE_URL = os.environ.get("APCA_API_BASE_URL")

if not all([API_KEY, API_SECRET, BASE_URL]):
    raise ValueError("Alpaca API keys or base URL not set in environment variables!")

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# ----------------------------
# Home route
@app.route("/", methods=["GET"])
def home():
    return "You have awoken TradeClaw🤖... Welcome to the future of trading!\nComing Soon..."

# ----------------------------
# Webhook route
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    symbol = data.get("symbol")
    qty = data.get("qty")
    side = data.get("side")

    if not all([symbol, qty, side]):
        return jsonify({"error": "Missing parameters"}), 400

    try:
        side_lower = side.lower()

        # Buy
        if side_lower == "buy":
            order = api.submit_order(symbol=symbol, qty=qty, side="buy", type="market", time_in_force="gtc")

        # Sell
        elif side_lower == "sell":
            order = api.submit_order(symbol=symbol, qty=qty, side="sell", type="market", time_in_force="gtc")

        # Short (entry)
        elif side_lower == "short":
            order = api.submit_order(symbol=symbol, qty=qty, side="sell", type="market", time_in_force="gtc")

        # Close Long safely
        elif side_lower == "close_long":
            try:
                position = api.get_position(symbol)
                if int(position.qty) > 0:
                    api.close_position(symbol)
                    order = {"id": "closed_long"}
                    print(f"✅ Closed long position for {symbol}")
                else:
                    order = {"id": "none"}
                    print(f"⚠️ No long position to close for {symbol}")
            except tradeapi.rest.APIError:
                order = {"id": "none"}
                print(f"⚠️ No long position to close for {symbol}")

        # Close Short safely
        elif side_lower == "close_short":
            try:
                position = api.get_position(symbol)
                if int(position.qty) < 0:
                    api.close_position(symbol)
                    order = {"id": "closed_short"}
                    print(f"✅ Closed short position for {symbol}")
                else:
                    order = {"id": "none"}
                    print(f"⚠️ No short position to close for {symbol}")
            except tradeapi.rest.APIError:
                order = {"id": "none"}
                print(f"⚠️ No short position to close for {symbol}")

        else:
            return jsonify({"error": "Invalid side"}), 400

        print(f"✅ Order processed: {side.upper()} {qty} {symbol}")
        return jsonify({"status": "success", "order_id": order.get('id', 'N/A')})

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error": str(e)}), 500

# ----------------------------
# Run server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    print("✅ TradeClaw running...🤖 Waiting for alerts.")
    app.run(host="0.0.0.0", port=port)

