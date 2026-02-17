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
@app.route("/", methods=["GET"])
def home():
    page = """
    <!-- Your original full HTML dashboard here, unchanged -->
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
# FIXED WEBHOOK — ONLY CHANGE
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

        # Map Pine signals to Alpaca sides
        if side == "buy" or side == "long":
            side = "buy"
        elif side == "short":
            side = "sell"

        # ---------------- LONG/SHORT ENTRY ----------------
        if side in ["buy", "sell"]:
            order = api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type="market",
                time_in_force="day"
            )
            return jsonify({"status": f"{side}_opened", "order_id": order.id})

        # ---------------- CLOSE LONG ----------------
        elif side == "close_long":
            api.close_position(symbol)
            return jsonify({"status": "long_closed"})

        # ---------------- CLOSE SHORT ----------------
        elif side == "close_short":
            api.close_position(symbol)
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



