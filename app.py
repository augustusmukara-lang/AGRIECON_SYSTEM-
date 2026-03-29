from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, make_response
import sqlite3
import os
import csv
import io
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# =========================
# BASE DIRECTORY
# =========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# =========================
# DATABASE
# =========================
DATABASE = os.path.join(BASE_DIR, "agriecon.db")

# =========================
# UPLOAD FOLDERS
# =========================
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PROFILE_FOLDER = os.path.join(UPLOAD_FOLDER, "profile")
RECEIPT_FOLDER = os.path.join(UPLOAD_FOLDER, "receipts")
REPORT_FOLDER = os.path.join(UPLOAD_FOLDER, "reports")
DOC_FOLDER = os.path.join(UPLOAD_FOLDER, "farm_docs")

os.makedirs(PROFILE_FOLDER, exist_ok=True)
os.makedirs(RECEIPT_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)
os.makedirs(DOC_FOLDER, exist_ok=True)
os.makedirs(os.path.join("static", "charts"), exist_ok=True)

# =========================
# DATABASE CONNECTION
# =========================
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# =========================
# INITIALIZE DATABASE
# =========================
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Farmers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS farmers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT,
        farm_name TEXT,
        phone TEXT,
        email TEXT,
        location TEXT,
        farm_size TEXT,
        enterprise_type TEXT,
        soil_type TEXT,
        irrigation_type TEXT,
        bio TEXT,
        profile_photo TEXT
    )
    """)

    # Inputs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inputs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        input_name TEXT,
        quantity REAL,
        unit TEXT,
        unit_cost REAL,
        total_cost REAL,
        supplier TEXT,
        date_added TEXT
    )
    """)

    # Production activities
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS production_activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        activity_name TEXT,
        crop_name TEXT,
        field_name TEXT,
        labour_used REAL,
        cost REAL,
        date_done TEXT,
        notes TEXT
    )
    """)

    # Labour
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS labour (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        worker_name TEXT,
        labour_type TEXT,
        activity TEXT,
        days_worked REAL,
        wage_rate REAL,
        total_paid REAL,
        date_added TEXT
    )
    """)

    # Harvests
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS harvests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        crop_name TEXT,
        quantity REAL,
        unit TEXT,
        harvest_date TEXT,
        notes TEXT
    )
    """)

    # Sales
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        product_name TEXT,
        quantity REAL,
        unit TEXT,
        price_per_unit REAL,
        total_sales REAL,
        buyer TEXT,
        market TEXT,
        sale_date TEXT
    )
    """)

    # Budgets
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        enterprise_name TEXT,
        season TEXT,
        estimated_cost REAL,
        estimated_revenue REAL,
        estimated_profit REAL
    )
    """)

    # Market records
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS market_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        product_name TEXT,
        market_name TEXT,
        price REAL,
        quantity_supplied REAL,
        quantity_demanded REAL,
        date_recorded TEXT
    )
    """)

    # Visitor messages
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        farmer_username TEXT,
        visitor_name TEXT,
        visitor_email TEXT,
        subject TEXT,
        message TEXT,
        date_sent TEXT
    )
    """)

    conn.commit()
    conn.close()

# =========================
# HELPER FUNCTIONS
# =========================
def login_required():
    return "user" in session

def calculate_total_cost(username):
    conn = get_db()
    inputs_total = conn.execute("""
        SELECT COALESCE(SUM(total_cost), 0) AS total FROM inputs WHERE username=?
    """, (username,)).fetchone()["total"]

    production_total = conn.execute("""
        SELECT COALESCE(SUM(cost), 0) AS total FROM production_activities WHERE username=?
    """, (username,)).fetchone()["total"]

    labour_total = conn.execute("""
        SELECT COALESCE(SUM(total_paid), 0) AS total FROM labour WHERE username=?
    """, (username,)).fetchone()["total"]

    conn.close()
    return inputs_total + production_total + labour_total

def calculate_total_revenue(username):
    conn = get_db()
    revenue = conn.execute("""
        SELECT COALESCE(SUM(total_sales), 0) AS total FROM sales WHERE username=?
    """, (username,)).fetchone()["total"]
    conn.close()
    return revenue

def calculate_total_output(username):
    conn = get_db()
    output = conn.execute("""
        SELECT COALESCE(SUM(quantity), 0) AS total FROM harvests WHERE username=?
    """, (username,)).fetchone()["total"]
    conn.close()
    return output

def generate_line_chart(x, y, title, xlabel, ylabel, filename):
    plt.figure(figsize=(8, 4))
    plt.plot(x, y, marker='o')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    chart_path = os.path.join("static", "charts", filename)
    plt.savefig(chart_path)
    plt.close()
    return filename

# =========================
# HOME PAGE
# =========================
@app.route("/")
def home():
    return render_template("index.html")

# =========================
# REGISTER
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        conn = get_db()
        existing = conn.execute("SELECT * FROM farmers WHERE username=?", (username,)).fetchone()

        if existing:
            conn.close()
            return render_template("register.html", error="Username already exists.")

        conn.execute("INSERT INTO farmers (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return redirect(url_for("login"))

    return render_template("register.html")

# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        conn = get_db()
        farmer = conn.execute("""
            SELECT * FROM farmers WHERE username=? AND password=?
        """, (username, password)).fetchone()
        conn.close()

        if farmer:
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid username or password.")

    return render_template("login.html")

# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))

    username = session["user"]
    conn = get_db()

    farmer = conn.execute("SELECT * FROM farmers WHERE username=?", (username,)).fetchone()
    total_cost = calculate_total_cost(username)
    total_revenue = calculate_total_revenue(username)
    total_profit = total_revenue - total_cost
    total_output = calculate_total_output(username)

    inputs_count = conn.execute("SELECT COUNT(*) AS count FROM inputs WHERE username=?", (username,)).fetchone()["count"]
    sales_count = conn.execute("SELECT COUNT(*) AS count FROM sales WHERE username=?", (username,)).fetchone()["count"]
    activities_count = conn.execute("SELECT COUNT(*) AS count FROM production_activities WHERE username=?", (username,)).fetchone()["count"]
    labour_count = conn.execute("SELECT COUNT(*) AS count FROM labour WHERE username=?", (username,)).fetchone()["count"]

    conn.close()

    return render_template(
        "dashboard.html",
        farmer=farmer,
        total_cost=total_cost,
        total_revenue=total_revenue,
        total_profit=total_profit,
        total_output=total_output,
        inputs_count=inputs_count,
        sales_count=sales_count,
        activities_count=activities_count,
        labour_count=labour_count
    )

# =========================
# EDIT FARM PROFILE
# =========================
@app.route("/edit_farm", methods=["GET", "POST"])
def edit_farm():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        farm_name = request.form.get("farm_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        location = request.form.get("location", "").strip()
        farm_size = request.form.get("farm_size", "").strip()
        enterprise_type = request.form.get("enterprise_type", "").strip()
        soil_type = request.form.get("soil_type", "").strip()
        irrigation_type = request.form.get("irrigation_type", "").strip()
        bio = request.form.get("bio", "").strip()

        current = conn.execute("SELECT * FROM farmers WHERE username=?", (session["user"],)).fetchone()
        filename = current["profile_photo"] if current and current["profile_photo"] else None

        photo = request.files.get("profile_photo")
        if photo and photo.filename:
            filename = photo.filename
            photo.save(os.path.join(PROFILE_FOLDER, filename))

        conn.execute("""
            UPDATE farmers
            SET full_name=?, farm_name=?, phone=?, email=?, location=?, farm_size=?,
                enterprise_type=?, soil_type=?, irrigation_type=?, bio=?, profile_photo=?
            WHERE username=?
        """, (
            full_name, farm_name, phone, email, location, farm_size,
            enterprise_type, soil_type, irrigation_type, bio, filename, session["user"]
        ))
        conn.commit()

    farmer = conn.execute("SELECT * FROM farmers WHERE username=?", (session["user"],)).fetchone()
    conn.close()
    return render_template("edit_farm.html", farmer=farmer)

# =========================
# INPUTS
# =========================
@app.route("/inputs", methods=["GET", "POST"])
def inputs():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":
        input_name = request.form["input_name"]
        quantity = float(request.form["quantity"])
        unit = request.form["unit"]
        unit_cost = float(request.form["unit_cost"])
        supplier = request.form["supplier"]
        date_added = request.form["date_added"]
        total_cost = quantity * unit_cost

        conn.execute("""
            INSERT INTO inputs (username, input_name, quantity, unit, unit_cost, total_cost, supplier, date_added)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (session["user"], input_name, quantity, unit, unit_cost, total_cost, supplier, date_added))
        conn.commit()

    records = conn.execute("SELECT * FROM inputs WHERE username=? ORDER BY id DESC", (session["user"],)).fetchall()
    conn.close()
    return render_template("inputs.html", records=records)

