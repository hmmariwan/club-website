from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3, io, os, random, qrcode
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
#print(secrets.token_hex(16))
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "385587ae2ea5563e8bfc5d51adc0e0d2" 

conn = sqlite3.connect("members.db")
cursor = conn.cursor()

conn.commit()
conn.close()

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

        photo = request.files["photo"]

        filename = None
        if photo and photo.filename != "":
            filename = secure_filename(photo.filename)
            photo.save(os.path.join("static/images", filename))

        conn = sqlite3.connect("members.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO members (name, email, phone, interests, password, photo) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, phone, interests, hashed_password, filename)
        )
        conn.commit()
        conn.close()

        return redirect(f"/success?name={name}")

    return render_template("join.html")

@app.route("/events")
def events():
    return render_template("events.html")

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

    # --- Get user ---
    conn = sqlite3.connect("members.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM members WHERE name = ?", (name,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return "User not found"

    # ✅ Create initials + 6-digit ID
    initials = "".join([part[0].upper() for part in name.split()])
    random_number = random.randint(100000, 999999)
    member_id = f"{initials}-{random_number}"

    # --- PDF setup ---
    buffer = io.BytesIO()
    width = 85.6 * mm
    height = 54 * mm

    doc = SimpleDocTemplate(buffer, pagesize=(width, height),
                            rightMargin=5, leftMargin=5,
                            topMargin=5, bottomMargin=5)

    styles = getSampleStyleSheet()

    # Custom styles
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

    # --- Logo ---
    logo_path = os.path.join("static", "images", "logo.png")
    logo = Image(logo_path, width=25, height=25) if os.path.exists(logo_path) else Spacer(1,1)

    # --- Photo ---
    photo_filename = user[6]
    if photo_filename:
        photo_path = os.path.join("static/images", photo_filename)
        photo = Image(photo_path, width=40, height=40) if os.path.exists(photo_path) else Spacer(1,1)
    else:
        photo = Spacer(1,1)

    # --- QR ---
    qr_data = f"{name} | ID: {member_id}"
    qr_img = qrcode.make(qr_data)

    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer)
    qr_buffer.seek(0)
    qr = Image(qr_buffer, width=35, height=35)

    empty = Spacer(1,1)

    # --- Layout ---
    card = Table([
        [logo, Paragraph("<b>Community Club</b>", title_style), qr],
        [empty, Paragraph("Est. 1999", text_style), empty],
        [photo, Paragraph(f"<b>{name}</b>", text_style), empty],
        [empty, Paragraph(f"<b>{member_id}</b>", text_style), empty],
    ], colWidths=[50, 100, 50])

    # 🎨 COLORFUL STYLE
    card.setStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),   # dark top
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#ecf0f1")),  # light body
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 2, colors.HexColor("#1abc9c")),

        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])

    doc.build([card])

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{name}_badge.pdf",
        mimetype="application/pdf"
    )

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]

        # For now, just print (later we can email or store it)
        print(name, email, message)

        return render_template("contact.html", success=True)

    return render_template("contact.html")

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