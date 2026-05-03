from flask import Flask, render_template, request, redirect, url_for, send_file, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import io, os, qrcode, secrets, random, psycopg2, re
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")

# ---------------- LOGIN SETUP ----------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ---------------- DB ----------------
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# ---------------- USER MODEL ----------------
class User(UserMixin):
    def __init__(self, data):
        self.id = data["id"]
        self.name = data["name"]
        self.email = data["email"]
        self.role = data["role"]

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM members WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return User(user) if user else None

# ---------------- NO CACHE ----------------
@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ---------------- INIT DB ----------------
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id SERIAL PRIMARY KEY,
            name TEXT,
            email TEXT UNIQUE,
            phone TEXT,
            interests TEXT,
            password TEXT,
            photo TEXT,
            member_id TEXT UNIQUE,
            role TEXT DEFAULT 'user'
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()

init_db()
os.makedirs("static/images", exist_ok=True)

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")

# ---------------- REGISTER ----------------
@app.route("/join", methods=["GET", "POST"])
def join():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        interests = request.form["interests"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM members WHERE email=%s", (email,))
        if cursor.fetchone():
            return render_template("join.html", error="Email already registered")

        hashed = generate_password_hash(password)

        # ✅ CLEAN INITIALS LOGIC
        parts = name.strip().split()
        first_initial = parts[0][0].upper() if parts else "X"
        last_initial = parts[-1][0].upper() if len(parts) > 1 else "X"
        initials = first_initial + last_initial  # e.g. JD

        # ✅ GENERATE UNIQUE INITIALS + 6 DIGITS
        while True:
            number = random.randint(100000, 999999)  # always 6 digits
            member_id = f"{initials}{number}"

            cursor.execute(
                "SELECT id FROM members WHERE member_id = %s",
                (member_id,)
            )
            if not cursor.fetchone():
                break

        role = "admin" if email == ADMIN_EMAIL else "user"

        photo = request.files.get("photo")
        filename = None

        if photo and photo.filename:
            filename = secure_filename(photo.filename)
            photo.save(os.path.join("static/images", filename))

        cursor.execute("""
            INSERT INTO members (name,email,phone,interests,password,photo,member_id,role)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (name, email, phone, interests, hashed, filename, member_id, role))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for("login"), code=303)

    return render_template("join.html")
# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin" if current_user.role == "admin" else "dashboard"), code=303)

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM members WHERE email=%s", (email,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()

        if user_data and check_password_hash(user_data["password"], password):
            login_user(User(user_data))
            return redirect(url_for("admin" if user_data["role"] == "admin" else "dashboard"), code=303)

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != "user":
        return redirect(url_for("admin"), code=303)

    return render_template("dashboard.html", user=current_user)

# ---------------- ADMIN ----------------
@app.route("/admin")
@login_required
def admin():
    if current_user.role != "admin":
        abort(403)

    search = request.args.get("search", "")

    conn = get_db_connection()
    cursor = conn.cursor()

    if search:
        cursor.execute("""
            SELECT id,name,email,phone,interests,member_id,role
            FROM members
            WHERE name ILIKE %s OR email ILIKE %s
        """, (f"%{search}%", f"%{search}%"))
    else:
        cursor.execute("""
            SELECT id,name,email,phone,interests,member_id,role
            FROM members
        """)

    members = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin.html", members=members, search=search)

# ---------------- DELETE USER (FIXED) ----------------
@app.route("/admin/delete/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if current_user.role != "admin":
        abort(403)

    # Prevent admin from deleting themselves
    if user_id == current_user.id:
        return redirect(url_for("admin"), code=303)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get photo before deleting
    cursor.execute("SELECT photo FROM members WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    if user:
        # Delete image file if exists
        if user["photo"]:
            photo_path = os.path.join("static/images", user["photo"])
            if os.path.exists(photo_path):
                os.remove(photo_path)

        cursor.execute("DELETE FROM members WHERE id=%s", (user_id,))
        conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("admin"), code=303)

# ---------------- LOGOUT ----------------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"), code=303)

# ---------------- BADGE ----------------
@app.route("/badge")
@login_required
def badge():
    user_id = current_user.id

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM members WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        return "User not found"

    name = user["name"]
    member_id = user["member_id"]

    # ✅ VALID FORMAT CHECK: 2 letters + 6 digits
    valid_format = bool(re.match(r"^[A-Z]{2}\d{6}$", member_id or ""))

    # ✅ FIX OR GENERATE IF INVALID
    if not valid_format:

        parts = name.strip().split()
        first_initial = parts[0][0].upper() if parts else "X"
        last_initial = parts[-1][0].upper() if len(parts) > 1 else "X"
        initials = first_initial + last_initial

        while True:
            number = random.randint(100000, 999999)
            new_id = f"{initials}{number}"

            cursor.execute(
                "SELECT id FROM members WHERE member_id = %s",
                (new_id,)
            )
            if not cursor.fetchone():
                member_id = new_id
                break

        cursor.execute(
            "UPDATE members SET member_id = %s WHERE id = %s",
            (member_id, user_id)
        )
        conn.commit()

    cursor.close()
    conn.close()

    # ---------------- PDF SETUP ----------------
    buffer = io.BytesIO()
    width = 85.6 * mm
    height = 54 * mm

    doc = SimpleDocTemplate(
        buffer,
        pagesize=(width, height),
        rightMargin=5,
        leftMargin=5,
        topMargin=5,
        bottomMargin=5
    )

    # ---------------- STYLES ----------------
    title_style = ParagraphStyle(
        name="title",
        fontSize=10,
        textColor=colors.white,
        alignment=TA_LEFT
    )

    name_style = ParagraphStyle(
        name="name",
        fontSize=10,
        alignment=TA_LEFT,
        spaceAfter=4
    )

    id_style = ParagraphStyle(
        name="id",
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_LEFT
    )

    # ---------------- LOGO ----------------
    logo_path = os.path.join("static", "images", "logo.png")
    logo = Spacer(1, 1)

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=20, height=20)

    # ---------------- PHOTO ----------------
    photo = Spacer(1, 1)

    if user["photo"]:
        photo_path = os.path.join("static/images", user["photo"])
        if os.path.exists(photo_path):
            photo = Image(photo_path, width=45, height=45)

    # ---------------- QR CODE ----------------
    qr_data = f"{name} | ID: {member_id}"
    qr_img = qrcode.make(qr_data)

    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer)
    qr_buffer.seek(0)

    qr = Image(qr_buffer, width=35, height=35)

    # ---------------- HEADER ----------------
    header = Table([
        [logo, Paragraph("<b>Community Club</b>", title_style)]
    ], colWidths=[30, 140])

    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2c3e50")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))

    # ---------------- BODY ----------------
    body = Table([
        [photo,
         Paragraph(f"<b>{name}</b>", name_style),
         qr],
        ["",
         Paragraph(f"ID: {member_id}", id_style),
         ""]
    ], colWidths=[55, 90, 45])

    body.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))

    # ---------------- CARD ----------------
    card = Table([
        [header],
        [body]
    ], colWidths=[190])

    card.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
    ]))

    doc.build([card])
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{name}_badge.pdf",
        mimetype="application/pdf"
    )
# ---------------- STATIC ----------------
@app.route("/contact")
def contact():
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

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)