# =========================
# PRODUCTION
# =========================
@app.route("/production", methods=["GET", "POST"])
def production():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":
        activity_name = request.form["activity_name"]
        crop_name = request.form["crop_name"]
        field_name = request.form["field_name"]
        labour_used = float(request.form["labour_used"])
        cost = float(request.form["cost"])
        date_done = request.form["date_done"]
        notes = request.form["notes"]

        conn.execute("""
            INSERT INTO production_activities (username, activity_name, crop_name, field_name, labour_used, cost, date_done, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (session["user"], activity_name, crop_name, field_name, labour_used, cost, date_done, notes))
        conn.commit()

    records = conn.execute("SELECT * FROM production_activities WHERE username=? ORDER BY id DESC", (session["user"],)).fetchall()
    conn.close()
    return render_template("production.html", records=records)

# =========================
# LABOUR
# =========================
@app.route("/labour", methods=["GET", "POST"])
def labour():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":
        worker_name = request.form["worker_name"]
        labour_type = request.form["labour_type"]
        activity = request.form["activity"]
        days_worked = float(request.form["days_worked"])
        wage_rate = float(request.form["wage_rate"])
        date_added = request.form["date_added"]
        total_paid = days_worked * wage_rate

        conn.execute("""
            INSERT INTO labour (username, worker_name, labour_type, activity, days_worked, wage_rate, total_paid, date_added)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (session["user"], worker_name, labour_type, activity, days_worked, wage_rate, total_paid, date_added))
        conn.commit()

    records = conn.execute("SELECT * FROM labour WHERE username=? ORDER BY id DESC", (session["user"],)).fetchall()
    conn.close()
    return render_template("labour.html", records=records)

