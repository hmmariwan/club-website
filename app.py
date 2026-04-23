from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
print(secrets.token_hex(16))

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

from flask import send_file
import os

app = Flask(__name__)
app.secret_key = "385587ae2ea5563e8bfc5d51adc0e0d2"  # simple for now

# Create DB (runs once)
def init_db():
    conn = sqlite3.connect("members.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            phone TEXT,
            interests TEXT,
            password TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/join", methods=["GET", "POST"])
def join():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        interests = request.form["interests"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect("members.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO members (name, email, phone, interests, password) VALUES (?, ?, ?, ?, ?)",
            (name, email, phone, interests, hashed_password)
        )
        conn.commit()
        conn.close()

        return redirect(f"/success?name={name}")

    return render_template("join.html")


@app.route("/success")
def success():
    name = request.args.get("name")
    return render_template("success.html", name=name)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("members.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM members WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[5], password):
            session["user"] = user[1]
            return redirect("/dashboard")
        else:
            return "Invalid email or password"

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user" in session:
        return render_template("dashboard.html")
    return redirect("/login")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

@app.route("/badge")
def badge():
    if "user" not in session:
        return redirect("/login")

    name = session["user"]

    filename = f"{name}_badge.pdf"
    filepath = os.path.join("static", filename)

    # Create PDF
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()

    content = []

    content.append(Paragraph("<b>Community Club</b>", styles["Title"]))
    content.append(Spacer(1, 20))

    content.append(Paragraph(f"Member Name: {name}", styles["Normal"]))
    content.append(Spacer(1, 10))

    content.append(Paragraph("Member since: 1999 Club", styles["Normal"]))
    content.append(Spacer(1, 20))

    content.append(Paragraph("This certifies membership in the club.", styles["Normal"]))

    doc.build(content)

    return send_file(filepath, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)