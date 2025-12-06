import sys
import os

# Добавляем путь к проекту
path = '/home/yourusername/mybot'
if path not in sys.path:
    sys.path.append(path)

# Импортируем Flask-приложение
from app import app

application = app
