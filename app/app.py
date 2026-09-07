import os
import sys
import json
import time
import logging
import threading
from flask import Flask, request, jsonify, Response
import telebot
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

app.logger.info("🚀 Бот запущен")
app.logger.info(f"Вебхук адрес из конфига: {WEBHOOK_URL}")

# Хранилище для фоновых задач
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
    processed_messages.add(key)
    if len(processed_messages) > 100:
        processed_messages.pop()


# Обработчик команд
def handle_start(message):
    """Обработчик команды /start"""
    app.logger.info(f"🔥 Обработка /start для {message.chat.id}")
    try:
        bot.send_message(message.chat.id, f'✅ Привет, {message.from_user.first_name}!')
        hi_text = (
            '🤖 Я бот для перевода голоса в текст\n\n'
            '📱 Просто перешли мне голосовое сообщение или кружок\n'
            '🔊 Я преобразую его в текст\n'
        )
        bot.send_message(message.chat.id, hi_text)
    except Exception as e:
        app.logger.error(f"❌ Ошибка в /start: {e}")


# Фоновая обработка голосовых
def process_voice_background(message_data, message_obj):
    """Фоновая обработка голосового сообщения"""
    chat_id = message_data['chat']['id']
    message_id = message_data['message_id']
    try:
        if is_already_processed(message_id, chat_id):
            return

        mark_as_processing(message_id, chat_id)
        bot.send_message(chat_id, "🎤 Голосовое сообщение получено, обрабатываю...")

        filename = download_file(bot, message_obj.voice.file_id)
        text = recognize_speech_chunked(filename)

        send_text_in_parts(bot=bot, chat_id=chat_id, text=text)
        mark_as_processed(message_id, chat_id)
        app.logger.info(f"✅ Голосовое {chat_id}:{message_id} обработано")

    except Exception as e:
        app.logger.error(f"❌ Фоновая ошибка голосового: {e}")
        try:
            bot.send_message(chat_id, "❌ Ошибка обработки голосового сообщения")
        except Exception:
            pass
    finally:
        pending_tasks.pop(f"{chat_id}:{message_id}", None)


# Фоновая обработка кружков
def process_video_note_background(message_data, message_obj):
    """Фоновая обработка видеосообщения"""
    chat_id = message_data['chat']['id']
    message_id = message_data['message_id']
    try:
        if is_already_processed(message_id, chat_id):
            return

        mark_as_processing(message_id, chat_id)
        bot.send_message(chat_id, "🎥 Видеосообщение получено, обрабатываю...")

        filename = download_file(bot, message_obj.video_note.file_id)
        text = recognize_speech_chunked(filename)

        send_text_in_parts(bot=bot, chat_id=chat_id, text=text)
        mark_as_processed(message_id, chat_id)
        app.logger.info(f"✅ Видеосообщение {chat_id}:{message_id} обработано")

    except Exception as e:
        app.logger.error(f"❌ Фоновая ошибка видеосообщения: {e}")
        try:
            bot.send_message(chat_id, "❌ Ошибка обработки видеосообщения")
        except Exception:
            pass
    finally:
        pending_tasks.pop(f"{chat_id}:{message_id}", None)


# ВЕБХУК
@app.route('/webhook', methods=['POST'])
def webhook():
    """Принимает запросы от Telegram и запускает обработку в потоке"""
    response = Response('OK', status=200)

    if request.headers.get('content-type') == 'application/json':
        try:
            json_str = request.get_data().decode('utf-8')
            data = json.loads(json_str)

            if 'message' in data:
                message_data = data['message']
                chat_id = message_data['chat']['id']
                message_id = message_data.get('message_id')

                if message_id and is_already_processed(message_id, chat_id):
                    return response

                message_obj = types.Message.de_json(message_data)

                if 'text' in message_data:
                    app.logger.info("📝 Текстовое сообщение")
                    text = message_data['text']
                    if text.startswith('/start'):
                        handle_start(message_obj)
                    elif text.startswith('/'):
                        bot.send_message(chat_id, f"Команда {text} не поддерживается")
                    else:
                        bot.send_message(chat_id, f"Вы написали: {text}")

                elif 'voice' in message_data:
                    app.logger.info("🎤 Голосовое (запуск в фоне)")
                    threading.Thread(
                        target=process_voice_background,
                        args=(message_data, message_obj),
                        daemon=True
                    ).start()

                elif 'video_note' in message_data:
                    app.logger.info("🎥 Видеосообщение (запуск в фоне)")
                    threading.Thread(
                        target=process_video_note_background,
                        args=(message_data, message_obj),
                        daemon=True
                    ).start()

        except Exception as e:
            app.logger.error(f"❌ Ошибка вебхука: {e}")

    return response


# Фоновая очистка подвисших задач
def cleanup_old_tasks():
    while True:
        time.sleep(3600)
        now = time.time()
        to_remove = [k for k, start in pending_tasks.items() if now - start > 7200]
        for key in to_remove:
            pending_tasks.pop(key, None)


threading.Thread(target=cleanup_old_tasks, daemon=True).start()


@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>🤖 Voice Bot</title></head>
    <body>
        <h1>✅ Бот работает!</h1>
        <p>Отправьте голосовое или видеосообщение в Telegram.</p>
    </body>
    </html>
    '''


@app.route('/tasks')
def show_tasks():
    return jsonify({
        "pending_tasks": pending_tasks,
        "processed_count": len(processed_messages),
        "timestamp": time.time()
    })


if __name__ == "__main__":
    app.run(debug=False)