import os
import sys

# Добавляем путь к проекту
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.insert(0, path)

# Импортируем Flask приложение
from app import create_app
from config import TOKEN

# Инициализируем приложение
application = create_app()  # Важно: переменная должна называться 'application'

# Инициализируем бота при запуске
with application.app_context():
    from app.bot import init_bot, setup_handlers
    import telebot

    # Получаем токен из переменных окружения PythonAnywhere
    token = TOKEN

    if token:
        # Инициализируем и настраиваем бота
        bot = init_bot(TOKEN)
        setup_handlers(bot)
        print("✅ Бот инициализирован")

        # Проверяем вебхук
        webhook_info = bot.get_webhook_info()
        if not webhook_info.url:
            print(
                "⚠️ Вебхук не установлен. Перейдите на /set-webhook для установки")
        else:
            print(f"✅ Вебхук установлен: {webhook_info.url}")
    else:
        print("❌ TELEGRAM_TOKEN не найден в переменных окружения")
        print(
            "Добавьте его в PythonAnywhere: Web app → Consoles → Bash console")
        print("И выполните: export TELEGRAM_TOKEN='ваш_токен'")
