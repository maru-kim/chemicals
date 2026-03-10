import os
import uuid
from werkzeug.utils import secure_filename

from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import openpyxl
from flask import flash

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = "your_secret_key"

ADMIN_PASSWORD = "1111"   # 관리자 비밀번호


# -------------------------
# DB 연결
# -------------------------
def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------
# DB 초기화
# -------------------------
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chemicals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        korean_name TEXT,
        english_name TEXT,
        formula TEXT,
        location TEXT,
        description TEXT,
        CAS_number TEXT,
        image TEXT
    )
    """)

    conn.commit()
    conn.close()


# -------------------------
# 🔎 검색 페이지
# -------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    results = []

    if request.method == "POST":
        keyword = request.form["keyword"]

        conn = get_db_connection()
        results = conn.execute("""
            SELECT * FROM chemicals
            WHERE korean_name LIKE ?
            OR english_name LIKE ?
            OR formula LIKE ?
            OR description LIKE ?
            OR CAS_number LIKE ?
        """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")).fetchall()
        conn.close()

    return render_template("index.html", results=results)

# -------------------------
# 🔐 관리자 로그인
# -------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():


    if request.method == "POST":
        password = request.form["password"]

        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))

    return render_template("admin_login.html")


# -------------------------
# 관리자 대시보드
# -------------------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    chemicals = conn.execute("SELECT * FROM chemicals").fetchall()
    conn.close()

    return render_template("admin_dashboard.html", chemicals=chemicals)


# -------------------------
# 약품 추가
# -------------------------
@app.route("/admin/add", methods=["POST"])
def add_chemical():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    

    korean_name = request.form["korean_name"]
    english_name = request.form["english_name"]
    formula = request.form["formula"]
    location = request.form["location"]
    description = request.form.get("description")
    CAS_number = request.form.get("CAS_number")

    file = request.files.get("image")
    print("file:", file, "filename:", file.filename if file else None)
    filename = None

    if file and file.filename != "":
        filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        print("Saved filename in add:", filename)

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO chemicals (korean_name, english_name, formula, location, description, CAS_number, image)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (korean_name, english_name, formula, location, description, CAS_number, filename))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


#--------------------------
# 약품 엑셀 업로드
#--------------------------
@app.route("/admin/upload_excel", methods=["POST"])
def upload_excel():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    file = request.files["file"]

    if not file:
        return redirect(url_for("admin_dashboard"))

    workbook = openpyxl.load_workbook(file)
    sheet = workbook.active

    conn = get_db_connection()

    for row in sheet.iter_rows(min_row=2, values_only=True):
        korean_name, english_name, formula, location, description, CAS_number = row

        conn.execute("""
            INSERT INTO chemicals (korean_name, english_name, formula, location, description, CAS_number)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (korean_name, english_name, formula, location, description, CAS_number))

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))



# -------------------------
# 약품 삭제
# -------------------------
@app.route("/admin/delete_chemical/<int:id>", methods=["POST"])
def delete_chemical(id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    conn.execute("DELETE FROM chemicals WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


# -------------------------
# 약품 수정
# -------------------------
@app.route("/admin/update/<int:id>", methods=["POST"])
def update_inline(id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    korean_name = request.form["korean_name"]
    english_name = request.form["english_name"]
    formula = request.form["formula"]
    location = request.form["location"]
    description = request.form.get("description")
    CAS_number = request.form.get("CAS_number")

    file = request.files.get("image")
    print("file:", file, "filename:", file.filename if file else None)
    filename = None

    if file and file.filename != "":
        filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        print("Saved filename in update:", filename)

    conn = get_db_connection()

    # 기존 image 가져오기
    existing_image = conn.execute("SELECT image FROM chemicals WHERE id = ?", (id,)).fetchone()
    existing_image = existing_image['image'] if existing_image else None

    if filename:
        # 기존 파일 삭제
        if existing_image:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], existing_image))
                print("Deleted existing image:", existing_image)
            except OSError as e:
                print("Error deleting file:", e)
        conn.execute("""
            UPDATE chemicals
            SET korean_name = ?, english_name = ?, formula = ?, location = ?, description = ?, CAS_number = ?, image = ?
            WHERE id = ?
            """, (korean_name, english_name, formula, location, description, CAS_number, filename, id))
    else:
        conn.execute("""
            UPDATE chemicals
            SET korean_name = ?, english_name = ?, formula = ?, location = ?, description = ?, CAS_number = ?
            WHERE id = ?
            """, (korean_name, english_name, formula, location, description, CAS_number, id))

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))



# -------------------------
# 약품 중복 제거
# -------------------------
@app.route("/admin/remove_duplicates")
def remove_duplicates():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    conn.execute("""
        DELETE FROM chemicals
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM chemicals
            GROUP BY korean_name, english_name, formula, location, description, CAS_number
        )
    """)

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


# -------------------------
# 로그아웃
# -------------------------
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))


# -------------------------
# 실행
# -------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
