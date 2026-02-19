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
#           "sl1": 5, "sl2": 5
#       }
#   }
# }
open_positions = {}
locks = {}

def get_lock(symbol):
    if symbol not in locks:
        locks[symbol] = threading.Lock()
    return locks[symbol]

# ----------------------------
TP_PERCENT = [0.015, 0.02, 0.03]   # 1.5%, 2%, 3%
SL_PERCENT = [0.006, 0.01]         # 0.6%, 1%

# How many shares to close at each tier (must sum to tradeQty from Pine)
# Matches your Pine Script: qty=5 for TP1, qty=5 for TP2, qty=5 for TP3
TIER_QTYS = {
    "tp1": 5,
    "tp2": 5,
    "tp3": 5,
    "sl1": 5,
    "sl2": 5,
}

# ----------------------------
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
    .card h2 { margin-top: 0; font-size: 24px; color: #ff2bd6; }
    .stat { font-size: 18px; margin: 5px 0; }
    .chart-select { display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
    .chart-select input, .chart-select select { padding: 5px 10px; border-radius: 8px; border: none; font-size: 16px; }
    .chart-select button { padding: 5px 12px; border-radius: 8px; border: none; background: #ff2bd6;
                           color: #fff; cursor: pointer; font-weight: bold; transition: 0.2s; }
    .chart-select button:hover { background: #ff7f50; }
    .message-box { text-align: center; font-size: 20px; color: #00ff00;
                   text-shadow: 0 0 10px #00ff00; margin-top: 10px; }
    #chart { width: 100%; height: 500px; border-radius: 15px; overflow: hidden;
             box-shadow: 0 0 40px rgba(255, 43, 214, 0.5); margin-bottom: 20px; }
    #multi_chart_container { display: none; margin-top: 20px; gap: 10px; }
  </style>
</head>
<body>
<div class="container">
  <div class="title">TradeClaw Premium</div>
  <div class="card">
    <h2>Account Overview</h2>
    <div class="stat">Balance: <span id="balance">$0.00</span></div>
    <div class="stat">Current Positions PnL: <span id="pnl">$0.00</span></div>
    <div class="stat">Recent Trade: <span id="recent_trade">N/A</span></div>
    <div class="stat">Trading Session: <span id="session_status">Loading...</span></div>
    <div class="message-box">Automated trades, Proven results.</div>
  </div>
  <div class="card">
    <h2>TradingView Chart</h2>
    <div class="chart-select">
      <input type="text" id="chart_symbol" placeholder="Single Symbol e.g. AAPL" />
      <select id="chart_interval">
        <option value="1">1 min</option>
        <option value="5">5 min</option>
        <option value="15" selected>15 min</option>
        <option value="60">1 hr</option>
        <option value="D">Daily</option>
      </select>
      <button onclick="updateChart()">Load Chart</button>
      <button onclick="toggleMultiView()">Show Multi-View</button>
      <label>Charts Count: <input type="number" id="multi_count" value="4" min="1" max="10" style="width:60px"/></label>
    </div>
    <div id="chart">
      <iframe id="chart_iframe"
        src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_12345&symbol=NASDAQ%3AAAPL&interval=15&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=000000&studies=[]&theme=dark&style=1"
        style="width:100%; height:500px;" allowtransparency="true" frameborder="0"></iframe>
    </div>
    <div id="multi_chart_container"></div>
  </div>
  <div class="card">
    <h2>Current Positions</h2>
    <div id="positions_box">Loading...</div>
  </div>
</div>
<script>
  function generateIframeSrc(symbol) {
    return `https://s.tradingview.com/widgetembed/?frameElementId=tradingview_12345&symbol=NASDAQ%3A${symbol}&interval=15&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=000000&studies=[]&theme=dark&style=1`;
  }
  function updateChart() {
    const symbol = document.getElementById('chart_symbol').value.toUpperCase() || "AAPL";
    document.getElementById('chart_iframe').src = generateIframeSrc(symbol);
  }
  function toggleMultiView() {
    const container = document.getElementById('multi_chart_container');
    if (container.style.display === "none") {
      container.style.display = "grid";
      container.style.gridTemplateColumns = "repeat(2, 1fr)";
      const maxCharts = parseInt(document.getElementById('multi_count').value) || 4;
      const tickers = ["META","WMT","HOOD","RIVN","AAPL","PLTR","NVDA","TSLA"].slice(0, maxCharts);
      container.innerHTML = "";
      tickers.forEach(symbol => {
        const chartDiv = document.createElement("div");
        chartDiv.style.marginBottom = "10px";
        const input = document.createElement("input");
        input.type = "text"; input.value = symbol; input.style.width = "70%"; input.style.marginBottom = "5px";
        const button = document.createElement("button");
        button.innerText = "Load";
        const iframe = document.createElement("iframe");
        iframe.style.width = "100%"; iframe.style.height = "300px";
        iframe.allowTransparency = "true";
        iframe.src = generateIframeSrc(symbol);
        button.onclick = () => { iframe.src = generateIframeSrc(input.value.toUpperCase()); };
        chartDiv.appendChild(input); chartDiv.appendChild(button); chartDiv.appendChild(iframe);
        container.appendChild(chartDiv);
      });
    } else {
      container.style.display = "none";
    }
  }
  async function fetchData() {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      document.getElementById('balance').innerText = data.balance;
      const pnlEl = document.getElementById('pnl');
      pnlEl.style.color = parseFloat(data.pnl.replace('$','').replace(',','')) >= 0 ? "#00ff00" : "#ff3b3b";
      pnlEl.innerText = data.pnl;
      document.getElementById('recent_trade').innerText = data.recent_trade;
      document.getElementById('session_status').innerText = data.session_status;
      const posBox = document.getElementById('positions_box');
      if (data.positions.length === 0) {
        posBox.innerHTML = "No open positions";
      } else {
        posBox.innerHTML = data.positions.map(p => {
          const color = p.side === "LONG" ? "#00ff00" : "#ff3b3b";
          return `<span style="color:${color}; font-weight:bold">${p.symbol}: ${p.side} ${p.qty} @ $${p.avg_entry_price} (${p.unrealized_pnl})</span>`;
        }).join('<br>');
      }
    } catch(e) { console.error(e); }
  }
  fetchData();
  setInterval(fetchData, 3000);
</script>
</body>
</html>"""
    return render_template_string(page), 200, {"Content-Type": "text/html"}

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
    """
    lock = get_lock(symbol)
    with lock:
        try:
            pos = open_positions.get(symbol)
            if not pos:
                return {"status": "no_open_position", "symbol": symbol}

            side   = pos["side"]
            tiers  = pos["tiers"]

            # Map alert_type -> tier key
            # e.g. "close_long_tp1" -> "tp1", "close_short_sl2" -> "sl2"
            tier_key = alert_type.split("_")[-1] + alert_type.split("_")[-2][-1]
            # Simpler parse: last two segments give e.g. "tp1", "sl2"
            parts    = alert_type.split("_")   # ["close","long","tp1"] or ["close","short","sl2"]
            tier_key = parts[-1]               # "tp1", "tp2", "tp3", "sl1", "sl2"

            close_qty = tiers.get(tier_key, 0)
            if close_qty <= 0:
                return {"status": "tier_already_closed", "tier": tier_key, "symbol": symbol}

            # Validate direction matches
            expected_direction = "long" if "long" in alert_type else "short"
            if side != expected_direction:
                return {"status": "direction_mismatch", "symbol": symbol,
                        "expected": expected_direction, "actual": side}

            order_side = "sell" if side == "long" else "buy"

            api.submit_order(
                symbol=symbol,
                qty=close_qty,
                side=order_side,
                type="market",
                time_in_force="day"
            )

            # Zero out this tier so duplicate alerts don't fire again
            tiers[tier_key] = 0

            # Check if all tiers exhausted → remove position
            total_remaining = sum(tiers.values())
            if total_remaining <= 0:
                open_positions.pop(symbol, None)

            return {
                "status": "closed",
                "symbol": symbol,
                "tier": tier_key,
                "qty_closed": close_qty,
                "remaining_qty": total_remaining - close_qty if total_remaining > close_qty else 0
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
            # Matches Pine Script: TP1=5, TP2=5, TP3=5 (qty per exit block)
            # Adjust TIER_QTYS at the top of the file if your Pine qty values change.
            new_tiers = dict(TIER_QTYS)  # {"tp1":5, "tp2":5, "tp3":5, "sl1":5, "sl2":5}

            def flip_position(close_side_label):
                """Close existing opposite position and wait for it to clear."""
                try:
                    api.get_position(symbol)
                    api.close_position(symbol)
                    open_positions.pop(symbol, None)
                    for _ in range(20):          # wait up to 10s
                        try:
                            api.get_position(symbol)
                            time.sleep(0.5)
                        except tradeapi.rest.APIError:
                            break
                    time.sleep(2)
                except tradeapi.rest.APIError:
                    pass

            # --- LONG ---
            if side == "long":
                if current_side == "long":
                    return {"status": "long_already_open"}
                if current_side == "short":
                    flip_position("short")

                api.submit_order(symbol=symbol, qty=qty, side="buy",
                                 type="market", time_in_force="day")
                open_positions[symbol] = {
                    "side":        "long",
                    "entry_price": current_price,
                    "tiers":       new_tiers
                }
                return {"status": "long_ordered", "symbol": symbol,
                        "entry_price": current_price, "tiers": new_tiers}

            # --- SHORT ---
            elif side == "short":
                if current_side == "short":
                    return {"status": "short_already_open"}
                if current_side == "long":
                    flip_position("long")

                api.submit_order(symbol=symbol, qty=qty, side="sell",
                                 type="market", time_in_force="day")
                open_positions[symbol] = {
                    "side":        "short",
                    "entry_price": current_price,
                    "tiers":       new_tiers
                }
                return {"status": "short_ordered", "symbol": symbol,
                        "entry_price": current_price, "tiers": new_tiers}

        except Exception as e:
            print(f"Execute order error {symbol}: {e}")
            return {"error": str(e)}

# ----------------------------
# NO monitor threads — TradingView alerts are the source of truth for TP/SL.
# The old monitor threads had a bug (zeroing tier_qtys[i] before subtracting)
# and competed with the webhook close path, causing double-fires or missed closes.

# ----------------------------
def scheduled_cleanup():
    """Sync open_positions with actual Alpaca positions every 60s."""
    while True:
        try:
            actual = {p.symbol for p in api.list_positions()}
            for symbol in list(open_positions.keys()):
                if symbol not in actual:
                    print(f"Cleanup: removing stale position {symbol}")
                    open_positions.pop(symbol, None)
        except Exception as e:
            print("Cleanup error:", e)
        time.sleep(60)

threading.Thread(target=scheduled_cleanup, daemon=True).start()

# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5100)))
