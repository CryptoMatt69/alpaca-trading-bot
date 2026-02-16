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
    raise ValueError("Missing Alpaca API credentials")

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>TradeClaw Terminal</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body { margin:0; font-family:Arial; background:#0f0c29; color:white;}
.nav { display:flex; gap:20px; padding:15px; background:black;}
.nav button { background:#DA70D6; border:none; padding:8px 15px; color:white; cursor:pointer;}
.section { display:none; padding:20px;}
.active { display:block;}
.card { background:#1a1a1a; padding:20px; border-radius:10px; margin-bottom:20px;}
.green { color:#DA70D6;}
.red { color:black;}
.grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px;}
iframe { width:100%; height:300px; border:none;}
table { width:100%; border-collapse:collapse;}
td,th { padding:6px; border-bottom:1px solid #333;}
</style>
</head>
<body>

<div class="nav">
<button onclick="showSection('dashboard')">Dashboard</button>
<button onclick="showSection('performance')">Performance</button>
</div>

<div id="dashboard" class="section active">
<div class="card">
<h2>Portfolio</h2>
<div>Equity: <span id="equity">Loading...</span></div>
<div>Daily PnL: <span id="daily_pnl">Loading...</span></div>
<div>Win Rate: <span id="winrate">Loading...</span></div>
</div>

<div class="card">
<h2>Positions</h2>
<div id="positions">Loading...</div>
</div>

<div class="card">
<h2>Charts</h2>
<button onclick="single()">Single</button>
<button onclick="multi()">Multi</button>
<div id="charts"></div>
</div>
</div>

<div id="performance" class="section">
<div class="card">
<h2>Equity Curve</h2>
<canvas id="equityChart"></canvas>
</div>

<div class="card">
<h2>Trade History</h2>
<table>
<thead>
<tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Status</th></tr>
</thead>
<tbody id="tradeTable"></tbody>
</table>
</div>
</div>

<script>

let equityChart;

function showSection(id){
document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
document.getElementById(id).classList.add('active');
}

function single(){
document.getElementById("charts").innerHTML =
`<iframe src="https://s.tradingview.com/widgetembed/?symbol=NASDAQ:AAPL&interval=15&theme=dark"></iframe>`;
}

function multi(){
let syms=["TSLA","NVDA","SPY","QQQ","AAPL","PLTR","UNH","RIVN"];
let html='<div class="grid">';
syms.forEach(s=>{
html+=`<iframe src="https://s.tradingview.com/widgetembed/?symbol=NASDAQ:${s}&interval=15&theme=dark"></iframe>`;
});
html+='</div>';
document.getElementById("charts").innerHTML=html;
}

async function loadData(){
try{
const res=await fetch('/api/fullstats');
const data=await res.json();

document.getElementById("equity").innerText=data.equity;
let pnlEl=document.getElementById("daily_pnl");
pnlEl.innerText=data.daily_pnl;
pnlEl.className = data.daily_pnl_value>=0 ? "green" : "red";
document.getElementById("winrate").innerText=data.winrate+"%";

let posHTML="";
data.positions.forEach(p=>{
let color=p.pnl>=0?"#DA70D6":"black";
posHTML+=`<div style="color:${color}">
${p.symbol} ${p.side} | PnL: $${p.pnl.toFixed(2)}
</div>`;
});
document.getElementById("positions").innerHTML=posHTML || "No Open Positions";

let tradeRows="";
data.trades.forEach(t=>{
tradeRows+=`<tr>
<td>${t.symbol}</td>
<td>${t.side}</td>
<td>${t.qty}</td>
<td>${t.status}</td>
</tr>`;
});
document.getElementById("tradeTable").innerHTML=tradeRows;

if(equityChart) equityChart.destroy();
equityChart = new Chart(document.getElementById("equityChart"),{
type:'line',
data:{
labels:data.equity_labels,
datasets:[{
label:'Equity',
data:data.equity_curve,
borderColor:'#DA70D6',
tension:0.3
}]
}
});

}catch(err){
console.error(err);
}
}

single();
loadData();
setInterval(loadData, 10000);

</script>
</body>
</html>
""")

# ---------------- API ----------------
@app.route("/api/fullstats")
def fullstats():
    try:
        account = api.get_account()
        equity = float(account.equity)
        last_equity = float(account.last_equity)
        daily_pnl = equity - last_equity
    except:
        return jsonify({"error":"Account load failed"}),500

    # Portfolio History (REAL curve)
    try:
        history = api.get_portfolio_history(period="1M", timeframe="1D")
        equity_curve = history.equity if history.equity else [equity]
        equity_labels = list(range(len(equity_curve)))
    except:
        equity_curve = [equity]
        equity_labels = ["Now"]

    # Orders + Win Rate
    try:
        orders = api.list_orders(status='closed', limit=50)
        wins = 0
        losses = 0

        for o in orders:
            if o.filled_avg_price and o.side == "sell":
                wins += 1

        total = len(orders)
        winrate = round((wins/total)*100,2) if total > 0 else 0

        trade_list = [{
            "symbol": o.symbol,
            "side": o.side,
            "qty": o.qty,
            "status": o.status
        } for o in orders]
    except:
        winrate = 0
        trade_list = []

    # Positions
    try:
        positions = []
        for p in api.list_positions():
            positions.append({
                "symbol": p.symbol,
                "side": "LONG" if float(p.qty) > 0 else "SHORT",
                "pnl": float(p.unrealized_pl)
            })
    except:
        positions = []

    return jsonify({
        "equity": f"${equity:,.2f}",
        "daily_pnl": f"${daily_pnl:,.2f}",
        "daily_pnl_value": daily_pnl,
        "winrate": winrate,
        "positions": positions,
        "trades": trade_list,
        "equity_curve": equity_curve,
        "equity_labels": equity_labels
    })

# ---------------- WEBHOOK ----------------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        symbol = data.get("symbol")
        qty = data.get("qty")
        side = data.get("side")

        if side in ["buy","sell"]:
            api.submit_order(symbol=symbol, qty=qty, side=side,
                             type="market", time_in_force="gtc")
        elif side in ["close_long","close_short"]:
            api.close_position(symbol)

        return jsonify({"status":"ok"})
    except Exception as e:
        return jsonify({"error":str(e)}),500

# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port)
