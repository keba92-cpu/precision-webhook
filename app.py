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

HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
    "Content-Type":        "application/json"
}

def close_position(symbol):
    try:
        r = requests.delete(f"{ALPACA_BASE}/v2/positions/{symbol}", headers=HEADERS)
        logging.info(f"Closed position {symbol}: {r.status_code}")
    except Exception as e:
        logging.error(f"Close position error: {e}")

def cancel_open_orders(symbol):
    try:
        r = requests.get(f"{ALPACA_BASE}/v2/orders?status=open&symbols={symbol}", headers=HEADERS)
        orders = r.json()
        for o in orders:
            requests.delete(f"{ALPACA_BASE}/v2/orders/{o['id']}", headers=HEADERS)
        logging.info(f"Cancelled {len(orders)} open orders for {symbol}")
    except Exception as e:
        logging.error(f"Cancel orders error: {e}")

def place_bracket_order(symbol, side, qty, tp, sl):
    body = {
        "symbol":        symbol,
        "qty":           str(qty),
        "side":          side,
        "type":          "market",
        "time_in_force": "day",
        "order_class":   "bracket",
        "take_profit":   {"limit_price": str(round(float(tp), 4))},
        "stop_loss":     {"stop_price":  str(round(float(sl), 4))}
    }
    r = requests.post(f"{ALPACA_BASE}/v2/orders", headers=HEADERS, json=body)
    logging.info(f"Order response {r.status_code}: {r.text}")
    return r.json(), r.status_code

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    logging.info(f"Received webhook: {data}")

    if WEBHOOK_SECRET:
        secret = request.headers.get("X-Webhook-Secret", "")
        if secret != WEBHOOK_SECRET:
            return jsonify({"error": "Unauthorized"}), 401

    action = data.get("action", "").lower()
    ticker = data.get("ticker", "")
    sl     = data.get("sl", 0)
    tp1    = data.get("tp1", 0)
    tp2    = data.get("tp2", 0)
    score  = data.get("score", 0)
    grade  = data.get("grade", "")
    qty    = data.get("qty", 1)

    if not ticker or action not in ["buy", "sell"]:
        return jsonify({"error": "Invalid payload"}), 400

    cancel_open_orders(ticker)
    close_position(ticker)

    side   = "buy" if action == "buy" else "sell"
    tp_use = tp2 if tp2 else tp1

    try:
        order, status = place_bracket_order(ticker, side, qty, tp_use, sl)
        return jsonify({"status": "ok", "action": action, "ticker": ticker, "grade": grade, "score": score, "order": order}), 200
    except Exception as e:
        logging.error(f"Order error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "online", "alpaca": ALPACA_BASE}), 200

@app.route("/positions", methods=["GET"])
def positions():
    r = requests.get(f"{ALPACA_BASE}/v2/positions", headers=HEADERS)
    return jsonify(r.json()), r.status_code

@app.route("/orders", methods=["GET"])
def orders():
    r = requests.get(f"{ALPACA_BASE}/v2/orders?status=open", headers=HEADERS)
    return jsonify(r.json()), r.status_code

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
