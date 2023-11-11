import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

from datetime import datetime


# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


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
    """Show portfolio of stocks"""
    username = session["user_id"]
    table_name = "stocks_" + str(username)
    user = db.execute("SELECT * FROM users WHERE id = ?", username)

    table_name = "stocks_" + str(username)
    check = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", table_name
    )
    # if the user doesn't have a table of stocks create it along with its history
    if not check:
        db.execute(
            "CREATE TABLE stocks_?(Username_id int, Symbol string, Shares int, Price float, Total float)",
            username,
        )
        db.execute(
            "CREATE TABLE history_?(Symbol string, Shares int, Price float, Timestamp Date)",
            username,
        )

    table = db.execute("SELECT * FROM ?", table_name)

    # Update values in table

    for row in table:
        symbol = row["Symbol"]
        shares = row["Shares"]
        price = lookup(symbol)
        db.execute(
            "UPDATE ? SET Price = ?, Total = ? WHERE Symbol = ?",
            table_name,
            price["price"],
            float(price["price"]) * shares,
            symbol,
        )

    # Loop to set the total value of the cash user has with all his stocks and the current money
    total_in_stocks = 0
    stocks_cash = 0
    for row in table:
        total_in_stocks += row["Total"]
        total = float(user[0]["cash"])
        stocks_cash = float(total_in_stocks) + total
    return render_template(
        "index.html", user=user[0]["cash"], stocks_cash=stocks_cash, table=table
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        # Check if the users prompts a valid symbol or a number of shares
        if not symbol:
            return apology("No symbol selected")
        if not shares:
            return apology("There aren't shares selected")
        check_sb = lookup(symbol)
        if not check_sb:
            return apology("Invalid Symbol")
        try:
            float(shares)
        except:
            return apology("Shares needs to be a number")

        if "." in shares or float(shares) < 0:
            return apology("Invalid number of shares")

        # get the id from the user through the session
        username = session["user_id"]
        table_name = "stocks_" + str(username)

        cash = db.execute("SELECT cash FROM users WHERE id=?", username)
        total_dict = lookup(symbol)
        total = float(total_dict["price"])
        spent = float(total) * float(shares)

        # if the money spent is less than the cash the user has he can't by any stocks
        if cash[0]["cash"] < float(spent):
            return apology("Not enough money")

        # Check if there are shares of that symbol and with the same price
        verify_symbol = db.execute(
            "SELECT * FROM ? WHERE Symbol = ?", table_name, symbol
        )
        if verify_symbol:
            new_total = float(verify_symbol[0]["Total"]) + float(spent)
            new_shares = float(verify_symbol[0]["Shares"]) + float(shares)
            db.execute(
                "UPDATE ? SET Total = ?, Shares = ? WHERE Symbol = ?",
                table_name,
                new_total,
                new_shares,
                symbol,
            )

        # Insert a new row of values fo the new symbol
        else:
            db.execute(
                "INSERT INTO stocks_? (Username_id, Symbol, Shares, Price, Total) VALUES (?, ?, ?, ?, ?)",
                username,
                username,
                symbol,
                shares,
                total,
                spent,
            )

        diff = cash[0]["cash"] - float(spent)

        # Update user's cash with the difference of the money he had and he spent variable
        db.execute("UPDATE users SET cash = ? WHERE id = ?", diff, username)

        # Update user's history
        timestamp = datetime.now().timestamp()
        formatted_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "INSERT INTO history_? (Symbol, Shares, Price, Timestamp) VALUES (?, ?, ?, ?)",
            username,
            symbol,
            shares,
            total,
            formatted_time,
        )

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user = session["user_id"]
    table_name = "history_" + str(user)
    check = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", table_name
    )
    if not check:
        return render_template("history.html")
    history = db.execute("SELECT * FROM history_?", user)
    return render_template("history.html", history=history)


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        if quote == None:
            return apology("Symbol Not Found")
        else:
            return render_template(
                "quote.html", name=quote["name"], price=quote["price"]
            )

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Ensure username doesn't exist
        rows = db.execute(
            "SELECT username FROM users WHERE username = ?",
            request.form.get("username"),
        )
        if len(rows) != 0:
            return apology("username alredy exists")

        # Ensure passwords match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("password doesn't match with confirmation, 403")

        # Inserts user into database while hashing the password

        db.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?)",
            request.form.get("username"),
            generate_password_hash(request.form.get("password")),
        )
        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("No symbol selected")
        # get the id from the user through the session
        user = session["user_id"]
        table_name = "stocks_" + str(user)
        check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", table_name
        )
        # if the user doesn't have a table of stocks return apology
        if not check:
            return apology("You don't have any stocks")
        # if not valid number of shares
        shares = request.form.get("shares")
        try:
            float(shares)
        except:
            return apology("Shares needs to be a number")

        if "." in shares or float(shares) < 0:
            return apology("Invalid number of shares")

        price = db.execute("SELECT Price FROM ? WHERE Symbol = ?", table_name, symbol)
        share_data = db.execute("SELECT * FROM ? WHERE Symbol = ?", table_name, symbol)
        shares_holder = int(share_data[0]["Shares"])
        if shares_holder < int(shares):
            return apology("Not enough shares")

        # Update database
        dt_base = db.execute(
            "SELECT Shares FROM ? WHERE Symbol = ?", table_name, symbol
        )
        is_cero = int(dt_base[0]["Shares"]) - int(shares)
        if is_cero == 0:
            db.execute("DELETE FROM ? WHERE Symbol = ?", table_name, symbol)
        else:
            total = db.execute(
                "SELECT Total FROM ? WHERE Symbol = ? ", table_name, symbol
            )
            db.execute(
                "UPDATE ? SET Shares = ?, Total = ? WHERE Symbol = ?",
                table_name,
                is_cero,
                (float(total[0]["Total"]) - (float(price[0]["Price"]) * int(shares))),
                symbol,
            )

        value = lookup(symbol)
        cash = db.execute("SELECT * FROM users WHERE id = ?", user)
        db.execute(
            "UPDATE users SET cash = ? WHERE id = ?",
            ((value["price"] * int(shares)) + float(cash[0]["cash"])),
            user,
        )

        timestamp = datetime.now().timestamp()
        formatted_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "INSERT INTO history_? (Symbol, Shares, Price, Timestamp) VALUES (?, -?, ?, ?)",
            user,
            symbol,
            shares,
            value["price"],
            formatted_time,
        )

        return redirect("/")

    else:
        symbol = request.form.get("symbol")
        user = session["user_id"]
        table_name = "stocks_" + str(user)
        check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", table_name
        )
        if check:
            row = db.execute("SELECT * FROM ?", table_name)
            return render_template("sell.html", table=row)
        else:
            return render_template("sell.html")


# Personal Touch (Add cash with password confirmation)
@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    if request.method == "POST":
        user = session["user_id"]
        cash = request.form.get("cash")
        password = request.form.get("password")

        if not cash:
            return apology("Need cash input")

        try:
            float(cash)
        except:
            return apology("Cash needs to be a number")

        if not password:
            return apology("Password required")

        rows = db.execute("SELECT * FROM users WHERE id = ?", user)

        if not check_password_hash(rows[0]["hash"], password):
            return apology("Invalid password", 403)

        if float(cash) < 0:
            return apology("Invalid quantity")

        prev_cash = db.execute(
            "SELECT cash FROM users WHERE id=?",
            user,
        )

        db.execute(
            "UPDATE users SET cash=? WHERE id=?",
            float(cash) + float(prev_cash[0]["cash"]),
            user,
        )

        return redirect("/")
    else:
        return render_template("cash.html")
