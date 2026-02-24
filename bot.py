import json
import os
from flask import Flask, request, jsonify, render_template_string
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import threading
import time
TRADES_FILE = "closed_trades.json"

# ----------------------------
load_dotenv()
app = Flask(__name__)

API_KEY    = os.environ.get("APCA_API_KEY_ID")
API_SECRET = os.environ.get("APCA_API_SECRET_KEY")
BASE_URL   = os.environ.get("APCA_API_BASE_URL")

if not all([API_KEY, API_SECRET, BASE_URL]):
    raise ValueError("Alpaca API keys or base URL not set!")

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

# ----------------------------
# open_positions tracks side, remaining qty per TP/SL tier, and entry price.
# Structure:
# {
#   "AAPL": {
#       "side": "long",
#       "entry_price": 150.00,
#       "tiers": {
#           "tp1": 5, "tp2": 5, "tp3": 5,   # qty remaining per tier
#           "sl1": 8, "sl2": 7
#       }
#   }
# }
open_positions = {}  # active positions
def load_trades():
    try:
        if os.path.exists(TRADES_FILE):
            with open(TRADES_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Load trades error: {e}")
    return []

def save_trades():
    try:
        with open(TRADES_FILE, "w") as f:
            json.dump(closed_trades, f, indent=2)
    except Exception as e:
        print(f"Save trades error: {e}")

closed_trades = load_trades()  # load from file on startup
locks = {}

def get_lock(symbol):
    if symbol not in locks:
        locks[symbol] = threading.Lock()
    return locks[symbol]

# ----------------------------
def log_closed_trade(symbol, side, qty, entry_price, exit_price, reason=""):
    """Log a closed trade to closed_trades and save to disk."""
    pnl = (exit_price - entry_price) * qty if side == "long" else (entry_price - exit_price) * qty
    est = pytz.timezone("US/Eastern")
    now = datetime.now(est)
    closed_trades.append({
        "symbol":      symbol,
        "side":        side.upper(),
        "qty":         qty,
        "entry_price": f"{entry_price:.2f}",
        "exit_price":  f"{exit_price:.2f}",
        "pnl":         f"{pnl:.2f}",
        "closed_at":   now.strftime("%I:%M %p EST"),
        "date":        now.strftime("%Y-%m-%d"),
        "reason":      reason
    })
    save_trades()
    print(f"Logged closed trade: {symbol} {side.upper()} {qty}sh entry={entry_price:.2f} exit={exit_price:.2f} pnl={pnl:.2f} ({reason})")

# ----------------------------
TP_PERCENT = [0.015, 0.02, 0.03]   # 1.5%, 2%, 3%
SL_PERCENT = [0.006, 0.01]         # 0.6%, 1%

# How many shares to close at each tier (must sum to tradeQty from Pine)
# Matches your Pine Script: qty=5 for TP1, qty=5 for TP2, qty=5 for TP3
TIER_QTYS = {
    "tp1": 5,
    "tp2": 5,
    "tp3": 5,
    "sl1": 8,
    "sl2": 7,
}

# (TRADING LOGIC ABOVE REMAINS EXACTLY THE SAME — I AM ONLY SHOWING
# THE FIXED home() SECTION SO YOU CAN REPLACE YOUR BROKEN HTML)

@app.route("/", methods=["GET"])
def home():
    page = """<!DOCTYPE html>
<html>
<head>
  <title>TradeClaw Premium</title>
  <style>
    html, body { background-color: #0d0d0d; color: white; font-family: 'Roboto Mono', monospace; }
    .container { max-width: 1300px; margin: 20px auto; padding: 10px; }
    .title { font-size: 60px; font-weight: 900; text-align: center;
             background: linear-gradient(90deg, #ff2bd6, #ff7f50);
             -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 30px; }
    .card { background: rgba(0,0,0,0.85); border-radius: 15px; padding: 20px; margin-bottom: 20px;
            box-shadow: 0 0 40px rgba(255, 43, 214, 0.5); }
  </style>
</head>
<body>
<div class="container">
  <div class="title">TradeClaw Premium</div>

  <div class="card">
    <h2>Account Overview</h2>
    <div>Balance: <span id="balance">$0.00</span></div>
    <div>Current Positions P&L: <span id="pnl">$0.00</span></div>
    <div>Daily P&L: <span id="daily_pnl">$0.00</span></div>
    <div>Recent Trade: <span id="recent_trade">N/A</span></div>
    <div>Trading Session: <span id="session_status">Loading...</span></div>
  </div>

  <div class="card">
    <h2>Closed Trades</h2>
    <div id="closed_list">Loading...</div>
  </div>
</div>

<script>
async function fetchClosed() {
  try {
    const res = await fetch('/api/closed_trades');
    const data = await res.json();
    const box = document.getElementById('closed_list');

    if (!data.trades || data.trades.length === 0) {
      box.innerHTML = "<span style='color:#aaa'>No closed trades</span>";
      document.getElementById("daily_pnl").innerText = "$0.00";
      return;
    }

    box.innerHTML = data.trades.map(t => {
      const pnl = parseFloat(t.pnl);
      const color = pnl >= 0 ? "#00ff00" : "#ff3b3b";
      const sign  = pnl >= 0 ? "+" : "";
      return `<div style="margin-bottom:8px; padding:8px; background:#111; border-radius:8px;">
        <b>${t.symbol}</b> ${t.side} ${t.qty} shares
        <span style="color:${color}; font-weight:bold; margin-left:10px">
          ${sign}$${Math.abs(pnl).toFixed(2)}
        </span>
        <span style="color:#555; font-size:12px; margin-left:8px">
          ${t.date} ${t.closed_at}
        </span>
      </div>`;
    }).join('');

    // DAILY P&L
    const est = new Date().toLocaleString("en-US", {timeZone: "America/New_York"});
    const today = new Date(est).toISOString().split("T")[0];
    const dailyTrades = data.trades.filter(t => t.date === today);
    const dailyTotal = dailyTrades.reduce((sum, t) => sum + parseFloat(t.pnl), 0);
    const dailyColor = dailyTotal >= 0 ? "#00ff00" : "#ff3b3b";
    const dailySign  = dailyTotal >= 0 ? "+" : "";

    const dailyEl = document.getElementById("daily_pnl");
    dailyEl.innerText = `${dailySign}$${Math.abs(dailyTotal).toFixed(2)}`;
    dailyEl.style.color = dailyColor;

  } catch(e) {
    console.error(e);
  }
}

async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();

    document.getElementById('balance').innerText = data.balance;
    document.getElementById('pnl').innerText = data.pnl;
    document.getElementById('recent_trade').innerText = data.recent_trade;
    document.getElementById('session_status').innerText = data.session_status;

  } catch(e) {
    console.error(e);
  }
}

fetchClosed();
fetchStats();

setInterval(fetchClosed, 5000);
setInterval(fetchStats, 3000);
</script>

</body>
</html>
"""
    return render_template_string(page)

# ----------------------------
@app.route("/api/stats", methods=["GET"])
def api_stats():
    balance_str  = "$0.00"
    pnl_str      = "$0.00"
    recent_trade = "None"
    session_status = "Unknown"
    pos_list     = []
    try:
        clock = api.get_clock()
        est_now = datetime.now(pytz.timezone("US/Eastern")).strftime("%I:%M:%S %p EST")
        session_status = f"{'OPEN 🟢' if clock.is_open else 'CLOSED 🔴'} {est_now}"
    except:
        pass
    try:
        account   = api.get_account()
        positions = api.list_positions()
        balance   = float(account.cash) + sum(float(p.market_value) for p in positions)
        balance_str = f"${balance:,.2f}"
        total_unrealized_pnl = 0.0
        for p in positions:
            side = "LONG" if float(p.qty) > 0 else "SHORT"
            qty  = abs(float(p.qty))
            entry = float(p.avg_entry_price)
            current_price = float(p.current_price)
            unrealized_pnl = (current_price - entry) * qty if side == "LONG" else (entry - current_price) * qty
            total_unrealized_pnl += unrealized_pnl
            pos_list.append({
                "symbol": p.symbol, "qty": qty,
                "avg_entry_price": entry, "side": side,
                "unrealized_pnl": f"${unrealized_pnl:,.2f}"
            })
        pnl_str = f"${total_unrealized_pnl:,.2f}"
        trades = api.list_orders(status='all', limit=10)
        trades.sort(key=lambda x: x.created_at, reverse=True)
        for t in trades:
            if float(t.filled_qty) > 0:
                recent_trade = f"{t.symbol} {t.side.upper()} {t.filled_qty} @ ${t.filled_avg_price or '0.00'}"
                break
    except Exception as e:
        print("Stats error:", e)
    return jsonify({
        "balance": balance_str, "pnl": pnl_str,
        "recent_trade": recent_trade, "session_status": session_status,
        "positions": pos_list
    })

# ----------------------------
@app.route("/api/closed_trades", methods=["GET"])
def api_closed_trades():
    from flask import request as req
    date_filter = req.args.get("date")  # e.g. ?date=2026-02-23

    # Reload from disk every request to ensure all trades are visible
    global closed_trades
    try:
        if os.path.exists(TRADES_FILE):
            with open(TRADES_FILE, "r") as f:
                closed_trades = json.load(f)
    except Exception as e:
        print(f"Error loading trades from file: {e}")
        closed_trades = []

    if date_filter:
        filtered = [t for t in closed_trades if t.get("date") == date_filter]
    else:
        filtered = closed_trades

    # Reverse so newest shows first
    return jsonify({"trades": list(reversed(filtered))})

# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data   = request.get_json(force=True)
        symbol = data.get("symbol")
        qty    = int(data.get("qty", 1))
        side   = data.get("side", "").lower()

        if not symbol or not side:
            return jsonify({"error": "Missing symbol or side"}), 400

        if side == "buy":
            side = "long"
        elif side == "sell":
            side = "short"

        # TP/SL close alerts from Pine Script
        if side in [
            "close_long_tp1",  "close_long_tp2",  "close_long_tp3",
            "close_short_tp1", "close_short_tp2", "close_short_tp3",
            "close_long_sl1",  "close_long_sl2",
            "close_short_sl1", "close_short_sl2",
        ]:
            result = execute_close(symbol, side)
            return jsonify(result)

        result = execute_order(symbol, qty, side)
        return jsonify(result)

    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return jsonify({"error": str(e)}), 500

# ----------------------------
def execute_close(symbol, alert_type):
    """
    Called by TradingView TP/SL alerts.
    Reads the remaining qty for the triggered tier from open_positions,
    submits the close order, then decrements the tier so repeat alerts are no-ops.
    Logs every close (partial or full) to closed_trades.json with PnL and hold time.
    """
    lock = get_lock(symbol)
    with lock:
        try:
            pos = open_positions.get(symbol)
            if not pos:
                return {"status": "no_open_position", "symbol": symbol}

            side   = pos["side"]
            tiers  = pos["tiers"]
            entry_price = pos.get("entry_price", 0.0)
            entry_time  = pos.get("entry_time", datetime.now(pytz.timezone("US/Eastern")))

            # Parse alert type -> tier key
            parts = alert_type.split("_")   # ["close","long","tp1"] etc
            tier_key = parts[-1]            # "tp1", "tp2", "tp3", "sl1", "sl2"

            close_qty = tiers.get(tier_key, 0)
            if close_qty <= 0:
                return {"status": "tier_already_closed", "tier": tier_key, "symbol": symbol}

            # Validate direction matches
            expected_direction = "long" if "long" in alert_type else "short"
            if side != expected_direction:
                return {"status": "direction_mismatch", "symbol": symbol,
                        "expected": expected_direction, "actual": side}

            order_side = "sell" if side == "long" else "buy"

            # Submit the market close order
            api.submit_order(
                symbol=symbol,
                qty=close_qty,
                side=order_side,
                type="market",
                time_in_force="day"
            )

            # Zero out this tier so duplicate alerts don't fire again
            tiers[tier_key] = 0

            # Get exit price
            try:
                last_trade = api.get_latest_trade(symbol)
                exit_price = float(last_trade.price)
            except:
                exit_price = 0.0

            # Compute PnL
            pnl_dollar = (exit_price - entry_price) * close_qty if side == "long" else (entry_price - exit_price) * close_qty
            pnl_percent = (exit_price - entry_price) / entry_price * 100 if side == "long" else (entry_price - exit_price) / entry_price * 100

            # How long held
            held_seconds = int((datetime.now(pytz.timezone("US/Eastern")) - entry_time).total_seconds())

            # Log every partial close
            closed_trades.append({
                "symbol": symbol,
                "side": side.upper(),
                "qty": close_qty,
                "entry_price": f"{entry_price:.2f}",
                "exit_price": f"{exit_price:.2f}",
                "pnl": f"{pnl_dollar:.2f}",
                "pnl_percent": f"{pnl_percent:.2f}",
                "held_seconds": held_seconds,
                "closed_at": datetime.now(pytz.timezone("US/Eastern")).strftime("%I:%M %p EST"),
                "date": datetime.now(pytz.timezone("US/Eastern")).strftime("%Y-%m-%d"),
                "reason": tier_key
            })
            save_trades()
            print(f"[CLOSE] {symbol} {tier_key} qty={close_qty} PnL=${pnl_dollar:.2f} ({pnl_percent:.2f}%) held {held_seconds}s")

            # If all tiers exhausted, remove position
            total_remaining = sum(tiers.values())
            if total_remaining <= 0:
                open_positions.pop(symbol, None)

            return {
                "status": "closed",
                "symbol": symbol,
                "tier": tier_key,
                "qty_closed": close_qty,
                "remaining_qty": total_remaining
            }

        except Exception as e:
            print(f"Execute close error {symbol}: {e}")
            return {"error": str(e)}

# ----------------------------
def execute_order(symbol, qty, side):
    lock = get_lock(symbol)
    with lock:
        try:
            current_pos  = open_positions.get(symbol, {})
            current_side = current_pos.get("side")

            last_trade    = api.get_latest_trade(symbol)
            current_price = float(last_trade.price)

            # Build fresh tier qty tracking for this new position
            new_tiers = dict(TIER_QTYS)

            # --- LONG ---
            if side == "long":
                # Close opposite short if open
                if current_side == "short":
                    pos = open_positions.pop(symbol, None)
                    exit_price = float(last_trade.price)
                    log_closed_trade(
                        symbol, "short",
                        sum(pos["tiers"].values()),
                        pos["entry_price"],
                        exit_price,
                        reason="flip"
                    )

                # Already have a long open
                if current_side == "long":
                    return {"status": "long_already_open"}

                # Place new long order
                api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side="buy",
                    type="market",
                    time_in_force="day"
                )
                open_positions[symbol] = {
                    "side": "long",
                    "entry_price": current_price,
                    "entry_time": datetime.now(pytz.timezone("US/Eastern")),
                    "tiers": new_tiers
                }
                return {
                    "status": "long_ordered",
                    "symbol": symbol,
                    "entry_price": current_price,
                    "tiers": new_tiers
                }

            # --- SHORT ---
            elif side == "short":
                # Close opposite long if open
                if current_side == "long":
                    pos = open_positions.pop(symbol, None)
                    exit_price = float(last_trade.price)
                    log_closed_trade(
                        symbol, "long",
                        sum(pos["tiers"].values()),
                        pos["entry_price"],
                        exit_price,
                        reason="flip"
                    )

                # Already have a short open
                if current_side == "short":
                    return {"status": "short_already_open"}

                # Place new short order
                api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side="sell",
                    type="market",
                    time_in_force="day"
                )
                open_positions[symbol] = {
                    "side": "short",
                    "entry_price": current_price,
                    "entry_time": datetime.now(pytz.timezone("US/Eastern")),
                    "tiers": new_tiers
                }
                return {
                    "status": "short_ordered",
                    "symbol": symbol,
                    "entry_price": current_price,
                    "tiers": new_tiers
                }

        except Exception as e:
            print(f"Execute order error {symbol}: {e}")
            return {"error": str(e)}