# =========================
# HARVEST
# =========================
@app.route("/harvest", methods=["GET", "POST"])
def harvest():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":
        crop_name = request.form["crop_name"]
        quantity = float(request.form["quantity"])
        unit = request.form["unit"]
        harvest_date = request.form["harvest_date"]
        notes = request.form["notes"]

        conn.execute("""
            INSERT INTO harvests (username, crop_name, quantity, unit, harvest_date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session["user"], crop_name, quantity, unit, harvest_date, notes))
        conn.commit()

    records = conn.execute("SELECT * FROM harvests WHERE username=? ORDER BY id DESC", (session["user"],)).fetchall()
    conn.close()
    return render_template("harvest.html", records=records)

# =========================
# SALES
# =========================
@app.route("/sales", methods=["GET", "POST"])
def sales():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":
        product_name = request.form["product_name"]
        quantity = float(request.form["quantity"])
        unit = request.form["unit"]
        price_per_unit = float(request.form["price_per_unit"])
        buyer = request.form["buyer"]
        market = request.form["market"]
        sale_date = request.form["sale_date"]
        total_sales = quantity * price_per_unit

        conn.execute("""
            INSERT INTO sales (username, product_name, quantity, unit, price_per_unit, total_sales, buyer, market, sale_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session["user"], product_name, quantity, unit, price_per_unit, total_sales, buyer, market, sale_date))
        conn.commit()

    records = conn.execute("SELECT * FROM sales WHERE username=? ORDER BY id DESC", (session["user"],)).fetchall()
    conn.close()
    return render_template("sales.html", records=records)

