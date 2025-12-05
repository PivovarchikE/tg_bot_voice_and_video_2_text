import os
import telebot
from .converting import download_file, recognize_speech
from config import TOKEN


bot = None

# Получаем токен из переменных окружения


def init_bot(token):
    """Инициализирует бота с переданным токеном"""
    global bot
    bot = telebot.TeleBot(token)
    return bot


def setup_handlers(bot_instance):
    """Настраиваем обработчики для бота"""
    @bot_instance.message_handler(commands=['start'])
    def say_hi(message):
        bot_instance.send_message(message.chat.id, f'Привет, {message.chat.first_name}!')

        sti_path = 'cat_persik/webp/file_157466499.webp'
        if os.path.exists(sti_path):
            with open(sti_path, 'rb') as sti:
                bot_instance.send_sticker(message.chat.id, sti)

        hi_text = (
            'Я перевожу голосовые сообщения в текст, используя api google. '
            'Пока я в режиме демо и работаю с файлами до 60 секунд и не '
            'расставляю знаки препинания.\n\n'
            'Просто запиши мне новое голосовое сообщение или '
            'перешли существующее.'
        )
        bot_instance.send_message(message.chat.id, hi_text)


    @bot_instance.message_handler(content_types=['voice'])
    def transcript(message):
        try:
            filename = download_file(bot_instance, message.voice.file_id)
            text = recognize_speech(filename)
            bot_instance.send_message(message.chat.id, text)
        except Exception as e:
            print(f"Ошибка: {e}")
            bot_instance.send_message(message.chat.id, "Извините, произошла ошибка")

    return bot_instance
