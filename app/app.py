import telebot
from flask import Flask, request

from config import TOKEN, WEBHOOK_URL
from app.converting import recognize_speech, download_file


token = TOKEN
bot = telebot.TeleBot(token)
app = Flask(__name__)


@bot.message_handler(commands=['start'])
def say_hi(message):
    bot.send_message(message.chat.id, f'Привет, {message.chat.first_name}!')
    hi_text = (
        'Я перевожу голосовые сообщения в текст, используя Google API.\n'
        'Файлы удаляются сразу после перевода.\n'
        'Пока работаю с файлами до 60 секунд.\n\n'
        'Запиши мне новое голосовое сообщение или перешли существующее.'
    )
    bot.send_message(message.chat.id, hi_text)


@bot.message_handler(content_types=['voice'])
def transcript(message):
    filename = download_file(bot, message.voice.file_id)
    text = recognize_speech(filename)
    bot.send_message(message.chat.id, text)


# Flask route для webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

if __name__ == "__main__":
    # Устанавливаем webhook (делается один раз при старте)
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=5000)
