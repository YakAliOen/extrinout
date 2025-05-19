import sqlite3
from flask import Flask, render_template, request, session, redirect
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

# Initialize Flask app
app = Flask(__name__)

# Session configuration
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Database connection setup
conn = sqlite3.connect("extrinout.db", check_same_thread=False)
conn.row_factory = sqlite3.Row  # This makes the results like dicts
db = conn.cursor()

# Custom filter for currency formatting
def idr(value):
    return f"Rp {value:,.2f}"

# Jinja filter setup
app.jinja_env.filters["idr"] = idr

# Decorator for login requirement
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# Custom apology message
def apology(message, code=400):
    return render_template("apology.html", message=message), code

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
    # Get expenses grouped by category and ordered by date (most recent first)
    expenses = db.execute(
        "SELECT category, SUM(amount) AS total_amount, MAX(date) AS last_date FROM expenses WHERE user_id = ? GROUP BY category ORDER BY last_date DESC",
        (session["user_id"],)
    ).fetchall()

    # Calculate total expenses
    total_expenses = sum(expense["total_amount"] for expense in expenses)

    return render_template("index.html", expenses=expenses, total_expenses=total_expenses)


@app.route("/add_expenses", methods=["GET", "POST"])
@login_required
def add_expenses():
    if request.method == "GET":
        return render_template("add_expenses.html")
    else:
        # Retrieve user inputs
        amount = request.form.get("amount")
        category = request.form.get("category")
        date = request.form.get("date")
        #type_ = request.form.get("type")

        # Validate inputs
        if not amount or not category or not date:
            return apology("All fields must be filled", 400)
        
        #if type_ not in ["IN", "OUT"]:
            #return apology("Invalid type selected", 400)

        try:
            amount = float(amount)  # Convert amount to float
            if amount <= 0:
                return apology("Amount must be a positive number", 400)
        except ValueError:
            return apology("Invalid amount format", 400)

        # Insert expense into database
        db.execute("INSERT INTO expenses (user_id, amount, category, date) VALUES (?, ?, ?, ?)",
                   (session["user_id"], amount, category, date))
        conn.commit()

        return redirect("/")


@app.route("/history", methods=["GET"])
@login_required
def history():
    # Get sorting parameter from URL (default: sort by date descending)
    sort_by = request.args.get("sort", "date")
    order = request.args.get("order", "DESC")

    # Validate sorting options
    valid_sort_columns = ["category", "date", "amount"]
    if sort_by not in valid_sort_columns:
        sort_by = "date"
    if order not in ["ASC", "DESC"]:
        order = "DESC"

    # Fetch expenses from the database with sorting
    expenses = db.execute(f"""
        SELECT amount, category, date FROM expenses
        WHERE user_id = ? ORDER BY {sort_by} {order}
    """, (session["user_id"],)).fetchall()

    return render_template("history.html", expenses=expenses, sort_by=sort_by, order=order)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
            return apology("must provide username", 403)
        if not password:
            return apology("must provide password", 403)

        # Query database for user
        rows = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchall()

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            return apology("invalid username and/or password", 403)

        # Store user session details
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]  # Store username in session

        return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Clear session
    session.clear()

    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not username or not password or not confirmation:
            return apology("user's input is blank", 400)
        elif len(password) < 8 or len(confirmation) < 8:
            return apology("password of 8 characters", 400)
        elif password != confirmation:
            return apology("passwords do not match", 400)
        else:
            try:
                hash = generate_password_hash(password)
                db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", (username, hash))
                conn.commit()
                return redirect("/")
            except ValueError:
                return apology("username already exists", 400)


@app.route("/delete_expenses", methods=["GET", "POST"])
@login_required
def delete_expenses():
    if request.method == "GET":
        expenses = db.execute(
            "SELECT id, amount, category, date FROM expenses WHERE user_id = ?", (session["user_id"],)
        ).fetchall()
        return render_template("delete_expenses.html", expenses=expenses)
    else:
        expense_id = request.form.get("expense_id")

        if not expense_id:
            return apology("Please select an expense to delete", 400)

        # Check if the expense exists
        expense = db.execute(
            "SELECT * FROM expenses WHERE id = ? AND user_id = ?", (expense_id, session["user_id"])
        ).fetchall()

        if not expense:
            return apology("Expense not found", 400)

        # Delete the expense
        db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()

        return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)