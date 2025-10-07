import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from datetime import datetime

# --- アプリケーションの初期設定 ---
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' # ログインしていないユーザーがアクセスしようとした場合のリダイレクト先
login_manager.login_message = "このページにアクセスするにはログインが必要です。"
login_manager.login_message_category = "info"

# URLSafeTimedSerializerのインスタンスを作成
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# --- データベースモデル定義 ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    confirmed = db.Column(db.Boolean, nullable=False, default=False) # メール認証済みフラグ
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), nullable=False)
    lost_area = db.Column(db.String(100), nullable=False)
    lost_place = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.now, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comments = db.relationship('Comment', backref='post', cascade='all, delete-orphan', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

# --- ヘルパー関数 ---

def allowed_file(filename):
    """アップロードされたファイルの拡張子が許可されているかチェック"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def send_confirmation_email(user_email):
    """確認メールを送信する関数"""
    token = s.dumps(user_email, salt='email-confirm-salt')
    confirm_url = url_for('confirm_email', token=token, _external=True)
    msg = Message('メールアドレスの確認', recipients=[user_email])
    msg.body = f'以下のリンクをクリックして、メールアドレスの確認を完了してください。\n\n{confirm_url}\n\nこのメールに心当たりがない場合は無視してください。'
    mail.send(msg)

# --- ルート定義 ---

@app.route('/')
def index():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template('index.html', posts=posts)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # ドメインチェック
        if not email.endswith('@cs.u-ryukyu.ac.jp'):
            flash('登録できるのは @cs.u-ryukyu.ac.jp のメールアドレスのみです。', 'danger')
            return redirect(url_for('register'))

        # 既存ユーザーチェック
        if User.query.filter_by(email=email).first():
            flash('このメールアドレスは既に使用されています。', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('このユーザー名は既に使用されています。', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        # 確認メールを送信
        send_confirmation_email(new_user.email)
        
        flash('確認メールを送信しました。メールを確認してアカウントを有効化してください。', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        # トークンを検証（有効期限は1時間）
        email = s.loads(token, salt='email-confirm-salt', max_age=3600)
    except SignatureExpired:
        flash('確認リンクの有効期限が切れています。再度登録してください。', 'danger')
        return redirect(url_for('register'))
    except BadTimeSignature:
        flash('無効な確認リンクです。', 'danger')
        return redirect(url_for('register'))
    
    user = User.query.filter_by(email=email).first_or_404()
    if user.confirmed:
        flash('このアカウントは既に有効化されています。', 'info')
    else:
        user.confirmed = True
        db.session.commit()
        flash('メールアドレスの確認が完了しました！ログインしてください。', 'success')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if user.confirmed:
                login_user(user)
                return redirect(url_for('index'))
            else:
                flash('アカウントが有効化されていません。確認メールをご確認ください。', 'warning')
        else:
            flash('メールアドレスまたはパスワードが正しくありません。', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ログアウトしました。', 'success')
    return redirect(url_for('index'))

@app.route('/post', methods=['POST'])
@login_required
def post():
    if not current_user.confirmed:
        flash('投稿するにはメールアドレスの確認が必要です。', 'warning')
        return redirect(url_for('index'))

    item_name = request.form.get('item_name')
    lost_area = request.form.get('lost_area')
    lost_place = request.form.get('lost_place')
    description = request.form.get('description')
    image_file = request.files.get('image')

    filename = None
    if image_file and allowed_file(image_file.filename):
        filename = secure_filename(image_file.filename)
        # ディレクトリが存在しない場合は作成
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    if item_name and lost_area and lost_place:
        new_post = Post(
            item_name=item_name, lost_area=lost_area, lost_place=lost_place,
            description=description, image_filename=filename, author=current_user
        )
        db.session.add(new_post)
        db.session.commit()
        flash('投稿が完了しました。', 'success')
    else:
        flash('必須項目を入力してください。', 'danger')

    return redirect(url_for('index'))

@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def post_comment(post_id):
    if not current_user.confirmed:
        flash('コメントするにはメールアドレスの確認が必要です。', 'warning')
        return redirect(url_for('index'))

    post_obj = Post.query.get_or_404(post_id)
    content = request.form.get('content')
    if content:
        new_comment = Comment(content=content, author=current_user, post=post_obj)
        db.session.add(new_comment)
        db.session.commit()
    return redirect(url_for('index'))

# --- アプリケーションの実行 ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

