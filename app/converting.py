import os

import speech_recognition as sr
import tempfile
from pydub import AudioSegment
import io
import moviepy as mp


def split_audio_segments(filename, chunk_duration_ms=15000):
    """Разделить аудио на сегменты по 15 секунд"""
    try:
        # Загружаем аудио
        audio = AudioSegment.from_file(filename)
        duration_ms = len(audio)

        chunks = []

        # Разделяем на части по chunk_duration_ms
        for start_ms in range(0, duration_ms, chunk_duration_ms):
            end_ms = min(start_ms + chunk_duration_ms, duration_ms)
            chunk = audio[start_ms:end_ms]

            # Создаем временный файл для chunk
            chunk_buffer = io.BytesIO()
            chunk.export(chunk_buffer, format="wav")
            chunk_buffer.seek(0)

            chunks.append(chunk_buffer)

            # Если осталось меньше 3 секунд, объединяем с предыдущим
            if duration_ms - end_ms < 3000 and chunks:
                break

        print(f"Разделили на {len(chunks)} частей по ~{chunk_duration_ms / 1000} сек")
        return chunks

    except Exception as e:
        print(f"Ошибка разделения аудио: {e}")
        # Если не удалось разделить, возвращаем оригинал
        with open(filename, 'rb') as f:
            buffer = io.BytesIO(f.read())
        return [buffer]


def recognize_speech_chunked(filename):
    """Распознавание речи с разделением на части"""
    try:
        # Разделяем аудио на части
        audio_chunks = split_audio_segments(filename)

        if len(audio_chunks) == 0:
            return "Не удалось обработать аудио"

        recognizer = sr.Recognizer()
        all_texts = []

        # Обрабатываем каждую часть
        for i, chunk_buffer in enumerate(audio_chunks, 1):
            print(f"Обрабатываю часть {i}/{len(audio_chunks)}...")

            try:
                # Используем BytesIO для AudioFile
                chunk_buffer.seek(0)
                with sr.AudioFile(chunk_buffer) as source:
                    # Регулируем уровень шума
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = recognizer.record(source)

                # Распознаем часть
                text = recognizer.recognize_google(
                    audio,
                    language='ru',
                    show_all=False
                )

                all_texts.append(text)
                print(f"  Часть {i}: done ...")

            except sr.UnknownValueError:
                print(f"  Часть {i}: не распознано")
                all_texts.append("[неразборчиво]")
            except sr.RequestError as e:
                print(f"  Часть {i}: ошибка API - {e}")
                all_texts.append(f"[ошибка API]")
            except Exception as e:
                print(f"  Часть {i}: ошибка - {str(e)[:50]}")
                all_texts.append(f"[ошибка обработки]")

        # Объединяем все части
        full_text = " ".join(all_texts)

        # Очистка файла
        if os.path.exists(filename):
            os.remove(filename)

        return full_text

    except Exception as e:
        print(f"Общая ошибка recognize_speech: {e}")
        return f"Ошибка обработки: {str(e)[:100]}"


def convert_to_wav(filename):
    if 'mp4' in filename:
        new_filename = filename.replace('.oga', '.wav')
        video = mp.VideoFileClip(filename)
        video.audio.write_audiofile(new_filename)
    else:
        new_filename = filename.replace('.oga', '.wav')
        audio = AudioSegment.from_file(filename)
        audio.export(new_filename, format="wav")
    return new_filename


def download_file(bot, file_id):
    # Скачивание файла, который прислал пользователь
    print('+++++++Начал скачивать')
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    filename = file_id + file_info.file_path
    filename = filename.replace('/', '_')
    with open(filename, 'wb') as f:
        f.write(downloaded_file)
    print('+++++++Закончил скачивать')
    return filename


def send_text_in_parts(bot, chat_id, text, reply_to_msg_id=None):
    """
    Простая отправка текста частями
    """
    MAX_LEN = 4090

    if len(text) <= MAX_LEN:
        bot.send_message(chat_id, text, reply_to_message_id=reply_to_msg_id)
        return 1

    parts = []
    while text:
        if len(text) <= MAX_LEN:
            parts.append(text)
            break

        # Разбиваем по последнему пробелу
        split_at = text.rfind(' ', 0, MAX_LEN)
        if split_at <= 0:
            split_at = MAX_LEN

        parts.append(text[:split_at])
        text = text[split_at:].lstrip()

    # Отправляем
    for i, part in enumerate(parts):
        if i == 0 and reply_to_msg_id:
            bot.send_message(chat_id, part, reply_to_message_id=reply_to_msg_id)
        else:
            bot.send_message(chat_id, part)

    return len(parts)
