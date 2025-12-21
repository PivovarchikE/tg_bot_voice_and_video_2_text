import telebot
from flask import Flask, request, jsonify
import logging
import sys
import json
from telebot import types

from config import TOKEN, WEBHOOK_URL
from .converting import recognize_speech_chunked, download_file

# Настройка логирования
logging.basicConfig(
    # level=logging.DEBUG, # подробное логирование
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

app.logger.info(f"🚀 Бот запущен")
app.logger.info(f"Вебхук: {WEBHOOK_URL}")

# Обработчик команд
def handle_start(message):
    """Обработчик команды /start"""
    app.logger.info(f"🔥 РУЧНОЙ обработчик /start для {message.chat.id}")
    try:
        bot.send_message(message.chat.id, f'✅ Привет, {message.from_user.first_name}!')

        hi_text = (
            '🤖 Я бот для перевода голоса в текст\n\n'
            '📱 Просто перешли мне голосовое сообщение или кружок\n'
            '🔊 Я преобразую его в текст\n'
        )
        bot.send_message(message.chat.id, hi_text)

        app.logger.info(f"✅ Ответ отправлен")

    except Exception as e:
        app.logger.error(f"❌ Ошибка: {e}")

# Обработчик голосовых
def handle_voice(message):
    app.logger.info(f"🎤 Голосовое от {message.chat.id}")
    try:
        # # Заглушка для теста
        # bot.send_message(message.chat.id, "🎤 Голосовое сообщение получено!")
        # app.logger.info("✅ Заглушка отправлена")

        bot.send_message(message.chat.id,f"🎤 Голосовое сообщение получено, слушаю ...")

        filename = download_file(bot, message.voice.file_id)
        text = recognize_speech_chunked(filename)
        bot.send_message(message.chat.id, f"📝 Текст:\n\n{text}")

    except Exception as e:
        app.logger.error(f"❌ Ошибка: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка обработки")


# Обработчик кружков
def handle_video_note(message):
    app.logger.info(f"🎥 Кружок от {message.chat.id}")
    try:
        # # Заглушка для теста
        # bot.send_message(message.chat.id, "🎥 Кружок получен!")
        # app.logger.info("✅ Заглушка отправлена")

        bot.send_message(message.chat.id,f"🎥 Видеосообщение получено, слушаю ...")

        filename = download_file(bot, message.video_note.file_id)
        text = recognize_speech_chunked(filename)
        bot.send_message(message.chat.id, f"📝 Текст:\n\n{text}")

    except Exception as e:
        app.logger.error(f"❌ Ошибка: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка обработки")


# ВЕБХУК с ручной обработкой
@app.route('/webhook', methods=['POST'])
def webhook():
    app.logger.info("📨 ВЕБХУК ПОЛУЧЕН")

    if request.headers.get('content-type') == 'application/json':
        try:
            json_str = request.get_data().decode('utf-8')
            app.logger.info(f"📦 Длина данных: {len(json_str)} chars")

            # Парсим
            data = json.loads(json_str)

            if 'message' in data:
                message_data = data['message']
                chat_id = message_data['chat']['id']

                app.logger.info(f"💬 Чат: {chat_id}")

                # Создаем объект Message
                message_obj = types.Message.de_json(message_data)

                # Проверяем тип сообщения
                if 'text' in message_data:
                    text = message_data['text']
                    app.logger.info(f"📝 Текст: {text}")

                    if text == '/start' or text == '/start@voice_and_video_to_text_bot':
                        handle_start(message_obj)
                        app.logger.info("✅ /start обработан")

                    elif text.startswith('/'):
                        # Другие команды
                        bot.send_message(chat_id, f"Команда {text} не поддерживается")

                    else:
                        # Обычный текст
                        bot.send_message(chat_id, f"Вы написали: {text}")

                elif 'voice' in message_data:
                    app.logger.info("🎤 Голосовое сообщение")
                    handle_voice(message_obj)
                    app.logger.info("✅ Голосовое обработано")

                elif 'video_note' in message_data:
                    app.logger.info("🎤 Голосовое сообщение")
                    handle_video_note(message_obj)
                    app.logger.info("✅ Голосовое обработано")

                else:
                    app.logger.warning(f"⚠️ Неизвестный тип сообщения: {list(message_data.keys())}")
                    bot.send_message(chat_id, "Извините, я пока не обрабатываю этот тип сообщений")

            app.logger.info("✅ Вебхук обработан")
            return jsonify({"status": "ok"}), 200

        except Exception as e:
            app.logger.error(f"❌ Ошибка вебхука: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "Invalid content type"}), 400

# Главная страница
@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>🤖 Voice Bot</title></head>
    <body>
        <h1>✅ Бот работает!</h1>
        <p>Команды:</p>
        <ul>
            <li><code>/start</code> - начать работу</li>
            <li>Отправьте голосовое сообщение для теста</li>
        </ul>
        <p><a href="/send-test">Отправить тест</a></p>
    </body>
    </html>
    '''

@app.route('/send-test')
def send_test():
    """Тест отправки сообщения"""
    import requests
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": 1014682122,
        "text": "✅ Бот работает корректно!"
    }

    response = requests.post(url, json=data)
    return f'''
    <div style="padding: 20px; background: #d4edda; border-radius: 10px;">
        <h2>✅ Тест отправлен!</h2>
        <pre>{json.dumps(response.json(), indent=2, ensure_ascii=False)}</pre>
        <p><a href="/">← На главную</a></p>
    </div>
    '''

# Установка вебхука
try:
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.logger.info(f"✅ Вебхук установлен: {WEBHOOK_URL}")

    # Проверяем
    import requests
    check = requests.get(f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo").json()
    app.logger.info(f"ℹ️ Вебхук: {check['result']['url']}")

except Exception as e:
    app.logger.error(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    app.run(debug=False)
