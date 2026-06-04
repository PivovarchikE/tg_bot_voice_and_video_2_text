import os
import io
import speech_recognition as sr
import moviepy as mp
from pydub import AudioSegment
from pydub.silence import split_on_silence
from config import TOKEN_WIT

def split_audio_segments(filename):
    """Разделить аудио на сегменты по тишине и вернуть список буферов BytesIO"""
    try:
        # Загружаем аудио
        audio = AudioSegment.from_file(filename)

        # Находим чанки по тишине
        audio_chunks = split_on_silence(
            audio,
            min_silence_len=500,  # минимальная длина тишины в мс
            silence_thresh=audio.dBFS - 14,  # порог тишины
            keep_silence=500  # оставить немного тишины по краям для естественности
        )

        processed_chunks = []

        # Конвертируем каждый AudioSegment чанк в BytesIO буфер, как и ожидает распознаватель
        for chunk in audio_chunks:
            chunk_buffer = io.BytesIO()
            chunk.export(chunk_buffer, format="wav")
            chunk_buffer.seek(0)
            processed_chunks.append(chunk_buffer)

        print(f"Разделили по тишине на {len(processed_chunks)} частей")
        return processed_chunks

    except Exception as e:
        print(f"Ошибка разделения аудио: {e}")
        # Если не удалось разделить, возвращаем оригинал в виде буфера
        with open(filename, 'rb') as f:
            buffer = io.BytesIO(f.read())
        return [buffer]


def recognize_speech_chunked(filename):
    """Распознавание речи с разделением на части"""
    try:
        # Разделяем аудио на части
        audio_chunks = split_audio_segments(filename)

        if len(audio_chunks) == 0:
            return "Не удалось обработать аудио (тишина или ошибка)"

        recognizer = sr.Recognizer()
        all_texts = []

        # Обрабатываем каждую часть
        for i, chunk_buffer in enumerate(audio_chunks, 1):
            print(f"Обрабатываю часть {i}/{len(audio_chunks)}...")

            try:
                # Теперь chunk_buffer — это гарантированно BytesIO
                chunk_buffer.seek(0)
                with sr.AudioFile(chunk_buffer) as source:
                    audio = recognizer.record(source)

                # Распознаем часть через Wit.ai
                text = recognizer.recognize_wit(
                    audio,
                    key=TOKEN_WIT
                )

                if text.strip():
                    all_texts.append(text)
                print(f"  Часть {i}: {text[:50]}...")

            except sr.UnknownValueError:
                print(f"  Часть {i}: не распознано")
                all_texts.append("[неразборчиво]")
            except sr.RequestError as e:
                print(f"  Часть {i}: ошибка API - {e}")
                all_texts.append("[ошибка API]")
            except Exception as e:
                print(f"  Часть {i}: ошибка - {str(e)[:50]}")
                all_texts.append("[ошибка обработки]")

        # Объединяем все части
        full_text = " ".join(all_texts)

        # Очистка исходного файла
        if os.path.exists(filename):
            os.remove(filename)

        return full_text

    except Exception as e:
        print(f"Общая ошибка recognize_speech: {e}")
        return f"Ошибка обработки: {str(e)[:100]}"


def convert_to_wav(filename):
    """Конвертация любого входящего аудио/видео файла в моно-WAV 16кГц"""
    # Безопасная замена любого старого расширения на .wav
    base, _ = os.path.splitext(filename)
    new_filename = base + '.wav'

    if 'mp4' in filename or filename.endswith('.mp4'):
        video = mp.VideoFileClip(filename)
        # Сразу жмем аудио при извлечении из видео для экономии CPU на PythonAnywhere
        video.audio.write_audiofile(
            new_filename,
            fps=16000,
            nbytes=2,
            buffersize=2000,
            codec='pcm_s16le',
            verbose=False,
            logger=None
        )
        video.close()  # Закрываем клип, чтобы освободить ресурсы RAM
    else:
        audio = AudioSegment.from_file(filename)
        audio = audio.set_channels(1)  # Обязательно Mono
        audio = audio.set_frame_rate(16000)  # Оптимально для речи
        audio.export(new_filename, format="wav")

    return new_filename


def download_file(bot, file_id):
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
    MAX_LEN = 4090

    if len(text) <= MAX_LEN:
        bot.send_message(chat_id, text, reply_to_message_id=reply_to_msg_id)
        return 1

    parts = []
    while text:
        if len(text) <= MAX_LEN:
            parts.append(text)
            break

        split_at = text.rfind(' ', 0, MAX_LEN)
        if split_at <= 0:
            split_at = MAX_LEN

        parts.append(text[:split_at])
        text = text[split_at:].lstrip()

    for i, part in enumerate(parts):
        if i == 0 and reply_to_msg_id:
            bot.send_message(chat_id, part, reply_to_message_id=reply_to_msg_id)
        else:
            bot.send_message(chat_id, part)

    return len(parts)