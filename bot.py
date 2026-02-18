import os
from flask import Flask, request, jsonify, render_template_string
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
from datetime import datetime, timedelta
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
# Track open positions
open_positions = {}
locks = {}

def get_lock(symbol):
    if symbol not in locks:
        locks[symbol] = threading.Lock()
    return locks[symbol]

# ----------------------------
TP_PERCENT = 1.2 / 100
SL_PERCENT = 0.6 / 100

# ----------------------------
@app.route("/", methods=["GET"])
def home():
    return "TradeClaw Running", 200

# ----------------------------
@app.route("/api/stats", methods=["GET"])
def api_stats():
    return jsonify({"status": "ok"})

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
        print("WEBHOOK ERROR:", e)
        return jsonify({"error": str(e)}), 500

# ----------------------------
def execute_order(symbol, qty, side):
    lock = get_lock(symbol)

    with lock:
        try:
            current_pos = open_positions.get(symbol, {})
            current_side = current_pos.get("side")

            last_trade = api.get_latest_trade(symbol)
            current_price = float(last_trade.price)

            if side == "long":
                if current_side == "long":
                    return {"status": "long_already_open"}

                order = api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side="buy",
                    type="market",
                    time_in_force="day"
                )

                entry_price = current_price

                tp_qty = min(3, qty)
                tp_price = round(entry_price * (1 + TP_PERCENT), 2)

                api.submit_order(
                    symbol=symbol,
                    qty=tp_qty,
                    side="sell",
                    type="limit",
                    time_in_force="day",
                    limit_price=tp_price
                )

                sl_price = round(entry_price * (1 - SL_PERCENT), 2)

                stop_order = api.submit_order(
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
                    "entry_price": entry_price,
                    "stop_order_id": stop_order.id,
                    "tp_qty": tp_qty
                }

                return {"status": "long_opened", "order_id": order.id}

            elif side == "short":
                if current_side == "short":
                    return {"status": "short_already_open"}

                order = api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side="sell",
                    type="market",
                    time_in_force="day"
                )

                entry_price = current_price

                tp_qty = min(3, qty)
                tp_price = round(entry_price * (1 - TP_PERCENT), 2)

                api.submit_order(
                    symbol=symbol,
                    qty=tp_qty,
                    side="buy",
                    type="limit",
                    time_in_force="day",
                    limit_price=tp_price
                )

                sl_price = round(entry_price * (1 + SL_PERCENT), 2)

                stop_order = api.submit_order(
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
                    "entry_price": entry_price,
                    "stop_order_id": stop_order.id,
                    "tp_qty": tp_qty
                }

                return {"status": "short_opened", "order_id": order.id}

            else:
                return {"error": f"Invalid side: {side}"}

        except Exception as e:
            print(f"Execution error for {symbol} {side}:", e)
            return {"error": str(e)}

# ----------------------------
# 🔥 AGGRESSIVE SESSION FLATTENING (NEW)
def scheduled_cleanup():
    eastern = pytz.timezone("US/Eastern")

    while True:
        try:
            now = datetime.now(eastern)
            current_time = now.time()

            open_start = datetime.strptime("09:25", "%H:%M").time()
            open_end   = datetime.strptime("09:31", "%H:%M").time()

            close_start = datetime.strptime("15:55", "%H:%M").time()
            close_end   = datetime.strptime("16:01", "%H:%M").time()

            # ---- OPEN WINDOW ----
            if open_start <= current_time <= open_end:
                print("[SCHEDULE] OPEN WINDOW FLATTENING")

                try:
                    for o in api.list_orders(status="open"):
                        api.cancel_order(o.id)
                except:
                    pass

                try:
                    for p in api.list_positions():
                        api.close_position(p.symbol)
                        open_positions.pop(p.symbol, None)
                except:
                    pass

                time.sleep(15)
                continue

            # ---- CLOSE WINDOW ----
            if close_start <= current_time <= close_end:
                print("[SCHEDULE] CLOSE WINDOW FLATTENING")

                try:
                    for o in api.list_orders(status="open"):
                        api.cancel_order(o.id)
                except:
                    pass

                try:
                    for p in api.list_positions():
                        api.close_position(p.symbol)
                        open_positions.pop(p.symbol, None)
                except:
                    pass

                time.sleep(15)
                continue

        except Exception as e:
            print("[SCHEDULE ERROR]", e)

        time.sleep(20)

threading.Thread(target=scheduled_cleanup, daemon=True).start()

# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5100)))
