from flask import Flask, request, jsonify
import requests
import os
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

ALPACA_BASE    = "https://paper-api.alpaca.markets"
ALPACA_KEY     = os.environ.get("ALPACA_KEY", "")
ALPACA_SECRET  = os.environ.get("ALPACA_SECRET", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

def get_headers(key=None, secret=None):
    return {
        "APCA-API-KEY-ID":     key or ALPACA_KEY,
        "APCA-API-SECRET-KEY": secret or ALPACA_SECRET,
        "Content-Type":        "application/json"
    }

def req_keys(r):
    return r.headers.get("X-API-Key"), r.headers.get("X-API-Secret")

@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key, X-API-Secret, X-Webhook-Secret"
    return response

@app.route("/health", methods=["GET", "OPTIONS"])
def health():
    return jsonify({"status": "online", "mode": "paper"}), 200

@app.route("/account", methods=["GET", "OPTIONS"])
def account():
    if request.method == "OPTIONS": return jsonify({}), 200
    k, s = req_keys(request)
    try:
        r = requests.get(f"{ALPACA_BASE}/v2/account", headers=get_headers(k, s))
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/positions", methods=["GET", "DELETE", "OPTIONS"])
def positions():
    if request.method == "OPTIONS": return jsonify({}), 200
    k, s = req_keys(request)
    try:
        if request.method == "DELETE":
            r = requests.delete(f"{ALPACA_BASE}/v2/positions", headers=get_headers(k, s))
            return jsonify({"status": "all closed"}), 200
        r = requests.get(f"{ALPACA_BASE}/v2/positions", headers=get_headers(k, s))
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/positions/<symbol>", methods=["DELETE", "OPTIONS"])
def close_position(symbol):
    if request.method == "OPTIONS": return jsonify({}), 200
    k, s = req_keys(request)
    try:
        requests.delete(f"{ALPACA_BASE}/v2/positions/{symbol}", headers=get_headers(k, s))
        return jsonify({"status": "closed", "symbol": symbol}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/orders", methods=["GET", "POST", "OPTIONS"])
def orders():
    if request.method == "OPTIONS": return jsonify({}), 200
    k, s = req_keys(request)
    try:
        if request.method == "POST":
            body = request.get_json(force=True)
            logging.info(f"Order: {body}")
            r = requests.post(f"{ALPACA_BASE}/v2/orders", headers=get_headers(k, s), json=body)
            logging.info(f"Response {r.status_code}: {r.text}")
            return jsonify(r.json()), r.status_code
        r = requests.get(f"{ALPACA_BASE}/v2/orders?status=open", headers=get_headers(k, s))
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/webhook", methods=["POST", "OPTIONS"])
def webhook():
    if request.method == "OPTIONS": return jsonify({}), 200
    data = request.get_json(force=True)
    logging.info(f"Webhook: {data}")
    if WEBHOOK_SECRET:
        if request.headers.get("X-Webhook-Secret", "") != WEBHOOK_SECRET:
            return jsonify({"error": "Unauthorized"}), 401
    action = data.get("action", "").lower()
    ticker = data.get("ticker", "")
    sl     = data.get("sl", 0)
    tp1    = data.get("tp1", 0)
    tp2    = data.get("tp2", 0)
    qty    = data.get("qty", 1)
    if not ticker or action not in ["buy", "sell"]:
        return jsonify({"error": "Invalid payload"}), 400
    try:
        r = requests.get(f"{ALPACA_BASE}/v2/orders?status=open&symbols={ticker}", headers=get_headers())
        for o in r.json():
            requests.delete(f"{ALPACA_BASE}/v2/orders/{o['id']}", headers=get_headers())
    except: pass
    try:
        requests.delete(f"{ALPACA_BASE}/v2/positions/{ticker}", headers=get_headers())
    except: pass
    side   = "buy" if action == "buy" else "sell"
    tp_use = tp2 if tp2 else tp1
    body   = {"symbol": ticker, "qty": str(qty), "side": side, "type": "market", "time_in_force": "day"}
    if tp_use and sl:
        body["order_class"] = "bracket"
        body["take_profit"] = {"limit_price": str(round(float(tp_use), 4))}
        body["stop_loss"]   = {"stop_price":  str(round(float(sl), 4))}
    try:
        r = requests.post(f"{ALPACA_BASE}/v2/orders", headers=get_headers(), json=body)
        return jsonify({"status": "ok", "order": r.json()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