# ----------------------------
# NO monitor threads — TradingView alerts are the source of truth for TP/SL.
# The old monitor threads had a bug (zeroing tier_qtys[i] before subtracting)
# and competed with the webhook close path, causing double-fires or missed closes.

# ----------------------------
def scheduled_cleanup():
    """Sync open_positions with actual Alpaca positions every 60s. Reset closed_trades daily."""
    est = pytz.timezone("US/Eastern")
    while True:
        try:
            actual_positions = {p.symbol: p for p in api.list_positions()}
            actual = set(actual_positions.keys())
            for symbol in list(open_positions.keys()):
                if symbol not in actual:
                    print(f"Cleanup: removing stale position {symbol} (manually closed or SL hit)")
                    pos = open_positions.pop(symbol, {})
                    # Try to get exit price from recent orders
                    try:
                        orders = api.list_orders(status="filled", limit=20)
                        orders.sort(key=lambda x: x.filled_at, reverse=True)
                        exit_price = None
                        for o in orders:
                            if o.symbol == symbol and o.filled_avg_price:
                                exit_price = float(o.filled_avg_price)
                                break
                        if exit_price is None:
                            exit_price = pos.get("entry_price", 0.0)
                        entry_price = pos.get("entry_price", 0.0)
                        side = pos.get("side", "long")
                        qty = sum(TIER_QTYS.values())
                        log_closed_trade(symbol, side, qty, entry_price, exit_price, reason="manual/SL")
                    except Exception as e:
                        print(f"Cleanup log error {symbol}: {e}")

        except Exception as e:
            print("Cleanup error:", e)
        time.sleep(60)

