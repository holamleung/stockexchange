import os
from collections import namedtuple
from tempfile import mkdtemp

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql import text
from werkzeug.exceptions import HTTPException, InternalServerError
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

# Make sure Database url is set
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("Database url not set")

# Configure SQLAlchemy to use database
engine = create_engine(
    os.getenv("DATABASE_URL"),
    connect_args={"check_same_thread": False}
    )
db = scoped_session(sessionmaker(bind=engine))

# Create necessary tables to the database if they haven't been created
db.execute(text("""
    CREATE TABLE IF NOT EXISTS users (id INTEGER, username TEXT NOT NULL,
    hash TEXT NOT NULL, cash NUMERIC NOT NULL DEFAULT 10000.00,
    PRIMARY KEY(id))
    """))
db.execute("CREATE UNIQUE INDEX IF NOT EXISTS username ON users (username)")
db.execute(text("""
    CREATE TABLE IF NOT EXISTS transactions (id INTEGER,
    user_id INTEGER NOT NULL, type TEXT NOT NULL, symbol TEXT,
    shares INTEGER, price NUMERIC, total NUMERIC NOT NULL,
    transacted DATETIME NOT NULL, PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id))
    """))

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    
    # Retrive user's data
    s = text("SELECT * FROM users WHERE id = :id")
    user = db.execute(s, {"id": session["user_id"]}).fetchone()
    cash = user.cash
    balance = cash
    
    # Calculate the current total value of stocks owned by user
    summaries = []
    Summary = namedtuple("Summary", ["symbol", "name", "shares", "price", "total"])
    s = text("""
        SELECT symbol, SUM(shares) AS shares
        FROM transactions
        WHERE user_id = :user_id
        GROUP BY symbol
        HAVING SUM(shares) > 0
        ORDER BY symbol
        """)
    stocks = db.execute(s, {"user_id": session["user_id"]}).fetchall()
    for stock in stocks:
        quote = lookup(stock.symbol)
        total = stock.shares * quote["price"]
        balance += total
        summaries.append(Summary(stock.symbol, quote["name"], stock.shares,
            usd(quote["price"]), usd(total)))
    return render_template("index.html", summaries=summaries, cash=usd(cash),
        balance=usd(balance))


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
        s = text("SELECT * FROM users WHERE id = :id")
        user = db.execute(s, {"id": session["user_id"]}).fetchone()
        cash = user.cash

        # Ensure enough cash
        if cost > cash:
            return apology("not enough cash", 400)

        # Add transaction to the database
        else:
            s = text("""
                INSERT INTO transactions (user_id, type, symbol, shares,
                price, total, transacted)
                VALUES(:user_id, 'buy', :symbol, :shares, :price, :total,
                datetime('now', 'localtime'))
                """)
            db.execute(s, {"user_id": session["user_id"], "symbol": symbol,
                "shares": shares, "price": usd(price), "total": usd(cost)})
            s = text("""
                UPDATE users SET cash = (cash - :cost)
                WHERE id = :id
                """)
            db.execute(s, {"cost": cost, "id": session["user_id"]})
            db.commit()

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
    s = text("""
        SELECT type, symbol, shares, price, total, transacted
        FROM transactions
        WHERE user_id = :user_id
        """)
    transactions = db.execute(s, {"user_id": session["user_id"]}).fetchall()
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        username = request.form.get("username")
        password = request.form.get("password")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 403)
        
        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 403)

        # Query database for username
        user = db.execute("SELECT * FROM users WHERE username = :username",
            {"username": username}).fetchone()

        # Ensure username exists and password is correct
        if user is None or not check_password_hash(user.hash, password):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = user.id

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
        s = text("SELECT * FROM users WHERE username = :username")
        rows = db.execute(s, {"username": username}).fetchall()
        if len(rows) > 0:
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
        pwhash = generate_password_hash(password, method="pbkdf2:sha256",
            salt_length=8)

        # Store new user's login in database
        s = text("INSERT INTO users (username, hash) VALUES(:username, :hash)")
        db.execute(s, {"username": username, "hash": pwhash})
        db.commit()
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
        s = text("""
            SELECT SUM(shares) AS shares
            FROM transactions
            WHERE user_id = :user_id AND symbol = :symbol
            GROUP BY symbol
            """)
        owns = db.execute(s, {"user_id": session["user_id"],
            "symbol": symbol}).fetchone()
        shares_own = owns.shares

        # Ensure user has enough shares to sell
        if shares_sell > shares_own:
            return apology("not enough shares", 400)
        else:
            income = shares_sell * price

        # Update sell to the database
        s = text("""
            INSERT INTO transactions (user_id, type, symbol, shares, price,
            total, transacted)
            VALUES(:user_id, 'sell', :symbol, :shares, :price, :total,
            datetime('now', 'localtime'))
            """)
        db.execute(s, {"user_id": session["user_id"], "symbol": symbol,
            "shares": -(shares_sell), "price": usd(price),
            "total": usd(income)})
        s = text("""
            UPDATE users SET cash = (cash + :income) WHERE id = :user_id
            """)
        db.execute(s, {"income": income, "user_id": session["user_id"]})
        db.commit()

        # Notify sell was made
        message = "Sold %i share(s) of %s" % (shares_sell, symbol)
        flash(message)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET
    else:

        # A list of symbol user own
        s = text("""
            SELECT symbol
            FROM transactions
            WHERE user_id = :user_id
            GROUP BY symbol HAVING SUM(shares) > 0
            ORDER BY symbol
            """)
        symbols = db.execute(s, {"user_id": session["user_id"]}).fetchall()
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
        
        # Ensure amount is positive float
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return apology("invalid number", 400)

        # Ensure transfter type is submitted
        if not request.form.get("type"):
            return apology("missing transfer type", 400)
        else:
            trans_type = request.form.get("type")

        # If transfer out
        if trans_type == "out":
            s = text("SELECT cash FROM users WHERE id = :id")
            user = db.execute(s, {"id": session["user_id"]}).fetchone()

            # Ensure user has enought cash in account
            if amount > user.cash:
                return apology("not enough cash", 400)
            else:
                s = text("""
                    UPDATE users
                    SET cash = (cash - :amount)
                    WHERE id = :id
                    """)
                db.execute(s, {"amount": amount, "id": session["user_id"]})
                message = "Transfered out %s" % (usd(amount))

        # If transfer in
        else:
            s = text("""
                UPDATE users
                SET cash = (cash + :amount)
                WHERE id = :id
                """)
            db.execute(s, {"amount": amount, "id": session["user_id"]})
            message = "Transfered in %s" % (usd(amount))
        s = text("""
            INSERT INTO transactions (user_id, type, total, transacted)
            VALUES (:id, :type, :total, datetime('now', 'localtime'))
            """)
        db.execute(s, {"id": session["user_id"], "type": trans_type,
            "total": usd(amount)})
        db.commit()

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
