import sys
import os

# Добавляем путь к проекту
path = '/home/PivovarchikE/tg_bot_voice_and_video_2_text'
if path not in sys.path:
    sys.path.insert(0, path)  # используем insert вместо append

# Настраиваем логирование
import logging
logging.basicConfig(level=logging.INFO)

# Импортируем Flask-приложение
from app import app

# Переименовываем для WSGI
application = app

# Логируем успешную загрузку
print("✅ WSGI приложение загружено")
print(f"📁 Путь: {path}")
