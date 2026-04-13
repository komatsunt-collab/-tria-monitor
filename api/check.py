import json
import urllib.request
from http.server import BaseHTTPRequestHandler

THRESHOLDS = {
    "apy_danger": 5.0,
    "apy_warning": 7.0,
    "tvl_baseline": 5900000,
    "tvl_drop_pct": 20,
}

def fetch_url(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TriaMonitor/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except:
        return None

def fetch_apy():
    data = fetch_url("https://yields.llama.fi/pools")
    if not data:
        return None, []
    targets = []
    for p in data.get("data", []):
        proj = p.get("project", "").lower()
        sym = p.get("symbol", "").upper()
        chain = p.get("chain", "").lower()
        apy = p.get("apy", 0) or 0
        if "usdc" in sym and chain == "ethereum" and any(k in proj for k in ["sentora","morpho","aave"]):
            targets.append({"project": p.get("project",""), "symbol": sym, "apy": round(float(apy), 2)})
    if not targets:
        return None, []
    targets.sort(key=lambda x: x["apy"], reverse=True)
    return targets[0]["apy"], targets[:5]

def fetch_tvl():
    data = fetch_url("https://api.llama.fi/protocol/sentora")
    if not data:
        return None
    tvls = data.get("currentChainTvls", {})
    total = sum(float(v) for v in tvls.values()) if tvls else 0
    if total == 0:
        lst = data.get("tvl", [])
        if lst:
            total = float(lst[-1].get("totalLiquidityUSD", 0))
    return round(total) if total > 0 else None

def fetch_pyusd():
    data = fetch_url("https://api.coingecko.com/api/v3/simple/price?ids=paypal-usd&vs_currencies=usd")
    if not data:
        return {"price": 1.0, "is_depegged": False}
    price = float(data.get("paypal-usd", {}).get("usd", 1.0))
    return {"price": price, "is_depegged": price < 0.98 or price > 1.02}

def evaluate(apy, tvl, pyusd):
    level = "safe"
    alerts = []
    if apy is None:
        alerts.append({"text": "APYデータを取得できませんでした", "severity": "warning"})
        level = "warning"
    elif apy < THRESHOLDS["apy_danger"]:
        alerts.append({"text": f"APYが{apy}%に急落（基準:{THRESHOLDS['apy_danger']}%以下で危険）", "severity": "danger"})
        level = "danger"
    elif apy < THRESHOLDS["apy_warning"]:
        alerts.append({"text": f"APYが{apy}%に低下（基準:{THRESHOLDS['apy_warning']}%以下で注意）", "severity": "warning"})
        if level != "danger":
            level = "warning"
    if tvl is None:
        alerts.append({"text": "TVLデータを取得できませんでした", "severity": "warning"})
    else:
        drop = max(0, (THRESHOLDS["tvl_baseline"] - tvl) / THRESHOLDS["tvl_baseline"] * 100)
        if drop > THRESHOLDS["tvl_drop_pct"]:
            alerts.append({"text": f"TVLがベースラインから{drop:.0f}%急減", "severity": "danger"})
            level = "danger"
        elif drop > 10:
            alerts.append({"text": f"TVLが{drop:.0f}%減少中（要​​​​​​​​​​​​​​​​
