from flask import Flask, render_template, request, redirect, session, send_file
import io, os, random, qrcode
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER
from werkzeug.utils import secure_filename

import secrets
print(secrets.token_hex(32))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# Detect environment
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- Database Connection ---
def get_db_connection():
    if DATABASE_URL:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    else:
        import sqlite3
        return sqlite3.connect("members.db")

# --- Placeholder helper ---
def placeholder():
    return "%s" if DATABASE_URL else "?"

# --- Init DB ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    if DATABASE_URL:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id SERIAL PRIMARY KEY,
                name TEXT,
                email TEXT UNIQUE,
                phone TEXT,
                interests TEXT,
                password TEXT,
                photo TEXT,
                member_id TEXT
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT UNIQUE,
                phone TEXT,
                interests TEXT,
                password TEXT,
                photo TEXT,
                member_id TEXT
            )
        """)

    conn.commit()
    cursor.close()
    conn.close()

init_db()

# --- Routes ---

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

        photo = request.files["photo"]
        filename = None

        if photo and photo.filename != "":
            filename = secure_filename(photo.filename)
            photo.save(os.path.join("static/images", filename))

        conn = get_db_connection()
        cursor = conn.cursor()

        query = f"""
            INSERT INTO members (name, email, phone, interests, password, photo)
            VALUES ({placeholder()}, {placeholder()}, {placeholder()}, {placeholder()}, {placeholder()}, {placeholder()})
        """
        try:
            cursor.execute(query, (name, email, phone, interests, hashed_password, filename))
            conn.commit()
        except Exception as e:
            conn.rollback()
            cursor.close()
            conn.close()
            return render_template("join.html", error="Email already exists")

        conn.commit()
        cursor.close()
        conn.close()

        return redirect(f"/success?name={name}")

    return render_template("join.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        query = f"SELECT * FROM members WHERE email = {placeholder()}"
        cursor.execute(query, (email,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user and check_password_hash(user[5], password):
            session["user"] = user[1]
            return redirect("/dashboard")
        else:
            return "Invalid email or password"

    return render_template("login.html")

@app.route("/success")
def success():
    name = request.args.get("name")
    return render_template("success.html", name=name)

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

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Correct query (SQLite version)
        cursor.execute(
            "SELECT * FROM members WHERE name = %s",
            (name,)
        )
        user = cursor.fetchone()

        if not user:
            return "User not found"

        # Safe access
        member_id = user["member_id"]

        # Generate only once
        if not member_id:
            initials = "".join([part[0].upper() for part in name.split()])
            random_number = random.randint(100000, 999999)
            member_id = f"{initials}-{random_number}"

            cursor.execute(
            "UPDATE members SET member_id = %s WHERE name = %s",
            (member_id, name)
            )
            conn.commit()

    except Exception as e:
        print("ERROR:", e)  # 👈 this will show exact issue in terminal
        return "Something went wrong (check server log)"

    finally:
        cursor.close()
        conn.close()

    # ---- PDF part (unchanged mostly) ----
    try:
        buffer = io.BytesIO()
        width = 85.6 * mm
        height = 54 * mm

        doc = SimpleDocTemplate(buffer, pagesize=(width, height),
                                rightMargin=5, leftMargin=5,
                                topMargin=5, bottomMargin=5)

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            name="title",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            textColor=colors.white,
            fontSize=10
        )

        text_style = ParagraphStyle(
            name="text",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=8
        )

        logo = Spacer(1,1)
        logo_path = os.path.join("static", "images", "logo.png")
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=25, height=25)

        photo = Spacer(1,1)
        if user["photo"]:
            photo_path = os.path.join("static/images", user["photo"])
            if os.path.exists(photo_path):
                photo = Image(photo_path, width=40, height=40)

        qr_data = f"{name} | ID: {member_id}"
        qr_img = qrcode.make(qr_data)

        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer)
        qr_buffer.seek(0)
        qr = Image(qr_buffer, width=35, height=35)

        empty = Spacer(1,1)

        card = Table([
            [logo, Paragraph("<b>Community Club</b>", title_style), qr],
            [empty, Paragraph("Est. 1999", text_style), empty],
            [photo, Paragraph(f"<b>{name}</b>", text_style), empty],
            [empty, Paragraph(f"<b>{member_id}</b>", text_style), empty],
        ], colWidths=[50, 100, 50])

        doc.build([card])
        buffer.seek(0)

        return send_file(buffer,
                         as_attachment=True,
                         download_name=f"{name}_badge.pdf",
                         mimetype="application/pdf")

    except Exception as e:
        print("PDF ERROR:", e)
        return "PDF generation failed"
        
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        print(request.form)
        return render_template("contact.html", success=True)
    return render_template("contact.html")

@app.route("/events")
def events():
    return render_template("events.html")

@app.route("/activities/reading")
def reading():
    return render_template("reading.html")

@app.route("/activities/art")
def art():
    return render_template("art.html")

@app.route("/activities/stories")
def stories():
    return render_template("stories.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
