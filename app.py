from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os
import yfinance as yf
from openai import OpenAI

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "replace-this-in-production")
DB = "jarvis_trading.db"

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = connect()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, username TEXT UNIQUE, cash REAL DEFAULT 100000)""")
    c.execute("""CREATE TABLE IF NOT EXISTS positions(
        user_id INTEGER, symbol TEXT, shares REAL, avg_price REAL,
        PRIMARY KEY(user_id, symbol))""")
    c.execute("""CREATE TABLE IF NOT EXISTS trades(
        id INTEGER PRIMARY KEY, user_id INTEGER, symbol TEXT, side TEXT,
        shares REAL, price REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY, username TEXT, body TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.commit()
    c.close()

# Initialize the database when the app is imported by Gunicorn.
init_db()

def get_price(symbol):
    try:
        d = yf.Ticker(symbol).history(period="2d")
        if d.empty:
            return None
        return float(d["Close"].dropna().iloc[-1])
    except Exception:
        return None

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/api/login")
def login():
    username = request.json.get("username", "").strip()
    if not username:
        return jsonify(error="Please enter a username"), 400
    c = connect()
    c.execute("INSERT OR IGNORE INTO users(username) VALUES(?)", (username,))
    u = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    c.commit()
    c.close()
    session["user_id"] = u["id"]
    session["username"] = u["username"]
    return jsonify(ok=True, username=u["username"])

@app.get("/api/quote/<symbol>")
def quote(symbol):
    symbol = symbol.upper()
    p = get_price(symbol)
    if p is None:
        return jsonify(error="Market data unavailable for that symbol"), 404
    return jsonify(symbol=symbol, price=p)

@app.get("/api/portfolio")
def portfolio():
    if "user_id" not in session:
        return jsonify(error="Login required"), 401
    c = connect()
    u = c.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    positions = c.execute(
        "SELECT * FROM positions WHERE user_id=? AND shares>0",
        (session["user_id"],)
    ).fetchall()

    total = float(u["cash"])
    result = []
    for p in positions:
        current = get_price(p["symbol"]) or p["avg_price"]
        value = current * p["shares"]
        pnl = (current - p["avg_price"]) * p["shares"]
        total += value
        result.append({
            "symbol": p["symbol"],
            "shares": p["shares"],
            "avg_price": p["avg_price"],
            "price": current,
            "value": value,
            "pnl": pnl
        })
    c.close()
    return jsonify(cash=u["cash"], total=total, positions=result)

@app.post("/api/trade")
def trade():
    if "user_id" not in session:
        return jsonify(error="Login first"), 401

    data = request.json
    symbol = data.get("symbol", "").upper()
    side = data.get("side")
    try:
        shares = float(data.get("shares", 0))
    except (TypeError, ValueError):
        shares = 0

    p = get_price(symbol)
    if not symbol or side not in ("BUY", "SELL") or shares <= 0 or p is None:
        return jsonify(error="Invalid trade"), 400

    c = connect()
    u = c.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    pos = c.execute(
        "SELECT * FROM positions WHERE user_id=? AND symbol=?",
        (session["user_id"], symbol)
    ).fetchone()

    if side == "BUY":
        cost = p * shares
        if cost > u["cash"]:
            c.close()
            return jsonify(error="Not enough virtual cash"), 400

        old_shares = pos["shares"] if pos else 0
        old_avg = pos["avg_price"] if pos else 0
        new_shares = old_shares + shares
        new_avg = ((old_shares * old_avg) + (shares * p)) / new_shares

        if pos:
            c.execute(
                "UPDATE positions SET shares=?, avg_price=? WHERE user_id=? AND symbol=?",
                (new_shares, new_avg, session["user_id"], symbol)
            )
        else:
            c.execute(
                "INSERT INTO positions VALUES(?,?,?,?)",
                (session["user_id"], symbol, shares, p)
            )

        c.execute("UPDATE users SET cash=cash-? WHERE id=?", (cost, session["user_id"]))

    else:
        if not pos or pos["shares"] < shares:
            c.close()
            return jsonify(error="Not enough shares"), 400

        c.execute(
            "UPDATE users SET cash=cash+? WHERE id=?",
            (p * shares, session["user_id"])
        )

        remaining = pos["shares"] - shares
        if remaining <= 0:
            c.execute(
                "DELETE FROM positions WHERE user_id=? AND symbol=?",
                (session["user_id"], symbol)
            )
        else:
            c.execute(
                "UPDATE positions SET shares=? WHERE user_id=? AND symbol=?",
                (remaining, session["user_id"], symbol)
            )

    c.execute(
        "INSERT INTO trades(user_id,symbol,side,shares,price) VALUES(?,?,?,?,?)",
        (session["user_id"], symbol, side, shares, p)
    )
    c.commit()
    c.close()
    return jsonify(ok=True, price=p)

@app.route("/api/community", methods=["GET", "POST"])
def community():
    c = connect()
    if request.method == "POST":
        if "username" not in session:
            c.close()
            return jsonify(error="Login first"), 401
        body = request.json.get("body", "").strip()
        if body:
            c.execute(
                "INSERT INTO posts(username,body) VALUES(?,?)",
                (session["username"], body)
            )
            c.commit()

    posts = c.execute(
        "SELECT * FROM posts ORDER BY id DESC LIMIT 50"
    ).fetchall()
    c.close()
    return jsonify([dict(p) for p in posts])

@app.post("/api/jarvis")
def jarvis():
    if "user_id" not in session:
        return jsonify(error="Login first"), 401

    message = request.json.get("message", "").strip()
    if not message:
        return jsonify(error="Ask Jarvis something"), 400

    c = connect()

    user = c.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    positions = c.execute(
        "SELECT * FROM positions WHERE user_id=? AND shares>0",
        (session["user_id"],)
    ).fetchall()

    trades = c.execute(
        """SELECT symbol, side, shares, price, created_at
           FROM trades
           WHERE user_id=?
           ORDER BY id DESC
           LIMIT 20""",
        (session["user_id"],)
    ).fetchall()

    c.close()

    portfolio = {
        "cash": round(float(user["cash"]), 2),
        "positions": []
    }

    for p in positions:
        current = get_price(p["symbol"]) or p["avg_price"]
        portfolio["positions"].append({
            "symbol": p["symbol"],
            "shares": float(p["shares"]),
            "average_price": round(float(p["avg_price"]), 4),
            "current_price": round(float(current), 4),
            "pnl": round(float((current - p["avg_price"]) * p["shares"]), 2)
        })

    recent_trades = [dict(t) for t in trades]

    try:
        client = OpenAI()

        response = client.responses.create(
            model="gpt-5.6-luna",
            instructions=(
                "You are Jarvis, the AI assistant inside JARVIS Trading. "
                "Help the user understand trading, markets, risk management, "
                "charts and their paper-trading account. "
                "Use the portfolio and trade information provided when relevant. "
                "Do not guarantee profits or claim certainty about future prices. "
                "Clearly distinguish education from financial advice. "
                "Be friendly, clear and beginner-friendly. "
                "If the user asks for a trade decision, explain relevant factors "
                "and risks rather than presenting a guaranteed outcome."
            ),
            input=(
                f"User's question:\n{message}\n\n"
                f"Current paper-trading portfolio:\n{portfolio}\n\n"
                f"Recent paper trades:\n{recent_trades}"
            )
        )

        return jsonify(answer=response.output_text)

    except Exception:
        return jsonify(
            error="Jarvis could not connect to the AI service. "
                  "Check that OPENAI_API_KEY is set correctly in Render."
        ), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501, debug=True)
