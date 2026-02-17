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
<!DOCTYPE html>
<html>
<head>
<title>TradeClaw Premium Terminal</title>
<style>
body {
    margin:0;
    font-family:'Roboto Mono', monospace;
    background: linear-gradient(to right, #0f0c29, #302b63, #24243e);
    color: #fff;
    overflow-x:hidden;
}
.container { max-width:1300px; margin:20px auto; padding:10px; }
.title { font-size:60px; font-weight:900; text-align:center; background:linear-gradient(90deg, #ff2bd6, #ff7f50); -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:30px; }
.card { background: rgba(0,0,0,0.85); border-radius:15px; padding:20px; margin-bottom:20px; box-shadow: 0 0 40px rgba(255, 43, 214, 0.5); transition: transform 0.2s; }
.card:hover { transform: scale(1.01); }
.card h2 { margin-top:0; font-size:24px; color:#ff2bd6; }
.stat { font-size:18px; margin:5px 0; transition: all 0.5s ease; }
.message-box { text-align:center; font-size:20px; color:#00ff00; text-shadow:0 0 10px #00ff00; margin-top:10px; }
.chart-select { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom:10px; }
.chart-select input { padding:5px 10px; border-radius:6px; border:none; font-size:16px; flex:1; min-width:150px; }
.chart-select select { padding:6px 10px; border-radius:6px; border:none; background:#111; color:white; }
.chart-select button { padding:6px 12px; border-radius:6px; border:none; background:#ff2bd6; color:white; font-weight:bold; cursor:pointer; transition:0.2s; }
.chart-select button:hover { background:#ff7f50; }
#chart { width:100%; height:500px; margin-top:10px; border-radius:15px; overflow:hidden; box-shadow:0 0 40px rgba(255,43,214,0.5); }
#multi_chart_container { display:none; margin-top:15px; gap:10px; }
#multi_chart_container div { margin-bottom:10px; }
#multi_chart_container input { width:70%; margin-bottom:5px; padding:4px 6px; border-radius:5px; border:none; }
#multi_chart_container button { padding:4px 8px; border-radius:5px; border:none; background:#ff2bd6; color:white; cursor:pointer; font-weight:bold; }
#multi_chart_container button:hover { background:#ff7f50; }
</style>
</head>
<body>

<div class="container">
    <div class="title">🤖 TradeClaw Premium</div>

    <!-- Account Overview -->
    <div class="card">
        <h2>Account Overview</h2>
        <div class="stat">Balance: <span id="balance">$0.00</span></div>
        <div class="stat">PnL: <span id="pnl">$0.00</span></div>
        <div class="stat">Recent Trade: <span id="recent_trade">N/A</span></div>
        <div class="stat">Trading Session: <span id="session_status">Loading...</span></div>
        <div class="message-box">Automated trades, Proven results.</div>
    </div>

    <!-- TradingView Chart -->
    <div class="card">
        <h2>TradingView Chart</h2>
        <div class="chart-select">
            <div id="single_search_container"></div>
            <select id="chart_interval">
                <option value="1">1 min</option>
                <option value="5">5 min</option>
                <option value="15" selected>15 min</option>
                <option value="60">1 hr</option>
                <option value="D">Daily</option>
            </select>
            <button onclick="updateChart()">Load Chart</button>
            <button onclick="toggleMultiView()">Multi-View</button>
        </div>

        <div id="chart">
            <iframe id="chart_iframe" 
                src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_12345&symbol=NASDAQ%3AAAPL&interval=15&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=000000&studies=[]&theme=dark&style=1&timezone=Etc%2FUTC&studies_overrides={'mainSeriesProperties.candleStyle.upColor':'#DA70D6','mainSeriesProperties.candleStyle.downColor':'#000000','mainSeriesProperties.candleStyle.wickUpColor':'#DA70D6','mainSeriesProperties.candleStyle.wickDownColor':'#000000','mainSeriesProperties.candleStyle.borderUpColor':'#DA70D6','mainSeriesProperties.candleStyle.borderDownColor':'#000000','paneProperties.background':'#000000'}"
                style="width:100%; height:100%;" allowtransparency="true" frameborder="0"></iframe>
        </div>

        <div id="multi_chart_container"></div>
    </div>

    <!-- Positions -->
    <div class="card">
        <h2>Current Positions</h2>
        <div id="positions_box">Loading...</div>
    </div>
</div>

<script src="https://s3.tradingview.com/tv.js"></script>
<script>
let lastPnl=0; let lastBalance=0;

// TradingView symbol search widget
new TradingView.widget({
    "autosize": true,
    "symbol": "NASDAQ:AAPL",
    "container_id": "single_search_container",
    "locale": "en",
    "enabled_features": ["symbol_search_hotlist"],
    "disabled_features": ["header_widget","timeframes_toolbar"],
    "theme":"Dark",
    "style":1,
    "interval":"15",
    "watchlist":["NASDAQ:WMT","NASDAQ:TSLA","NASDAQ:NVDA","NASDAQ:QQQ","NASDAQ:SPY","NASDAQ:UNH","NASDAQ:PLTR","NASDAQ:AAPL","NASDAQ:RIVN","NASDAQ:HOOD"]
});

// ------------------- Functions -------------------
function generateIframeSrc(symbol, interval="15"){
    return `https://s.tradingview.com/widgetembed/?frameElementId=tradingview_12345&symbol=NASDAQ%3A${symbol}&interval=${interval}&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=000000&studies=[]&theme=dark&style=1&timezone=Etc%2FUTC&studies_overrides={'mainSeriesProperties.candleStyle.upColor':'#DA70D6','mainSeriesProperties.candleStyle.downColor':'#000000','mainSeriesProperties.candleStyle.wickUpColor':'#DA70D6','mainSeriesProperties.candleStyle.wickDownColor':'#000000','mainSeriesProperties.candleStyle.borderUpColor':'#DA70D6','mainSeriesProperties.candleStyle.borderDownColor':'#000000','paneProperties.background':'#000000'}`;
}

function updateChart(){
    const symbol = document.querySelector('#single_search_container input').value.toUpperCase() || "AAPL";
    const interval = document.getElementById('chart_interval').value;
    document.getElementById('chart_iframe').src = generateIframeSrc(symbol, interval);
}

function toggleMultiView(){
    const container = document.getElementById('multi_chart_container');
    if(container.style.display==="none"){
        container.style.display="grid";
        container.style.gridTemplateColumns="repeat(2,1fr)";
        container.style.gap="10px";
        const tickers=["WMT","TSLA","NVDA","QQQ","SPY","UNH","PLTR","AAPL","RIVN","HOOD"];
        container.innerHTML="";
        tickers.forEach(symbol=>{
            const chartDiv=document.createElement("div");
            const input=document.createElement("input");
            input.type="text"; input.value=symbol;
            const button=document.createElement("button");
            button.innerText="Load"; 
            const iframe=document.createElement("iframe");
            iframe.style.width="100%"; iframe.style.height="300px"; iframe.allowTransparency="true"; 
            iframe.src=generateIframeSrc(symbol);
            button.onclick=()=>{ iframe.src=generateIframeSrc(input.value); };
            chartDiv.append(input, button, iframe);
            container.appendChild(chartDiv);
        });
    } else { container.style.display="none"; }
}

function animateNumber(element,start,end){
    const duration=500; const range=end-start; const startTime=performance.now();
    function step(currentTime){
        const progress=Math.min((currentTime-startTime)/duration,1);
        element.innerText="$"+(start+range*progress).toFixed(2);
        if(progress<1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

// ------------------- Fetch Alpaca Data -------------------
async function fetchData(){
    try{
        const res=await fetch('/api/stats');
        const data=await res.json();

        const balanceEl=document.getElementById('balance');
        const balanceValue=parseFloat(data.balance.replace('$','').replace(',',''))||0;
        animateNumber(balanceEl,lastBalance,balanceValue);
        lastBalance=balanceValue;

        const pnlEl=document.getElementById('pnl');
        const pnlValue=parseFloat(data.pnl.replace('$','').replace(',',''))||0;
        pnlEl.style.color=pnlValue>=0?"#DA70D6":"#ff3b3b";
        animateNumber(pnlEl,lastPnl,pnlValue);
        lastPnl=pnlValue;

        document.getElementById('recent_trade').innerText=data.recent_trade;
        document.getElementById('session_status').innerText=data.session_status;

        const posBox=document.getElementById('positions_box');
        if(data.positions.length===0){ posBox.innerHTML="No open positions"; }
        else{
            posBox.innerHTML=data.positions.map(p=>{
                const color=p.side==="LONG"?"#00ff00":"#ff3b3b";
                return `<span style="color:${color}; font-weight:bold">${p.symbol}: ${p.side} ${p.qty} @ $${p.avg_entry_price}</span>`;
            }).join('<br>');
        }
    } catch(e){ console.error(e); }
}

fetchData(); setInterval(fetchData,3000);
</script>
</body>
</html>
    """
    return render_template_string(page)

# ----------------------------
@app.route("/api/stats", methods=["GET"])
def api_stats():
    try:
        clock=api.get_clock()
        est_now=datetime.now(pytz.timezone("US/Eastern")).strftime("%I:%M:%S %p EST")
        session_status=f"{'OPEN 🟢' if clock.is_open else 'CLOSED 🔴'} {est_now}"
    except:
        session_status="UNKNOWN"

    try:
        account=api.get_account()
        balance = f"${float(account.equity):,.2f}"
        pnl = f"${float(account.equity)-float(account.cash):,.2f}"
        trades=api.list_orders(status='closed', limit=1, order_by='created_at', direction='desc')
        recent_trade=f"{trades[0].symbol} {trades[0].side.upper()} {trades[0].filled_qty}" if trades else "N/A"
    except:
        balance="$0.00"; pnl="$0.00"; recent_trade="N/A"

    pos_list=[]
    try:
        positions=api.list_positions()
        for p in positions:
            side="LONG" if float(p.qty)>0 else "SHORT"
            pos_list.append({"symbol":p.symbol,"qty":abs(float(p.qty)),"avg_entry_price":p.avg_entry_price,"side":side})
    except:
        pos_list=[]

    return jsonify({"balance":balance,"pnl":pnl,"recent_trade":recent_trade,"session_status":session_status,"positions":pos_list})

# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data=request.get_json()
        if not data: return jsonify({"error":"No JSON received"}),400

        symbol=data.get("symbol"); qty=data.get("qty"); side=data.get("side")
        if not all([symbol,qty,side]): return jsonify({"error":"Missing parameters"}),400

        side=side.lower()
        if side in ["buy","sell"]:
            order=api.submit_order(symbol=symbol,qty=qty,side=side,type="market",time_in_force="gtc")
            return jsonify({"status":"order_submitted","id":order.id})
        elif side in ["close_long","close_short"]:
            api.close_position(symbol)
            return jsonify({"status":"position_closed"})
        else:
            return jsonify({"error":"Invalid side"}),400
    except Exception as e:
        return jsonify({"error":str(e)}),500

# ----------------------------
if __name__=="__main__":
    port=int(os.environ.get("PORT",5100))
    app.run(host="0.0.0.0", port=port)

