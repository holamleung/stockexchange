import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///stockx.db")

# Add an additional table to the SQLite database if it hasn't been created
db.execute("CREATE TABLE IF NOT EXISTS transactions (id INTEGER, user_id INTEGER NOT NULL, type TEXT NOT NULL, symbol TEXT, shares INTEGER, price NUMERIC, total NUMERIC NOT NULL, transacted DATETIME NOT NULL, PRIMARY KEY (id), FOREIGN KEY (user_id) REFERENCES users(id))")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    cash = user[0]["cash"]
    balance = cash
    stocks = db.execute(
        "SELECT symbol, SUM(shares) FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0 ORDER BY symbol", session["user_id"])
    for stock in stocks:
        quote = lookup(stock["symbol"])
        stock["market_price"] = quote["price"]
        stock["name"] = quote["name"]
        stock["total"] = stock["SUM(shares)"] * stock["market_price"]
        balance += stock["total"]
    return render_template("index.html", stocks=stocks, cash=usd(cash), balance=usd(balance))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST
    if request.method == "POST":
        symbol = request.form.get("symbol")

        # Ensure symbol was submitted
        if not symbol:
            return apology("missing symbol", 400)
        quote = lookup(symbol)

        # Ensure symbol is valid
        if not quote:
            return apology("invalid symbol", 400)
        else:
            symbol = symbol.upper()
        shares = request.form.get("shares")

        # Ensure a positive integer number is submitted for shares
        if not shares.isdigit() or int(shares) <= 0:
            return apology("invalid number", 400)
        else:
            shares = int(shares)
        price = quote["price"]
        cost = price * shares
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        cash = rows[0]["cash"]

        # Ensure enough cash
        if cost > cash:
            return apology("not enough cash", 400)

        # Add transaction to the database
        else:
            db.execute("INSERT INTO transactions (user_id, type, symbol, shares, price, total, transacted) VALUES(?, 'buy', ?, ?, ?, ?, datetime('now', 'localtime'))", session["user_id"], symbol, shares, usd(price), usd(cost))
            db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", cost, session["user_id"])

            # Notify buy was made
            message = "Bought %i share(s) of %s" % (shares, symbol)
            flash(message)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT type, symbol, shares, price, total, transacted FROM transactions WHERE user_id = ?", session["user_id"])
    return render_template("history.html", transactions=transactions)


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

    # User reached route via POST
    if request.method == "POST":
        symbol = request.form.get("symbol")

        # Ensure symbol is submitted
        if not symbol:
            return apology("missing symbol", 400)
        quote = lookup(symbol)

        # Ensure symbol is valid
        if not quote:
            return apology("invalid symbol", 400)

        # Redirect user to lookup page
        return render_template("lookup.html", quote=quote)

    # User reached route via GET
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST
    if request.method == "POST":
        username = request.form.get("username")

        # Ensure username is submitted
        if not username:
            return apology("missing username", 400)

        # Ensure not duplicated username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) == 1:
            return apology("username is not available", 400)
        password = request.form.get("password")

        # Ensure password is submitted
        if not password:
            return apology("missing password", 400)
        confirmation = request.form.get("confirmation")

        # Ensure password confirmation is submitted and matched
        if not confirmation or confirmation != password:
            return apology("passwords don't match", 400)

        # Hash user's password
        pwhash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=8)

        # Store new user's login in database
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, pwhash)

        # Notify registration finished
        flash("Registration success!")

        # Redirect user to login page
        return render_template("login.html")

    # User reached route via GET
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST
    if request.method == "POST":
        symbol = request.form.get("symbol")

        # Ensure symbol is submitted
        if not symbol:
            return apology("missing symbol", 400)
        quote = lookup(symbol)

        # Ensure symbol is valid
        if not quote:
            return apology("invalid symbol", 400)
        shares_sell = request.form.get("shares")

        # Ensure a positive integer number is submitted for shares
        if not shares_sell.isdigit() or int(shares_sell) <= 0:
            return apology("invalid number of shares", 400)
        else:
            shares_sell = int(shares_sell)
        price = quote["price"]
        owns = db.execute(
            "SELECT SUM(shares) FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", session["user_id"], symbol)
        shares_own = owns[0]["SUM(shares)"]

        # Ensure user has enough shares to sell
        if shares_sell > shares_own:
            return apology("not enough shares", 400)
        else:
            income = shares_sell * price

        # Update sell to the database
        db.execute(
            "INSERT INTO transactions (user_id, type, symbol, shares, price, total, transacted) VALUES(?, 'sell', ?, ?, ?, ?, datetime('now', 'localtime'))", session["user_id"], symbol, -(shares_sell), usd(price), usd(income))
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", income, session["user_id"])

        # Notify sell was made
        message = "Sold %i share(s) of %s" % (shares_sell, symbol)
        flash(message)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET
    else:

        # A list of symbol user own
        symbols = []
        transactions = db.execute(
            "SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0 ORDER BY symbol", session["user_id"])
        for transaction in transactions:
            symbols.append(transaction["symbol"])
        return render_template("sell.html", symbols=symbols)


@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    """Transfer cash in or out"""

    # User reached route via POST
    if request.method == "POST":
        amount = request.form.get("amount")

        # Ensure amount is submitted
        if not amount:
            return apology("missing number", 400)

        # Ensure amount is positive integer
        elif not amount.isdigit() or int(amount) <= 0:
            return apology("invalid number", 400)
        else:
            amount = int(amount)

        # Ensure transfter type is submitted
        if not request.form.get("type"):
            return apology("missing transfer type", 400)
        else:
            trans_type = request.form.get("type")

        # If transfer out
        if trans_type == "out":
            user = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
            cash = user[0]["cash"]

            # Ensure user has enought cash in account
            if amount > cash:
                return apology("not enough cash", 400)
            else:
                db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", amount, session["user_id"])
                message = "Transfered out %s" % (usd(amount))

        # If transfer in
        else:
            db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", amount, session["user_id"])
            message = "Transfered in %s" % (usd(amount))
        db.execute("INSERT INTO transactions (user_id, type, total, transacted) VALUES(?, ?, ?, datetime('now', 'localtime'))", session["user_id"], trans_type, usd(amount))

        # Notify user transfers is made
        flash(message)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET
    else:
        return render_template("transfer.html")


@app.errorhandler(Exception)
def errorhandler(e):
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)
