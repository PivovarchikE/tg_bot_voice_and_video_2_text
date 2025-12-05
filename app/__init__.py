import os
from flask import Flask

from config import TOKEN

def create_app():
    app = Flask(__name__)

    if not TOKEN:
        raise ValueError("TOKEN не установлен config.py")

    app.config['SECRET_KEY'] = TOKEN

    from app.routes import bp
    app.register_blueprint(bp)

    return app