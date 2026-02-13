from dotenv import load_dotenv
import os
from flask import Flask, request, jsonify
import alpaca_trade_api as tradeapi
import threading

# Load .env locally (ignored on Render)
load_dotenv()
app = Flask(__name__)

# Alpaca credentials from environment variables
API_KEY = os.environ.get("APCA_API_KEY_ID")
API_SECRET = os.environ.get("APCA_API_SECRET_KEY")
BASE_URL = os.environ.get("APCA_API_BASE_URL")

if not all([API_KEY, API_SECRET, BASE_URL]):
    raise ValueError("Alpaca API keys or base URL not set in environment variables!")

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# -------------------------
# TradeClaw Alert
# -------------------------
def show_tradeclaw_message():
    # Only run GUI locally
    if os.environ.get("RENDER") is None:
        import tkinter as tk
        root = tk.Tk()
        root.title("TradeClaw Activated")
        
        # Center the window
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        width = 600
        height = 200
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")
        
        root.configure(bg="black")
        
        label = tk.Label(
            root,
            text="YOU HAVE AWOKEN TRADECLAW",
            font=("Courier", 30, "bold"),
            fg="#39FF14",  # neon green
            bg="black"
        )
        label.pack(expand=True)
        root.after(3000, root.destroy)
        root.mainloop()
    else:
        # On Render just print to console
        print("\n" + "*"*60)
        print("YOU HAVE AWOKEN TRADECLAW".center(60))
        print("*"*60 + "\n")

# Run the alert in a separate thread so Flask can start immediately
threading.Thread(target=show_tradeclaw_message).start()

# -------------------------
# Routes
# -------------------------
@app.route("/", methods=["GET"])
def home():
    return """You have awoken TradeClaw🤖... Welcome to the future of trading!

Coming Soon!"""

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
            order = api.submit_order(
                symbol=symbol, qty=qty, side="buy", type="market", time_in_force="gtc"
            )
        elif side.lower() == "sell":
            order = api.submit_order(
                symbol=symbol, qty=qty, side="sell", type="market", time_in_force="gtc"
            )
        else:
            return jsonify({"error": "Invalid side"}), 400

        print(f"✅ Order submitted: {side.upper()} {qty} {symbol}")
        return jsonify({"status": "success", "order_id": order.id})
    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error": str(e)}), 500

# -------------------------
# Run Flask locally
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port)

