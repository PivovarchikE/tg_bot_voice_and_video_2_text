import telebot
from flask import Flask, request, jsonify, Response
import logging
import sys
import json
import threading
import time
from telebot import types

from config import TOKEN, WEBHOOK_URL
from .converting import recognize_speech_chunked, download_file, send_text_in_parts

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

app.logger.info(f"🚀 Бот запущен")
app.logger.info(f"Вебхук: {WEBHOOK_URL}")

# Хранилище для фоновых задач (чтобы избежать повторной обработки)
processed_messages = set()
pending_tasks = {}

def is_already_processed(message_id, chat_id):
    """Проверяет, обрабатывается ли уже это сообщение"""
    key = f"{chat_id}:{message_id}"
    return key in processed_messages or key in pending_tasks

def mark_as_processing(message_id, chat_id):
    """Помечает сообщение как обрабатываемое"""
    key = f"{chat_id}:{message_id}"
    pending_tasks[key] = time.time()

def mark_as_processed(message_id, chat_id):
    """Помечает сообщение как обработанное"""
    key = f"{chat_id}:{message_id}"
    pending_tasks.pop(key, None)
    # Храним ID последних 100 обработанных сообщений
    processed_messages.add(key)
    if len(processed_messages) > 100:
        # Удаляем самые старые
        processed_messages.pop()

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

# Фоновая обработка голосовых
def process_voice_background(message_data, message_obj):
    """Фоновая обработка голосового сообщения"""
    try:
        chat_id = message_data['chat']['id']
        message_id = message_data['message_id']

        # Проверяем, не обрабатывается ли уже
        if is_already_processed(message_id, chat_id):
            app.logger.info(f"⏭️ Сообщение {chat_id}:{message_id} уже обрабатывается, пропускаем")
            return

        # Помечаем как обрабатываемое
        mark_as_processing(message_id, chat_id)

        # Уведомляем пользователя
        bot.send_message(chat_id, "🎤 Голосовое сообщение получено, слушаю...")

        # Обработка
        filename = download_file(bot, message_obj.voice.file_id)
        text = recognize_speech_chunked(filename)

        # Отправка результата
        send_text_in_parts(
            bot=bot,
            chat_id=chat_id,
            text=text,
        )

        # Помечаем как обработанное
        mark_as_processed(message_id, chat_id)
        app.logger.info(f"✅ Голосовое {chat_id}:{message_id} обработано в фоне")

    except Exception as e:
        app.logger.error(f"❌ Фоновая ошибка голосового: {e}")
        try:
            bot.send_message(chat_id, "❌ Ошибка обработки голосового сообщения")
        except:
            pass
        finally:
            # Снимаем блокировку при ошибке
            if 'chat_id' in locals() and 'message_id' in locals():
                pending_tasks.pop(f"{chat_id}:{message_id}", None)

# Фоновая обработка кружков
def process_video_note_background(message_data, message_obj):
    """Фоновая обработка видеосообщения"""
    try:
        chat_id = message_data['chat']['id']
        message_id = message_data['message_id']

        # Проверяем, не обрабатывается ли уже
        if is_already_processed(message_id, chat_id):
            app.logger.info(f"⏭️ Сообщение {chat_id}:{message_id} уже обрабатывается, пропускаем")
            return

        # Помечаем как обрабатываемое
        mark_as_processing(message_id, chat_id)

        # Уведомляем пользователя
        bot.send_message(chat_id, "🎥 Видеосообщение получено, слушаю...")

        # Обработка
        filename = download_file(bot, message_obj.video_note.file_id)
        text = recognize_speech_chunked(filename)

        # Отправка результата
        send_text_in_parts(
            bot=bot,
            chat_id=chat_id,
            text=text,
        )

        # Помечаем как обработанное
        mark_as_processed(message_id, chat_id)
        app.logger.info(f"✅ Видеосообщение {chat_id}:{message_id} обработано в фоне")

    except Exception as e:
        app.logger.error(f"❌ Фоновая ошибка видеосообщения: {e}")
        try:
            bot.send_message(chat_id, "❌ Ошибка обработки видеосообщения")
        except:
            pass
        finally:
            # Снимаем блокировку при ошибке
            if 'chat_id' in locals() and 'message_id' in locals():
                pending_tasks.pop(f"{chat_id}:{message_id}", None)

