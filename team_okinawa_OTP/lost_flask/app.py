from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import re
import hashlib

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# SQLite DB
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# アップロード設定
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -----------------
# モデル
# -----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    item_type = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    comments = db.relationship('Comment', backref='post', cascade='all, delete-orphan', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)

# -----------------
# フィルター nl2br
# -----------------
@app.template_filter('nl2br')
def nl2br_filter(s):
    return s.replace("\n", "<br>")

# -----------------
# ログイン必須チェックデコレータ
# -----------------
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "email" not in session:
            flash("ログインしてください", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# -----------------
# ルート
# -----------------
@app.route("/")
@login_required
def index():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template("index.html", posts=posts, username=session["username"])

# -----------------
# 投稿処理
# -----------------
@app.route("/post", methods=["POST"])
@login_required
def post():
    username = session["username"]
    item_type = request.form.get("item_type")
    location = request.form.get("location")
    content = request.form.get("content")
    image_file = request.files.get("image")

    filename = None
    if image_file and image_file.filename != "":
        filename = secure_filename(image_file.filename)
        image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    if username and item_type and location and content:
        new_post = Post(
            username=username,
            item_type=item_type,
            location=location,
            content=content,
            image_filename=filename
        )
        db.session.add(new_post)
        db.session.commit()
    return redirect(url_for("index"))

# -----------------
# コメント処理
# -----------------
@app.route("/post_comment/<int:post_id>", methods=["POST"])
@login_required
def post_comment(post_id):
    post_obj = Post.query.get_or_404(post_id)
    username = session["username"]
    content = request.form.get("content")
    if content:
        new_comment = Comment(post_id=post_obj.id, username=username, content=content)
        db.session.add(new_comment)
        db.session.commit()
    return redirect(url_for("index"))

# -----------------
# ログイン
# -----------------
@app.route("/login", methods=['GET', 'POST'])
def login():
    if "email" in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form['email']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session["email"] = user.email
            session["username"] = user.username
            flash('ログイン成功', 'success')
            return redirect(url_for('index'))
        else:
            flash('メールアドレスまたはパスワードが違います。', 'danger')
    return render_template('login.html')

# -----------------
# 新規登録
# -----------------
@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if not re.match(r'^e\d{6}@cs\.u-ryukyu\.ac\.jp$', email):
            flash('学内メールを使用してください。', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('ユーザー名がすでに使用されています。', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('メールアドレスがすでに登録されています。', 'danger')
            return redirect(url_for('register'))

        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        new_user = User(username=username, password=hashed_password, email=email)
        db.session.add(new_user)
        db.session.commit()
        flash('登録完了しました。ログインしてください。', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# -----------------
# ログアウト
# -----------------
@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("ログアウトしました", "success")
    return redirect(url_for("login"))

# -----------------
# DB作成
# -----------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

