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
open_positions = {}  # symbol -> {'side': 'long'/'short', 'qty': int, 'entry_price': float, 'stop_order_id': str, 'tp_qty': int}
locks = {}           # symbol -> threading.Lock()

def get_lock(symbol):
    if symbol not in locks:
        locks[symbol] = threading.Lock()
    return locks[symbol]

# ----------------------------
# SYNC memory with Alpaca positions at startup
try:
    positions = api.list_positions()
    for p in positions:
        side = "long" if float(p.qty) > 0 else "short"
        open_positions[p.symbol] = {"side": side, "qty": abs(float(p.qty)), "entry_price": float(p.avg_entry_price)}
except Exception as e:
    print("Error syncing positions at startup:", e)

# ----------------------------
TP_PERCENT = 1.2 / 100
SL_PERCENT = 0.6 / 100

# ----------------------------
@app.route("/", methods=["GET"])
def home():
    page = """<!DOCTYPE html>
<html>
<!-- your existing HTML unchanged -->
</html>"""
    return render_template_string(page), 200, {"Content-Type": "text/html"}

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
    except: pass

    try:
        account = api.get_account()
        balance = float(account.cash) + sum(float(p.market_value) for p in api.list_positions())
        balance_str = f"${balance:,.2f}"

        positions = api.list_positions()
        total_unrealized_pnl = 0.0

        for p in positions:
            side = "LONG" if float(p.qty) > 0 else "SHORT"
            qty = abs(float(p.qty))
            entry = float(p.avg_entry_price)
            current_price = float(p.current_price)
            unrealized_pnl = (current_price - entry)*qty if side=="LONG" else (entry - current_price)*qty
            total_unrealized_pnl += unrealized_pnl

            pos_list.append({
                "symbol": p.symbol,
                "qty": qty,
                "avg_entry_price": entry,
                "side": side,
                "unrealized_pnl": f"${unrealized_pnl:,.2f}"
            })

        pnl_str = f"${total_unrealized_pnl:,.2f}"  # live PnL

        trades = api.list_orders(status='all', limit=10)
        trades.sort(key=lambda x: x.created_at, reverse=True)
        for t in trades:
            if float(t.filled_qty) > 0:
                recent_trade = f"{t.symbol} {t.side.upper()} {t.filled_qty} @ ${t.filled_avg_price if t.filled_avg_price else '0.00'}"
                break

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
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        symbol = data.get("symbol")
        qty = int(data.get("qty",1))
        side = data.get("side","").lower()
        if not symbol or not side: return jsonify({"error":"Missing symbol or side"}),400
        if side=="buy": side="long"
        elif side=="sell": side="short"
        result = execute_order(symbol, qty, side)
        return jsonify(result)
    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return jsonify({"error": str(e)}),500

# ----------------------------
def execute_order(symbol, qty, side):
    lock = get_lock(symbol)
    with lock:
        try:
            # SYNC memory for this symbol before checking
            if symbol not in open_positions:
                try:
                    positions = api.list_positions()
                    for p in positions:
                        if p.symbol == symbol:
                            side_mem = "long" if float(p.qty) > 0 else "short"
                            open_positions[symbol] = {"side": side_mem, "qty": abs(float(p.qty)), "entry_price": float(p.avg_entry_price)}
                except: pass

            current_pos = open_positions.get(symbol, {})
            current_side = current_pos.get("side")
            current_entry_price = current_pos.get("entry_price", 0)
            current_qty = current_pos.get("qty", 0)

            if side in ["close_long","close_short"]:
                if current_side and ((side=="close_long" and current_side=="long") or (side=="close_short" and current_side=="short")):
                    api.close_position(symbol)
                    open_positions.pop(symbol, None)
                    return {"status":"position_closed"}
                else: return {"status":"no_position_to_close"}

            # GET current market price
            last_quote = api.get_latest_trade(symbol)
            current_price = float(last_quote.price) if last_quote.price else 0.0

            # LONG ENTRY
            if side=="long":
                if current_side=="long": return {"status":"long_already_open"}
                elif current_side=="short":
                    api.close_position(symbol)
                    open_positions.pop(symbol, None)
                    time.sleep(2)

                order = api.submit_order(symbol=symbol, qty=qty, side="buy", type="market", time_in_force="day")
                entry_price = current_price

                tp_price = round(entry_price*(1+TP_PERCENT),2)
                api.submit_order(symbol=symbol, qty=3, side="sell", type="limit", time_in_force="day", limit_price=tp_price)

                sl_price = round(entry_price*(1-SL_PERCENT),2)
                stop_order = api.submit_order(symbol=symbol, qty=qty, side="sell", type="stop", time_in_force="day", stop_price=sl_price)

                open_positions[symbol] = {"side":"long","qty":qty,"entry_price":entry_price,"stop_order_id":stop_order.id,"tp_qty":3}

                def monitor_tp():
                    while True:
                        try:
                            orders = api.list_orders(status='all',symbol=symbol)
                            tp_order = next((o for o in orders if o.side=="sell" and float(o.qty)==3 and o.type=="limit"),None)
                            if tp_order and float(tp_order.filled_qty)==3:
                                remaining_qty = qty-3
                                if remaining_qty>0:
                                    try: api.cancel_order(stop_order.id)
                                    except: pass
                                    api.submit_order(symbol=symbol, qty=remaining_qty, side="sell", type="stop", time_in_force="day", stop_price=entry_price)
                                break
                        except: pass
                        time.sleep(1)
                threading.Thread(target=monitor_tp, daemon=True).start()
                return {"status":"long_opened","order_id":order.id}

            # SHORT ENTRY
            elif side=="short":
                if current_side=="short": return {"status":"short_already_open"}
                elif current_side=="long":
                    api.close_position(symbol)
                    open_positions.pop(symbol, None)
                    time.sleep(2)

                order = api.submit_order(symbol=symbol, qty=qty, side="sell", type="market", time_in_force="day")
                entry_price = current_price

                tp_price = round(entry_price*(1-TP_PERCENT),2)
                api.submit_order(symbol=symbol, qty=3, side="buy", type="limit", time_in_force="day", limit_price=tp_price)

                sl_price = round(entry_price*(1+SL_PERCENT),2)
                stop_order = api.submit_order(symbol=symbol, qty=qty, side="buy", type="stop", time_in_force="day", stop_price=sl_price)

                open_positions[symbol] = {"side":"short","qty":qty,"entry_price":entry_price,"stop_order_id":stop_order.id,"tp_qty":3}

                def monitor_tp_short():
                    while True:
                        try:
                            orders = api.list_orders(status='all',symbol=symbol)
                            tp_order = next((o for o in orders if o.side=="buy" and float(o.qty)==3 and o.type=="limit"),None)
                            if tp_order and float(tp_order.filled_qty)==3:
                                remaining_qty = qty-3
                                if remaining_qty>0:
                                    try: api.cancel_order(stop_order.id)
                                    except: pass
                                    api.submit_order(symbol=symbol, qty=remaining_qty, side="buy", type="stop", time_in_force="day", stop_price=entry_price)
                                break
                        except: pass
                        time.sleep(1)
                threading.Thread(target=monitor_tp_short, daemon=True).start()
                return {"status":"short_opened","order_id":order.id}

            else: return {"error":f"Invalid side: {side}"}

        except Exception as e:
            print(f"Execution error for {symbol} {side}:", e)
            return {"error": str(e)}

# ----------------------------
if __name__=="__main__":
    port = int(os.environ.get("PORT",5100))
    app.run(host="0.0.0.0", port=port)


