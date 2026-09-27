from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import date, timedelta
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# データベースを作る
def init_db():
    conn = sqlite3.connect("database.db")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS pops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pop_name TEXT NOT NULL,
            barcode TEXT NOT NULL,
            location TEXT NOT NULL,
            expire_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            image_path TEXT
        )
    """)

    try:
        conn.execute("ALTER TABLE pops ADD COLUMN image_path TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


@app.route("/")
def index():
    return render_template("home.html")


# POP一覧
@app.route("/list")
def pop_list():

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    today = date.today().isoformat()

    pops = conn.execute("""
        SELECT *,
            CASE
                WHEN expire_date = ? THEN 1
                WHEN expire_date < ? THEN 2
                WHEN expire_date = date(?, '+1 day') THEN 3
                ELSE 4
            END AS priority
        FROM pops
        ORDER BY priority, location, expire_date
    """, (today, today, today)).fetchall()

    conn.close()

    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    return render_template(
        "list.html",
        pops=pops,
        today=today,
        tomorrow=tomorrow
    )


# 撤去確認
@app.route("/remove/check", methods=["POST"])
def remove_check():

    barcode = request.form["barcode"]

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    pop = conn.execute("""
        SELECT *
        FROM pops
        WHERE barcode = ? AND status = 'active'
    """, (barcode,)).fetchone()

    conn.close()

    if pop is None:
        return """
        <h1>❌ エラー</h1>
        <p>登録されているPOPと一致しません。</p>
        <a href="/remove">撤去確認に戻る</a>
        """

    return render_template(
        "remove_confirm.html",
        pop=pop
    )


# 撤去完了
@app.route("/remove/confirm/<int:pop_id>", methods=["POST"])
def remove_confirm(pop_id):

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    pop = conn.execute("""
        SELECT *
        FROM pops
        WHERE id = ?
    """, (pop_id,)).fetchone()

    if pop is None:
        conn.close()
        return "POPが見つかりません。"

    conn.execute("""
        UPDATE pops
        SET status = 'removed'
        WHERE id = ?
    """, (pop_id,))

    conn.commit()
    conn.close()

    return render_template(
        "remove_complete.html",
        pop=pop
    )


# 古い手動撤去用
@app.route("/remove/<int:pop_id>", methods=["POST"])
def remove_pop(pop_id):

    conn = sqlite3.connect("database.db")

    conn.execute("""
        UPDATE pops
        SET status = 'removed'
        WHERE id = ?
    """, (pop_id,))

    conn.commit()
    conn.close()

    return redirect("/list")


# POP登録
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        pop_name = request.form["pop_name"]
        barcode = request.form["barcode"]
        location = request.form["location"]
        expire_date = request.form["expire_date"]

        image = request.files.get("image")

        image_path = ""

        if image and image.filename:

            os.makedirs(
                app.config["UPLOAD_FOLDER"],
                exist_ok=True
            )

            filename = secure_filename(image.filename)

            image_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            image.save(image_path)

        conn = sqlite3.connect("database.db")

        conn.execute("""
            INSERT INTO pops
            (pop_name, barcode, location, expire_date, image_path)
            VALUES (?, ?, ?, ?, ?)
        """, (
            pop_name,
            barcode,
            location,
            expire_date,
            image_path
        ))

        conn.commit()
        conn.close()

        return """
        <h1>POPを登録しました！</h1>
        <p><a href="/">ホームに戻る</a></p>
        <p><a href="/register">続けてPOPを登録する</a></p>
        <p><a href="/list">POP一覧を見る</a></p>
        """

    return render_template("register.html")


# POP編集
@app.route("/edit/<int:pop_id>", methods=["GET", "POST"])
def edit(pop_id):

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    pop = conn.execute(
        "SELECT * FROM pops WHERE id = ?",
        (pop_id,)
    ).fetchone()

    if pop is None:
        conn.close()
        return "POPが見つかりません"

    if request.method == "POST":

        pop_name = request.form["pop_name"]
        barcode = request.form["barcode"]
        location = request.form["location"]
        expire_date = request.form["expire_date"]

        conn.execute("""
            UPDATE pops
            SET pop_name = ?,
                barcode = ?,
                location = ?,
                expire_date = ?
            WHERE id = ?
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


# POP削除
@app.route("/delete/<int:pop_id>", methods=["GET", "POST"])
def delete(pop_id):

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    pop = conn.execute(
        "SELECT * FROM pops WHERE id = ?",
        (pop_id,)
    ).fetchone()

    if pop is None:
        conn.close()
        return "POPが見つかりません"

    if request.method == "POST":

        conn.execute(
            "DELETE FROM pops WHERE id = ?",
            (pop_id,)
        )

        conn.commit()
        conn.close()

        return redirect("/list")

    conn.close()

    return render_template("delete.html", pop=pop)


# 撤去済みPOP一括削除
@app.route("/delete_removed", methods=["POST"])
def delete_removed():

    conn = sqlite3.connect("database.db")

    conn.execute("""
        DELETE FROM pops
        WHERE status = 'removed'
    """)

    conn.commit()
    conn.close()

    return redirect("/list")


# 撤去済みPOP一括削除確認
@app.route("/delete_removed/confirm", methods=["GET", "POST"])
def delete_removed_confirm():

    if request.method == "POST":

        conn = sqlite3.connect("database.db")

        conn.execute("""
            DELETE FROM pops
            WHERE status = 'removed'
        """)

        conn.commit()
        conn.close()

        return redirect("/list")

    return render_template("delete_removed.html")


# 撤去画面
@app.route("/remove")
def remove():
    return render_template("remove.html")


# データベース初期化
init_db()


app.run(
    host="0.0.0.0",
    port=5000,
    debug=True
)