# =========================
# BUDGETS
# =========================
@app.route("/budgets", methods=["GET", "POST"])
def budgets():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":
        enterprise_name = request.form["enterprise_name"]
        season = request.form["season"]
        estimated_cost = float(request.form["estimated_cost"])
        estimated_revenue = float(request.form["estimated_revenue"])
        estimated_profit = estimated_revenue - estimated_cost

        conn.execute("""
            INSERT INTO budgets (username, enterprise_name, season, estimated_cost, estimated_revenue, estimated_profit)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session["user"], enterprise_name, season, estimated_cost, estimated_revenue, estimated_profit))
        conn.commit()

    records = conn.execute("SELECT * FROM budgets WHERE username=? ORDER BY id DESC", (session["user"],)).fetchall()
    conn.close()
    return render_template("budgets.html", records=records)

# =========================
# MARKET
# =========================
@app.route("/market", methods=["GET", "POST"])
def market():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":
        product_name = request.form["product_name"]
        market_name = request.form["market_name"]
        price = float(request.form["price"])
        quantity_supplied = float(request.form["quantity_supplied"])
        quantity_demanded = float(request.form["quantity_demanded"])
        date_recorded = request.form["date_recorded"]

        conn.execute("""
            INSERT INTO market_prices (username, product_name, market_name, price, quantity_supplied, quantity_demanded, date_recorded)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session["user"], product_name, market_name, price, quantity_supplied, quantity_demanded, date_recorded))
        conn.commit()

    records = conn.execute("SELECT * FROM market_prices WHERE username=? ORDER BY id DESC", (session["user"],)).fetchall()
    conn.close()
    return render_template("market.html", records=records)

# =========================
# MICROECONOMICS
# =========================
@app.route("/economics")
def economics():
    if not login_required():
        return redirect(url_for("login"))

    username = session["user"]

    total_cost = calculate_total_cost(username)
    total_revenue = calculate_total_revenue(username)
    total_profit = total_revenue - total_cost
    total_output = calculate_total_output(username)

    average_cost = total_cost / total_output if total_output > 0 else 0
    average_revenue = total_revenue / total_output if total_output > 0 else 0
    profit_per_unit = total_profit / total_output if total_output > 0 else 0
    break_even_output = total_cost / average_revenue if average_revenue > 0 else 0
    marginal_profit_signal = "Positive" if total_profit > 0 else "Negative or Zero"

    return render_template(
        "economics.html",
        total_cost=total_cost,
        total_revenue=total_revenue,
        total_profit=total_profit,
        total_output=total_output,
        average_cost=average_cost,
        average_revenue=average_revenue,
        profit_per_unit=profit_per_unit,
        break_even_output=break_even_output,
        marginal_profit_signal=marginal_profit_signal
    )

# =========================
# MACROECONOMICS + POLICY SIMULATION
# =========================
@app.route("/macroeconomics", methods=["GET", "POST"])
def macroeconomics():
    if not login_required():
        return redirect(url_for("login"))

    username = session["user"]
    total_cost = calculate_total_cost(username)
    total_revenue = calculate_total_revenue(username)

    inflation_rate = 10
    interest_rate = 12
    subsidy_rate = 0
    tax_rate = 0
    exchange_rate_effect = 0

    simulated_cost = total_cost
    simulated_profit = total_revenue - simulated_cost

    if request.method == "POST":
        inflation_rate = float(request.form.get("inflation_rate", 10))
        interest_rate = float(request.form.get("interest_rate", 12))
        subsidy_rate = float(request.form.get("subsidy_rate", 0))
        tax_rate = float(request.form.get("tax_rate", 0))
        exchange_rate_effect = float(request.form.get("exchange_rate_effect", 0))

        inflation_cost = total_cost * (inflation_rate / 100)
        interest_cost = total_cost * (interest_rate / 100) * 0.1
        exchange_cost = total_cost * (exchange_rate_effect / 100) * 0.15
        subsidy_reduction = total_cost * (subsidy_rate / 100)
        tax_reduction = total_revenue * (tax_rate / 100)

        simulated_cost = total_cost + inflation_cost + interest_cost + exchange_cost - subsidy_reduction
        simulated_profit = total_revenue - simulated_cost - tax_reduction

    return render_template(
        "macroeconomics.html",
        total_cost=total_cost,
        total_revenue=total_revenue,
        inflation_rate=inflation_rate,
        interest_rate=interest_rate,
        subsidy_rate=subsidy_rate,
        tax_rate=tax_rate,
        exchange_rate_effect=exchange_rate_effect,
        simulated_cost=simulated_cost,
        simulated_profit=simulated_profit
    )

# =========================
# ANALYTICS + REGRESSION + CHARTS
# =========================
@app.route("/analytics")
def analytics():
    if not login_required():
        return redirect(url_for("login"))

    username = session["user"]
    conn = get_db()

    sales = conn.execute("SELECT sale_date, total_sales FROM sales WHERE username=? ORDER BY sale_date", (username,)).fetchall()
    inputs = conn.execute("SELECT date_added, total_cost FROM inputs WHERE username=? ORDER BY date_added", (username,)).fetchall()
    market = conn.execute("SELECT quantity_supplied, quantity_demanded, price FROM market_prices WHERE username=?", (username,)).fetchall()

    conn.close()

    sales_dates = [row["sale_date"] for row in sales]
    sales_values = [row["total_sales"] for row in sales]

    input_dates = [row["date_added"] for row in inputs]
    input_values = [row["total_cost"] for row in inputs]

    sales_chart = None
    cost_chart = None

    if len(sales_dates) > 0:
        sales_chart = generate_line_chart(sales_dates, sales_values, "Sales Trend", "Date", "Sales (KSh)", "sales_chart.png")

    if len(input_dates) > 0:
        cost_chart = generate_line_chart(input_dates, input_values, "Input Cost Trend", "Date", "Cost (KSh)", "cost_chart.png")

    regression_result = None
    correlation_result = None

    if len(market) >= 2:
        supplied = np.array([row["quantity_supplied"] for row in market], dtype=float)
        demanded = np.array([row["quantity_demanded"] for row in market], dtype=float)
        prices = np.array([row["price"] for row in market], dtype=float)

        try:
            slope, intercept = np.polyfit(supplied, prices, 1)
            correlation_result = np.corrcoef(supplied, prices)[0, 1]
            regression_result = {
                "equation": f"Price = {slope:.2f} * Supply + {intercept:.2f}",
                "correlation": round(float(correlation_result), 4)
            }
        except:
            regression_result = {
                "equation": "Not enough valid market data",
                "correlation": 0
            }

    return render_template(
        "analytics.html",
        sales_chart=sales_chart,
        cost_chart=cost_chart,
        regression_result=regression_result
    )

# =========================
# REPORTS PAGE
# =========================
@app.route("/reports")
def reports():
    if not login_required():
        return redirect(url_for("login"))

    username = session["user"]
    conn = get_db()

    farmer = conn.execute("SELECT * FROM farmers WHERE username=?", (username,)).fetchone()
    inputs = conn.execute("SELECT * FROM inputs WHERE username=?", (username,)).fetchall()
    production = conn.execute("SELECT * FROM production_activities WHERE username=?", (username,)).fetchall()
    labour = conn.execute("SELECT * FROM labour WHERE username=?", (username,)).fetchall()
    harvests = conn.execute("SELECT * FROM harvests WHERE username=?", (username,)).fetchall()
    sales = conn.execute("SELECT * FROM sales WHERE username=?", (username,)).fetchall()
    budgets = conn.execute("SELECT * FROM budgets WHERE username=?", (username,)).fetchall()
    market = conn.execute("SELECT * FROM market_prices WHERE username=?", (username,)).fetchall()

    total_cost = calculate_total_cost(username)
    total_revenue = calculate_total_revenue(username)
    total_profit = total_revenue - total_cost

    conn.close()

    return render_template(
        "reports.html",
        farmer=farmer,
        inputs=inputs,
        production=production,
        labour=labour,
        harvests=harvests,
        sales=sales,
        budgets=budgets,
        market=market,
        total_cost=total_cost,
        total_revenue=total_revenue,
        total_profit=total_profit
    )

