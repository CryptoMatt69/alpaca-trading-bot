import os
from flask import Flask, request, jsonify
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
from datetime import datetime
import pytz
import threading
import time

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
open_positions = {}
locks = {}

def get_lock(symbol):
    if symbol not in locks:
        locks[symbol] = threading.Lock()
    return locks[symbol]

# ----------------------------
TP_PERCENT = 1.2 / 100
SL_PERCENT = 0.6 / 100
TP_PARTIAL_QTY = 3
TRAIL_PERCENT = 0.4  # 0.4% trailing stop
# ----------------------------

@app.route("/", methods=["GET"])
def home():
    return "TradeClaw Premium Running"

# ----------------------------
def cancel_existing_stops(symbol):
    open_orders = api.list_orders(status="open", symbols=[symbol])
    for order in open_orders:
        if order.type in ["stop", "trailing_stop"]:
            api.cancel_order(order.id)

# ----------------------------
def manage_after_partial(symbol, side, original_qty):
    try:
        position = api.get_position(symbol)
        remaining_qty = abs(int(float(position.qty)))

        if remaining_qty < original_qty and remaining_qty > 0:

            cancel_existing_stops(symbol)

            entry_price = float(position.avg_entry_price)

            # Move stop to breakeven
            if side == "long":
                api.submit_order(
                    symbol=symbol,
                    qty=remaining_qty,
                    side="sell",
                    type="stop",
                    stop_price=round(entry_price, 2),
                    time_in_force="day"
                )

                # Add trailing stop
                api.submit_order(
                    symbol=symbol,
                    qty=remaining_qty,
                    side="sell",
                    type="trailing_stop",
                    trail_percent=TRAIL_PERCENT,
                    time_in_force="day"
                )

            else:
                api.submit_order(
                    symbol=symbol,
                    qty=remaining_qty,
                    side="buy",
                    type="stop",
                    stop_price=round(entry_price, 2),
                    time_in_force="day"
                )

                api.submit_order(
                    symbol=symbol,
                    qty=remaining_qty,
                    side="buy",
                    type="trailing_stop",
                    trail_percent=TRAIL_PERCENT,
                    time_in_force="day"
                )

    except:
        pass

# ----------------------------
def execute_order(symbol, qty, side):
    lock = get_lock(symbol)

    with lock:
        try:
            current_pos = open_positions.get(symbol, {})
            current_side = current_pos.get("side")

            # CLOSE ALERTS
            if side in ["close_long", "close_short"]:
                try:
                    api.close_position(symbol)
                except:
                    pass
                open_positions.pop(symbol, None)
                return {"status": "position_closed"}

            last_trade = api.get_last_trade(symbol)
            current_price = float(last_trade.price)

            # ---------------- LONG ----------------
            if side == "long":

                if current_side == "short":
                    api.close_position(symbol)
                    open_positions.pop(symbol, None)
                    time.sleep(2)

                api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side="buy",
                    type="market",
                    time_in_force="day"
                )

                entry_price = current_price

                tp_price = round(entry_price * (1 + TP_PERCENT), 2)
                sl_price = round(entry_price * (1 - SL_PERCENT), 2)

                # Partial TP
                api.submit_order(
                    symbol=symbol,
                    qty=TP_PARTIAL_QTY,
                    side="sell",
                    type="limit",
                    time_in_force="day",
                    limit_price=tp_price
                )

                # Initial SL
                api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side="sell",
                    type="stop",
                    time_in_force="day",
                    stop_price=sl_price
                )

                open_positions[symbol] = {
                    "side": "long",
                    "qty": qty,
                    "entry_price": entry_price
                }

                time.sleep(4)
                manage_after_partial(symbol, "long", qty)

                return {"status": "long_opened"}

            # ---------------- SHORT ----------------
            elif side == "short":

                if current_side == "long":
                    api.close_position(symbol)
                    open_positions.pop(symbol, None)
                    time.sleep(2)

                api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side="sell",
                    type="market",
                    time_in_force="day"
                )

                entry_price = current_price

                tp_price = round(entry_price * (1 - TP_PERCENT), 2)
                sl_price = round(entry_price * (1 + SL_PERCENT), 2)

                api.submit_order(
                    symbol=symbol,
                    qty=TP_PARTIAL_QTY,
                    side="buy",
                    type="limit",
                    time_in_force="day",
                    limit_price=tp_price
                )

                api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side="buy",
                    type="stop",
                    time_in_force="day",
                    stop_price=sl_price
                )

                open_positions[symbol] = {
                    "side": "short",
                    "qty": qty,
                    "entry_price": entry_price
                }

                time.sleep(4)
                manage_after_partial(symbol, "short", qty)

                return {"status": "short_opened"}

            else:
                return {"error": f"Invalid side: {side}"}

        except Exception as e:
            print("Execution error:", e)
            return {"error": str(e)}

# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        symbol = data.get("symbol")
        qty = int(data.get("qty", 1))
        side = data.get("side", "").lower()

        if not symbol or not side:
            return jsonify({"error": "Missing symbol or side"}), 400

        if side == "buy":
            side = "long"
        elif side == "sell":
            side = "short"

        result = execute_order(symbol, qty, side)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port)

