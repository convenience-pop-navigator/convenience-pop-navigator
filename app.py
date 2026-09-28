from flask import Flask, render_template, request, redirect
from datetime import date, timedelta
import os
import psycopg
import cloudinary
import cloudinary.uploader
from psycopg.rows import dict_row

app = Flask(__name__)

# ==========================================
# Cloudinary設定
# ==========================================
cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"]
)


# ==========================================
# Neon PostgreSQLへの接続
# ==========================================
def get_db_connection():
    return psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row
    )


# ==========================================
# データベース初期化
# ==========================================
def init_db():
    conn = get_db_connection()

    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pops (
                id SERIAL PRIMARY KEY,
                pop_name TEXT NOT NULL,
                barcode TEXT NOT NULL,
                location TEXT NOT NULL,
                expire_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                image_path TEXT
            )
        """)

    conn.commit()
    conn.close()


# ==========================================
# ホーム
# ==========================================
@app.route("/")
def index():
    return render_template("home.html")


# ==========================================
# POP一覧
# ==========================================
@app.route("/list")
def pop_list():
    conn = get_db_connection()

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT *,
                CASE
                    WHEN expire_date = %s THEN 1
                    WHEN expire_date < %s THEN 2
                    WHEN expire_date = %s THEN 3
                    ELSE 4
                END AS priority
            FROM pops
            ORDER BY priority, location, expire_date
        """, (today, today, tomorrow))

        pops = cur.fetchall()

    conn.close()

    return render_template(
        "list.html",
        pops=pops,
        today=today,
        tomorrow=tomorrow
    )


# ==========================================
# 撤去確認
# ==========================================
@app.route("/remove/check", methods=["POST"])
def remove_check():
    barcode = request.form["barcode"]

    conn = get_db_connection()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT *
            FROM pops
            WHERE barcode = %s
            AND status = 'active'
        """, (barcode,))

        pop = cur.fetchone()

    conn.close()

    if pop is None:
        return """
        <h1>❌ エラー</h1>
        <p>登録されているPOPと一致しません。</p>
        <a href="/remove">撤去確認に戻る</a>
        """

    return render_template("remove_confirm.html", pop=pop)


# ==========================================
# 撤去完了
# ==========================================
@app.route("/remove/confirm/<int:pop_id>", methods=["POST"])
def remove_confirm(pop_id):
    conn = get_db_connection()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM pops WHERE id = %s",
            (pop_id,)
        )

        pop = cur.fetchone()

        if pop is None:
            conn.close()
            return "POPが見つかりません。"

        cur.execute(
            "UPDATE pops SET status = 'removed' WHERE id = %s",
            (pop_id,)
        )

    conn.commit()
    conn.close()

    return render_template("remove_complete.html", pop=pop)


# ==========================================
# 一覧から撤去
# ==========================================
@app.route("/remove/<int:pop_id>", methods=["POST"])
def remove_pop(pop_id):
    conn = get_db_connection()

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE pops SET status = 'removed' WHERE id = %s",
            (pop_id,)
        )

    conn.commit()
    conn.close()

    return redirect("/list")


# ==========================================
# POP登録
# ==========================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        pop_name = request.form["pop_name"]
        barcode = request.form["barcode"]
        location = request.form["location"]
        expire_date = request.form["expire_date"]

        # ------------------------------------------
        # Cloudinaryへ画像アップロード
        # ------------------------------------------
        image = request.files.get("image")

        image_path = ""

        if image and image.filename:
            upload_result = cloudinary.uploader.upload(
                image,
                folder="convenience_pop_navigator"
            )

            image_path = upload_result["secure_url"]

        # ------------------------------------------
        # Neon PostgreSQLへ登録
        # ------------------------------------------
        conn = get_db_connection()

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pops
                (pop_name, barcode, location, expire_date, image_path)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                pop_name,
                barcode,
                location,
                expire_date,
                image_path
            ))

        conn.commit()
        conn.close()

        return render_template("register_complete.html")

    return render_template("register.html")


# ==========================================
# POP編集
# ==========================================
@app.route("/edit/<int:pop_id>", methods=["GET", "POST"])
def edit(pop_id):
    conn = get_db_connection()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM pops WHERE id = %s",
            (pop_id,)
        )

        pop = cur.fetchone()

        if pop is None:
            conn.close()
            return "POPが見つかりません"

        if request.method == "POST":

            pop_name = request.form["pop_name"]
            barcode = request.form["barcode"]
            location = request.form["location"]
            expire_date = request.form["expire_date"]

            cur.execute("""
                UPDATE pops
                SET pop_name = %s,
                    barcode = %s,
                    location = %s,
                    expire_date = %s
                WHERE id = %s
            """, (
                pop_name,
                barcode,
                location,
                expire_date,
                pop_id
            ))

            conn.commit()
            conn.close()

            return redirect("/list")

    conn.close()

    return render_template("edit.html", pop=pop)


# ==========================================
# POP削除
# ==========================================
@app.route("/delete/<int:pop_id>", methods=["GET", "POST"])
def delete(pop_id):
    conn = get_db_connection()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM pops WHERE id = %s",
            (pop_id,)
        )

        pop = cur.fetchone()

        if pop is None:
            conn.close()
            return "POPが見つかりません"

        if request.method == "POST":

            cur.execute(
                "DELETE FROM pops WHERE id = %s",
                (pop_id,)
            )

            conn.commit()
            conn.close()

            return redirect("/list")

    conn.close()

    return render_template("delete.html", pop=pop)


# ==========================================
# 撤去済みPOPを一括削除
# ==========================================
@app.route("/delete_removed", methods=["POST"])
def delete_removed():
    conn = get_db_connection()

    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM pops WHERE status = 'removed'"
        )

    conn.commit()
    conn.close()

    return redirect("/list")


# ==========================================
# 撤去済みPOP削除確認
# ==========================================
@app.route("/delete_removed/confirm", methods=["GET", "POST"])
def delete_removed_confirm():

    if request.method == "POST":

        conn = get_db_connection()

        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM pops WHERE status = 'removed'"
            )

        conn.commit()
        conn.close()

        return redirect("/list")

    return render_template("delete_removed.html")


# ==========================================
# 撤去画面
# ==========================================
@app.route("/remove")
def remove():
    return render_template("remove.html")


# ==========================================
# アプリ起動時にNeonのテーブルを作成
# ==========================================
init_db()


# ==========================================
# ローカル起動
# ==========================================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )