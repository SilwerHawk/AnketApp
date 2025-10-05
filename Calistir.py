from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
import psycopg2.extras
import re
import functools

app = Flask(__name__)
app.secret_key = "dev-secret"  # demo için; prod'da değiştirin

# --- PostgreSQL ayarları ---
DB_HOST = "localhost"
DB_NAME = "anketdb"
DB_USER = "admin1"
DB_PASS = "1991"

def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        cursor_factory=psycopg2.extras.DictCursor
    )

# --- E-posta doğrulama: @ ve .com zorunlu ---
EMAIL_REGEX = re.compile(r'^[^@\s]+@[^@\s]+\.com$', re.IGNORECASE)
def email_is_valid(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email or ""))

# --- Admin oturumu koruması ---
def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Lütfen önce giriş yapın.", "err")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

# ----------------- Rotalar -----------------

# Anasayfa: bağlantılar
@app.route("/ankesst")
def home():
    return render_template("home.html", title="Anasayfa")

# Anket formu
@app.route("/", methods=["GET", "POST"])
def anket():
    if request.method == "POST":
        full_name        = request.form.get("full_name", "").strip()
        email            = request.form.get("email", "").strip()
        hizmet_kalite    = request.form.get("hizmet_kalite", "")
        personel_ilgi    = request.form.get("personel_ilgi", "")
        fiyat_memnuniyet = request.form.get("fiyat_memnuniyet", "")
        tekrar_tercih    = request.form.get("tekrar_tercih", "")
        yorum            = request.form.get("yorum", "").strip()

        # Basit doğrulamalar
        if not full_name:
            flash("Lütfen 'Ad Soyad' alanını doldurun.", "err")
            return redirect(url_for("anket"))
        if not email_is_valid(email):
            flash('Geçersiz e-posta. "@" ve ".com" içermelidir.', "err")
            return redirect(url_for("anket"))

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO anketler
                        (full_name, email, hizmet_kalite, personel_ilgi, fiyat_memnuniyet, tekrar_tercih, yorum)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (full_name, email, hizmet_kalite, personel_ilgi, fiyat_memnuniyet, tekrar_tercih, yorum))
                    conn.commit()
            return redirect(url_for("sonuc"))
        except Exception as e:
            flash(f"Hata: {e}", "err")

    return render_template("anket.html", title="Hizmet Memnuniyeti Anketi")

# Teşekkür sayfası
@app.route("/sonuc")
def sonuc():
    return render_template("sonuc.html", title="Teşekkürler")

# --- Admin giriş/çıkış ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        kullanici = request.form.get("kullanici")
        sifre = request.form.get("sifre")
        if kullanici == "admin1" and sifre == "1991":
            session["is_admin"] = True
            session["admin_user"] = kullanici
            flash("Giriş başarılı.", "ok")
            return redirect(url_for("admin_panel"))
        else:
            flash("Hatalı kullanıcı adı veya şifre.", "err")
    return render_template("admin_login.html", title="Admin Girişi")

@app.route("/logout")
def logout():
    session.clear()
    flash("Çıkış yapıldı.", "ok")
    return redirect(url_for("home"))

# Admin paneli: kayıtları listele
@app.route("/admin")
@login_required
def admin_panel():
    rows = []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, full_name, email, hizmet_kalite, personel_ilgi,
                           fiyat_memnuniyet, tekrar_tercih, olusturulma
                    FROM anketler
                    ORDER BY id DESC
                """)
                rows = cur.fetchall()
    except Exception as e:
        flash(f"Listeleme hatası: {e}", "err")
    return render_template("admin_panel.html", rows=rows, title="Admin Paneli")

# İstatistikler
@app.route("/istatistik")
def istatistik():
    total = 0
    kalite = []
    tekrar = []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM anketler")
                total = cur.fetchone()[0]

                cur.execute("SELECT hizmet_kalite, COUNT(*) FROM anketler GROUP BY hizmet_kalite")
                kalite = cur.fetchall()

                cur.execute("SELECT tekrar_tercih, COUNT(*) FROM anketler GROUP BY tekrar_tercih")
                tekrar = cur.fetchall()
    except Exception as e:
        flash(f"İstatistik hatası: {e}", "err")

    def to_percent(rows):
        data = []
        for label, count in rows:
            pct = round((count / total) * 100, 2) if total else 0
            data.append({"label": label, "count": count, "percent": pct})
        return data

    return render_template(
        "istatistik.html",
        title="İstatistikler",
        total=total,
        kalite=to_percent(kalite),
        tekrar=to_percent(tekrar),
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
