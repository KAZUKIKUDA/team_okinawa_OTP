import os

class Config:
    """Flaskアプリケーションの設定を管理するクラス"""

    # --- 基本設定 ---
    # SECRET_KEYは必須。設定されていない場合はエラーを発生させます。
    try:
        SECRET_KEY = os.environ['SECRET_KEY']
    except KeyError:
        raise RuntimeError("環境変数 'SECRET_KEY' が設定されていません。")

    # --- データベース設定 ---
    SQLALCHEMY_DATABASE_URI = "sqlite:///posts.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- 画像アップロード設定 ---
    UPLOAD_FOLDER = 'static/uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # --- メール設定 ---
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True

    # ユーザー名とパスワードも必須。設定されていない場合はエラーを発生させます。
    try:
        MAIL_USERNAME = os.environ['MAIL_USERNAME']
        MAIL_PASSWORD = os.environ['MAIL_PASSWORD']
    except KeyError:
        raise RuntimeError("環境変数 'MAIL_USERNAME' または 'MAIL_PASSWORD' が設定されていません。")
    
    # メールの送信元として表示される名前とアドレス
    MAIL_DEFAULT_SENDER = ('忘れ物掲示板', MAIL_USERNAME)