# ВЕБХУК с мгновенным ответом
@app.route('/webhook', methods=['POST'])
def webhook():
    """Вебхук, который отвечает мгновенно и обрабатывает в фоне"""
    app.logger.info("📨 ВЕБХУК ПОЛУЧЕН")

    # 1. НЕМЕДЛЕННО возвращаем ответ Telegram
    response = Response('OK', status=200)

    if request.headers.get('content-type') == 'application/json':
        try:
            # Быстро читаем данные
            json_str = request.get_data().decode('utf-8')
            data = json.loads(json_str)

            # Если есть сообщение - запускаем в фоне
            if 'message' in data:
                message_data = data['message']
                chat_id = message_data['chat']['id']
                message_id = message_data.get('message_id')

                app.logger.info(f"💬 Чат: {chat_id}, Сообщение ID: {message_id}")

                # Проверяем дубликат
                if message_id and is_already_processed(message_id, chat_id):
                    app.logger.info(f"🔄 Дубликат вебхука, игнорируем")
                    return response

                # Создаем объект Message для фоновой обработки
                message_obj = types.Message.de_json(message_data)

                # Определяем тип и запускаем в фоне
                if 'text' in message_data:
                    text = message_data['text']
                    if text == '/start' or text.startswith('/start'):
                        # Команды обрабатываем сразу (они быстрые)
                        handle_start(message_obj)
                    elif text.startswith('/'):
                        bot.send_message(chat_id, f"Команда {text} не поддерживается")

                elif 'voice' in message_data:
                    app.logger.info("🎤 Голосовое (запуск в фоне)")
                    # Запускаем в отдельном потоке
                    thread = threading.Thread(
                        target=process_voice_background,
                        args=(message_data, message_obj),
                        daemon=True
                    )
                    thread.start()

                elif 'video_note' in message_data:
                    app.logger.info("🎥 Видеосообщение (запуск в фоне)")
                    # Запускаем в отдельном потоке
                    thread = threading.Thread(
                        target=process_video_note_background,
                        args=(message_data, message_obj),
                        daemon=True
                    )
                    thread.start()

                else:
                    app.logger.warning(f"⚠️ Неизвестный тип")

            app.logger.info("✅ Вебхук принят, обработка в фоне")

        except Exception as e:
            app.logger.error(f"❌ Ошибка парсинга вебхука: {e}")
            # Все равно возвращаем OK, чтобы Telegram не слал повторно
    else:
        app.logger.warning("⚠️ Неверный content-type")

    return response  # Важно: возвращаем подготовленный response

# Очистка старых задач (раз в час)
def cleanup_old_tasks():
    """Очищает старые задачи, которые висят слишком долго"""
    while True:
        time.sleep(3600)  # Раз в час
        now = time.time()
        to_remove = []

        for key, start_time in pending_tasks.items():
            if now - start_time > 7200:  # 2 часа
                to_remove.append(key)
                app.logger.warning(f"🧹 Удаляю зависшую задачу: {key}")

        for key in to_remove:
            pending_tasks.pop(key, None)

# Запуск очистки в фоне
cleanup_thread = threading.Thread(target=cleanup_old_tasks, daemon=True)
cleanup_thread.start()

# Главная страница (без изменений)
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
        <p><strong>⚠️ Длинные голосовые обрабатываются в фоне до 30 минут</strong></p>
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
        "text": "✅ Бот работает корректно! (Webhook мгновенный, обработка в фоне)"
    }

    response = requests.post(url, json=data)
    return f'''
    <div style="padding: 20px; background: #d4edda; border-radius: 10px;">
        <h2>✅ Тест отправлен!</h2>
        <pre>{json.dumps(response.json(), indent=2, ensure_ascii=False)}</pre>
        <p><a href="/">← На главную</a></p>
    </div>
    '''

# Статус задач
@app.route('/tasks')
def show_tasks():
    """Показывает текущие задачи"""
    return jsonify({
        "pending_tasks": pending_tasks,
        "processed_count": len(processed_messages),
        "timestamp": time.time()
    })

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
    app.logger.error(f"❌ Ошибка установки вебхука: {e}")

if __name__ == "__main__":
    app.run(debug=False)