# =========================
# EXPORT CSV
# =========================
@app.route("/export/csv/<table_name>")
def export_csv(table_name):
    if not login_required():
        return redirect(url_for("login"))

    allowed = {
        "inputs": "inputs",
        "production": "production_activities",
        "labour": "labour",
        "harvests": "harvests",
        "sales": "sales",
        "budgets": "budgets",
        "market": "market_prices"
    }

    if table_name not in allowed:
        return "Invalid table", 400

    conn = get_db()
    rows = conn.execute(f"SELECT * FROM {allowed[table_name]} WHERE username=?", (session["user"],)).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    if rows:
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow(list(row))

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={table_name}.csv"
    response.headers["Content-type"] = "text/csv"
    return response

# =========================
# EXPORT PDF
# =========================
@app.route("/export/pdf")
def export_pdf():
    if not login_required():
        return redirect(url_for("login"))

    username = session["user"]
    total_cost = calculate_total_cost(username)
    total_revenue = calculate_total_revenue(username)
    total_profit = total_revenue - total_cost
    total_output = calculate_total_output(username)

    pdf_path = os.path.join(REPORT_FOLDER, f"{username}_report.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Agricultural Economics Farm Report", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Farmer Username: {username}", styles["Normal"]))
    elements.append(Paragraph(f"Date Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    data = [
        ["Indicator", "Value"],
        ["Total Cost", f"KSh {total_cost:.2f}"],
        ["Total Revenue", f"KSh {total_revenue:.2f}"],
        ["Total Profit", f"KSh {total_profit:.2f}"],
        ["Total Output", f"{total_output:.2f}"]
    ]

    table = Table(data, colWidths=[200, 200])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
    ]))

    elements.append(table)
    doc.build(elements)

    return send_from_directory(REPORT_FOLDER, f"{username}_report.pdf", as_attachment=True)

# =========================
# PUBLIC FARM PROFILE
# =========================
@app.route("/public/<username>", methods=["GET", "POST"])
def public_farm(username):
    conn = get_db()

    farmer = conn.execute("""
        SELECT * FROM farmers WHERE LOWER(username)=LOWER(?)
    """, (username,)).fetchone()

    if not farmer:
        conn.close()
        return "Farmer profile not found", 404

    db_user = farmer["username"]

    sales = conn.execute("SELECT * FROM sales WHERE username=? ORDER BY id DESC LIMIT 5", (db_user,)).fetchall()
    harvests = conn.execute("SELECT * FROM harvests WHERE username=? ORDER BY id DESC LIMIT 5", (db_user,)).fetchall()

    success = None

    if request.method == "POST":
        visitor_name = request.form.get("visitor_name", "").strip()
        visitor_email = request.form.get("visitor_email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        if visitor_name and visitor_email and subject and message:
            conn.execute("""
                INSERT INTO messages (farmer_username, visitor_name, visitor_email, subject, message, date_sent)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (db_user, visitor_name, visitor_email, subject, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            success = "Your message has been sent successfully!"

    conn.close()

    return render_template(
        "public_farm.html",
        farmer=farmer,
        sales=sales,
        harvests=harvests,
        success=success
    )

# =========================
# DELETE RECORDS
# =========================
@app.route("/delete/<table>/<int:item_id>")
def delete_record(table, item_id):
    if not login_required():
        return redirect(url_for("login"))

    allowed_tables = {
        "inputs": "inputs",
        "production": "production_activities",
        "labour": "labour",
        "harvests": "harvests",
        "sales": "sales",
        "budgets": "budgets",
        "market": "market_prices"
    }

    if table not in allowed_tables:
        return redirect(url_for("dashboard"))

    conn = get_db()
    conn.execute(f"DELETE FROM {allowed_tables[table]} WHERE id=? AND username=?", (item_id, session["user"]))
    conn.commit()
    conn.close()

    return redirect(request.referrer or url_for("dashboard"))

# =========================
# DOWNLOAD FILES
# =========================
@app.route("/download/<folder>/<filename>")
def download_file(folder, filename):
    folder_map = {
        "profile": PROFILE_FOLDER,
        "receipts": RECEIPT_FOLDER,
        "reports": REPORT_FOLDER,
        "farm_docs": DOC_FOLDER
    }

    if folder not in folder_map:
        return "Invalid folder", 400

    return send_from_directory(folder_map[folder], filename)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    init_db()
    print("Using database:", DATABASE)
    app.run(debug=True)