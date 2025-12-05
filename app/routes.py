from flask import Blueprint, request, jsonify, current_app
import telebot
import logging


bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)


# Импортируем бота
from app.bot import bot


@bp.route('/')
def home():
    """Главная страница"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 Голосовой бот на PythonAnywhere</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: white;
            }
            .card {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 40px;
                color: #333;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            h1 {
                color: #667eea;
                margin-top: 0;
            }
            .status {
                padding: 15px;
                border-radius: 10px;
                margin: 20px 0;
                background: #d4edda;
                color: #155724;
                border-left: 5px solid #28a745;
            }
            .btn {
                display: inline-block;
                padding: 12px 24px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 50px;
                margin: 10px 5px;
                transition: transform 0.3s, background 0.3s;
            }
            .btn:hover {
                background: #764ba2;
                transform: translateY(-2px);
            }
            .code {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 10px;
                font-family: monospace;
                overflow-x: auto;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🤖 Голосовой Telegram бот</h1>
            <p>Бот работает на PythonAnywhere и преобразует голосовые сообщения в текст</p>

            <div class="status">
                ✅ <strong>Статус:</strong> Бот активен и готов к работе!
            </div>

            <h3>🔧 Управление вебхуком:</h3>
            <p>
                <a href="/set-webhook" class="btn">Установить вебхук</a>
                <a href="/remove-webhook" class="btn">Удалить вебхук</a>
                <a href="/webhook-info" class="btn">Информация</a>
                <a href="/health" class="btn">Проверка</a>
            </p>

            <h3>📱 Как использовать:</h3>
            <ol>
                <li>Найдите бота в Telegram</li>
                <li>Отправьте команду <code>/start</code></li>
                <li>Отправьте голосовое сообщение</li>
                <li>Получите распознанный текст</li>
            </ol>

            <h3>📊 Информация о сервере:</h3>
            <div class="code">
                PythonAnywhere<br>
                HTTPS: Да<br>
                Webhook URL: https://ВАШ_USERNAME.pythonanywhere.com/webhook
            </div>

            <p style="margin-top: 30px; font-size: 0.9em; color: #666;">
                Хостинг: PythonAnywhere | Статус: <span style="color: green;">●</span> Online
            </p>
        </div>
    </body>
    </html>
    '''


@bp.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint для получения обновлений от Telegram"""
    if request.headers.get('content-type') == 'application/json':
        try:
            # Получаем обновление
            update = telebot.types.Update.de_json(
                request.get_data().decode('utf-8'))

            # Обрабатываем обновление
            bot.process_new_updates([update])

            logger.info(f"Webhook processed update_id: {update.update_id}")
            return jsonify({"status": "ok"}), 200

        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "Invalid content type"}), 403


@bp.route('/set-webhook', methods=['GET'])
def set_webhook():
    """Устанавливает вебхук на PythonAnywhere"""
    try:
        from flask import current_app

        # Получаем токен из переменных окружения PythonAnywhere
        token = current_app.config.get('TELEGRAM_TOKEN')
        if not token:
            token = os.environ.get('TELEGRAM_TOKEN')

        if not token:
            return "❌ TELEGRAM_TOKEN не установлен. Добавьте его в переменные окружения PythonAnywhere.", 400

        # Формируем URL вебхука
        username = os.environ.get('USER', 'ваш_username')
        webhook_url = f"https://{username}.pythonanywhere.com/webhook"

        # Устанавливаем вебхук
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)

        return f'''
        <div style="padding: 20px; background: #d4edda; border-radius: 10px;">
            <h2 style="color: #155724;">✅ Вебхук успешно установлен!</h2>
            <p><strong>URL:</strong> {webhook_url}</p>
            <p><strong>Статус:</strong> Бот готов принимать сообщения</p>
            <a href="/" style="display: inline-block; padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; margin-top: 15px;">
                На главную
            </a>
        </div>
        '''

    except Exception as e:
        return f'''
        <div style="padding: 20px; background: #f8d7da; border-radius: 10px;">
            <h2 style="color: #721c24;">❌ Ошибка установки вебхука</h2>
            <p><strong>Ошибка:</strong> {str(e)}</p>
            <a href="/" style="display: inline-block; padding: 10px 20px; background: #dc3545; color: white; text-decoration: none; border-radius: 5px; margin-top: 15px;">
                На главную
            </a>
        </div>
        ''', 500


@bp.route('/remove-webhook', methods=['GET'])
def remove_webhook():
    """Удаляет вебхук"""
    try:
        bot.remove_webhook()
        return '''
        <div style="padding: 20px; background: #fff3cd; border-radius: 10px;">
            <h2 style="color: #856404;">⚠️ Вебхук удален</h2>
            <p>Бот больше не будет получать сообщения через вебхук.</p>
            <a href="/set-webhook" style="display: inline-block; padding: 10px 20px; background: #ffc107; color: black; text-decoration: none; border-radius: 5px; margin-top: 15px;">
                Установить снова
            </a>
        </div>
        '''
    except Exception as e:
        return f'Ошибка: {str(e)}', 500


@bp.route('/webhook-info', methods=['GET'])
def webhook_info():
    """Показывает информацию о вебхуке"""
    try:
        info = bot.get_webhook_info()
        return f'''
        <div style="padding: 20px; background: #e2e3e5; border-radius: 10px;">
            <h2>📊 Информация о вебхуке</h2>
            <pre style="background: white; padding: 15px; border-radius: 5px; overflow-x: auto;">
URL: {info.url or "Не установлен"}
Pending updates: {info.pending_update_count}
Last error: {info.last_error_message or "Нет"}
Last error date: {info.last_error_date or "Нет"}
Max connections: {info.max_connections}
            </pre>
            <a href="/" style="display: inline-block; padding: 10px 20px; background: #6c757d; color: white; text-decoration: none; border-radius: 5px; margin-top: 15px;">
                На главную
            </a>
        </div>
        '''
    except Exception as e:
        return f'Ошибка: {str(e)}', 500


@bp.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья приложения"""
    return jsonify({
        "status": "healthy",
        "service": "telegram-voice-bot",
        "platform": "PythonAnywhere",
        "webhook_enabled": True if bot.get_webhook_info().url else False
    }), 200
