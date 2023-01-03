import os
import re
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():

    id = session["user_id"]
    database = db.execute("SELECT * FROM portfolio WHERE user_id = ? GROUP BY symbol", id)

    finance = db.execute("SELECT * FROM users WHERE id = ?", id)
    total = 10000

    return render_template("index.html", database=database, total=total, finance=finance)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "POST":

        symbol = request.form.get("symbol")
        share = request.form.get("shares")

        if not symbol:
            return apology("missing symbol", 400)

        if not lookup(symbol):
            return apology("invalid symbol", 400)

        if not share:
            return apology("missing shares", 400)

        if not share.isnumeric() or int(share) < 1:
            return apology("invalid share(s)")

        dic = lookup(symbol)
        stock_name = dic["name"]
        share = int(share)
        price = float(dic["price"])
        total_price = price * share

        rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        user_cash = rows[0]["cash"]

        if not rows:
            return apology("buying stock failed", 400)

        if (price * share) > user_cash:
            return apology("not enough cash", 400)

        else:
            check = db.execute("SELECT shares FROM portfolio WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)
            if check:
                new_share = int(check) + share
                new_total_price = new_share * price
                db.execute("UPDATE portfolio SET shares = ? , total_price = ?", new_share, new_total_price)
            else:
                # transaction time
                now = datetime.now()
                dt_string = now.strftime("%d-%m-%Y %H:%M:%S")

                db.execute("INSERT INTO portfolio (user_id, symbol, stock_name, shares, price, total_price) VALUES (?, ?, ?, ?, ?, ?)",
                           session["user_id"], dic["symbol"], stock_name, share, price, total_price)

            db.execute("INSERT INTO history (user_id, symbol, shares, price, total_price, operation, transacted) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       session["user_id"], dic["symbol"], share, price, total_price, "BUY", dt_string)
            user_new_cash = user_cash - total_price
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=user_new_cash, id=session["user_id"])

            flash("Bought!")
            return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():

    id = session["user_id"]
    database = db.execute("SELECT * FROM history WHERE user_id = ?", id)

    return render_template("history.html", database=database)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash("Logged In!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        dic = lookup(symbol)
        if dic:
            return render_template("quoted.html", name=dic['name'], price=dic['price'], symbol=dic['symbol'])
        else:
            return apology("invalid symbol")
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    # User reached route via POST (as by clicking a link or via redirect)
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure username was submitted to registration form
        if not username:
            return apology("must provide username")

        if db.execute("SELECT username FROM users WHERE username = ?", username):
            return apology("username is taken")

        # Ensure password was submitted to registration form
        if not password:
            return apology("must provide password")

        # Ensure confirmation password was submitted to registration form
        if not confirmation:
            return apology("must provide password again")

        # Ensure confirmation password and password was equal
        if password != confirmation:
            return apology("must provide same password again")

        # TESTING PASSSWORD RULE
        reg = "^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!#%*?&]{6,20}$"

        # compiling regex
        pat = re.compile(reg)

        # searching regex
        mat = re.search(pat, password)

        # validating conditions
        if not mat:
            return apology("Password must have at least one number, at least one uppercase and lowercase character, at least one special symbol, and be between 6 and 20 characters long.", 403)

        hashed_password = generate_password_hash(password)

        # Inserting users data into database called users
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hashed_password)

        flash("Registered!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    sell_symbol = db.execute("SELECT symbol FROM portfolio WHERE user_id = ?", session["user_id"])

    if request.method == "POST":

        user_id = session["user_id"]
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        dic = lookup(symbol)

        if not symbol:
            return apology("missing symbol", 400)

        if not shares:
            return apology("missing shares", 400)

        if shares <= 0:
            return apology("invalid number of shares", 400)

        item_price = dic['price']
        total_price = shares * item_price

        shares_owned = db.execute("SELECT shares FROM portfolio WHERE symbol = ? AND user_id = ?", symbol, user_id)[0]["shares"]

        if shares_owned < shares:
            return apology("not enough share(s)", 400)

        current_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        db.execute("UPDATE users SET cash = ? WHERE id = ?", current_cash + total_price, user_id)

        if shares_owned - shares == 0:
            db.execute("DELETE FROM portfolio WHERE symbol = ? AND user_id = ?", symbol, user_id)
        else:
            new_shares = shares_owned - shares
            db.execute("UPDATE portfolio SET shares = ?, total_price = ? WHERE user_id = ? AND symbol = ?",
                       new_shares, new_shares * item_price, user_id, symbol)

        now = datetime.now()
        dt_string = now.strftime("%d-%m-%Y %H:%M:%S")

        db.execute("INSERT INTO history (user_id, symbol, shares, price, total_price, operation, transacted) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   user_id, symbol, -shares, item_price, total_price, "SELL", dt_string)

        flash("Sold!")
        return redirect("/")
    else:
        return render_template("sell.html", symbols=sell_symbol)