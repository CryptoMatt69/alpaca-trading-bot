import os
from flask import Flask, request, jsonify, render_template_string
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
# Track open positions
open_positions = {}  # symbol -> {'side': 'long'/'short', 'qty': int, 'entry_price': float}
locks = {}           # symbol -> threading.Lock()

def get_lock(symbol):
    if symbol not in locks:
        locks[symbol] = threading.Lock()
    return locks[symbol]

# ----------------------------
@app.route("/", methods=["GET"])
def home():
    page = """ ... (your full HTML from previous version) ... """
    return render_template_string(page)

# ----------------------------
@app.route("/api/stats", methods=["GET"])
def api_stats():
    balance_str = "$0.00"
    pnl_str = "$0.00"
    recent_trade = "None"
    session_status = "Unknown"
    pos_list = []

    try:
        clock = api.get_clock()
        est_now = datetime.now(pytz.timezone("US/Eastern")).strftime("%I:%M:%S %p EST")
        session_status = f"{'OPEN 🟢' if clock.is_open else 'CLOSED 🔴'} {est_now}"
    except:
        pass

    try:
        account = api.get_account()
        balance = float(account.portfolio_value)
        balance_str = f"${balance:,.2f}"

        # Most recent filled trade
        trades = api.list_orders(status='all', limit=10, order_by='created_at', direction='desc')
        for t in trades:
            if float(t.filled_qty) > 0:
                recent_trade = f"{t.symbol} {t.side.upper()} {t.filled_qty} @ ${t.filled_avg_price if t.filled_avg_price else '0.00'}"
                break

        # Positions & calculate PnL
        total_unrealized = 0
        positions = api.list_positions()
        for p in positions:
            side = "LONG" if float(p.qty) > 0 else "SHORT"
            qty = abs(float(p.qty))
            entry = float(p.avg_entry_price)
            current_price = float(p.current_price)
            unrealized_pnl = (current_price - entry) * qty if side=="LONG" else (entry - current_price) * qty
            total_unrealized += unrealized_pnl
            pos_list.append({
                "symbol": p.symbol,
                "qty": qty,
                "avg_entry_price": entry,
                "side": side,
                "unrealized_pnl": f"${unrealized_pnl:,.2f}"
            })

        pnl_str = f"${total_unrealized:,.2f}"

    except Exception as e:
        print("Stats error:", e)

    return jsonify({
        "balance": balance_str,
        "pnl": pnl_str,
        "recent_trade": recent_trade,
        "session_status": session_status,
        "positions": pos_list
    })

# ----------------------------
def execute_order(symbol, qty, side):
    lock = get_lock(symbol)
    with lock:
        try:
            current_pos = open_positions.get(symbol, {}).get("side")
            if side in ["close_long", "close_short"]:
                if current_pos and ((side=="close_long" and current_pos=="long") or (side=="close_short" and current_pos=="short")):
                    api.close_position(symbol)
                    open_positions.pop(symbol, None)
                    return {"status":"position_closed"}
                else:
                    return {"status":"no_position_to_close"}

            if side=="long":
                if current_pos=="long":
                    return {"status":"long_already_open"}
                elif current_pos=="short":
                    api.close_position(symbol)
                    time.sleep(1)
                order = api.submit_order(symbol=symbol, qty=qty, side="buy", type="market", time_in_force="day")
                open_positions[symbol] = {"side":"long","qty":qty,"entry_price": float(order.filled_avg_price) if order.filled_avg_price else 0}
                return {"status":"long_opened","order_id":order.id}

            elif side=="short":
                if current_pos=="short":
                    return {"status":"short_already_open"}
                elif current_pos=="long":
                    api.close_position(symbol)
                    time.sleep(1)
                order = api.submit_order(symbol=symbol, qty=qty, side="sell", type="market", time_in_force="day")
                open_positions[symbol] = {"side":"short","qty":qty,"entry_price": float(order.filled_avg_price) if order.filled_avg_price else 0}
                return {"status":"short_opened","order_id":order.id}

            else:
                return {"error":f"Invalid side: {side}"}

        except Exception as e:
            print(f"Execution error for {symbol} {side}:", e)
            return {"error": str(e)}

# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        symbol = data.get("symbol")
        qty = int(data.get("qty",1))
        side = data.get("side","").lower()

        if not symbol or not side:
            return jsonify({"error":"Missing symbol or side"}),400
        if side=="buy": side="long"
        elif side=="sell": side="short"

        result = execute_order(symbol, qty, side)
        return jsonify(result)

    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return jsonify({"error": str(e)}),500

# ----------------------------
if __name__=="__main__":
    port = int(os.environ.get("PORT",5100))
    app.run(host="0.0.0.0", port=port)