threading.Thread(target=scheduled_cleanup, daemon=True).start()

# ----------------------------
def sync_positions_on_startup():
    """
    On startup, load any existing Alpaca positions into open_positions
    so TP/SL webhook alerts work immediately without needing a new entry.
    Entry price is pulled from Alpaca. Tiers are reset to full since we
    don't know what's already been partially closed.
    """
    try:
        positions = api.list_positions()
        for p in positions:
            symbol = p.symbol
            side   = "long" if float(p.qty) > 0 else "short"
            entry  = float(p.avg_entry_price)
            open_positions[symbol] = {
                "side":        side,
                "entry_price": entry,
                "tiers":       dict(TIER_QTYS)
            }
            print(f"Startup sync: loaded {symbol} {side} @ ${entry}")
        print(f"Startup sync complete. {len(open_positions)} position(s) loaded.")
    except Exception as e:
        print(f"Startup sync error: {e}")

# Call it on startup to load existing positions
sync_positions_on_startup()

# NO TP/SL monitor thread — alerts from TradingView are the source of truth

# ----------------------------
def eod_liquidation():
    """
    Every minute, check if it's 3:55 PM EST or later during a trading day.
    If so, close all open positions via Alpaca and clear open_positions.
    """
    est = pytz.timezone("US/Eastern")
    while True:
        try:
            now = datetime.now(est)
            if now.weekday() < 5:  # Monday–Friday only
                if (now.hour == 15 and now.minute >= 55) or now.hour == 16:
                    positions = api.list_positions()
                    if positions:
                        print(f"EOD liquidation triggered at {now.strftime('%I:%M %p EST')}")
                        for p in positions:
                            try:
                                pos = open_positions.get(p.symbol, {})
                                entry_price = pos.get("entry_price", float(p.avg_entry_price))
                                side = pos.get("side", "long" if float(p.qty) > 0 else "short")
                                qty = abs(float(p.qty))
                                exit_price = float(p.current_price)
                                api.close_position(p.symbol)
                                open_positions.pop(p.symbol, None)
                                log_closed_trade(p.symbol, side, qty, entry_price, exit_price, reason="EOD")
                                print(f"EOD: closed {p.symbol}")
                            except Exception as e:
                                print(f"EOD close error {p.symbol}: {e}")
        except Exception as e:
            print(f"EOD liquidation error: {e}")
        time.sleep(60)

threading.Thread(target=eod_liquidation, daemon=True).start()

# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5100)))
