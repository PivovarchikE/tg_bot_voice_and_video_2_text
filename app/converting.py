import os
import io
import time
import speech_recognition as sr
import moviepy as mp
from pydub import AudioSegment
from pydub.silence import split_on_silence
from config import TOKEN_WIT


def split_audio_segments(filename):
    """Разделить аудио на сегменты по тишине с ограничением максимальной длины"""
    try:
        audio = AudioSegment.from_file(filename)

        # Делаем порог чуть строже для компенсации фонового шума улицы
        audio_chunks = split_on_silence(
            audio,
            min_silence_len=500,
            silence_thresh=audio.dBFS - 16,
            keep_silence=300
        )

        max_chunk_length_ms = 12000  # Максимум 12 секунд на один кусок
        final_chunks = []

        for chunk in audio_chunks:
            # Принудительно режем слишком длинные куски, чтобы избежать Request Timeout в Wit.ai
            if len(chunk) > max_chunk_length_ms:
                for i in range(0, len(chunk), max_chunk_length_ms):
                    final_chunks.append(chunk[i:i + max_chunk_length_ms])
            else:
                final_chunks.append(chunk)

        processed_chunks = []
        for chunk in final_chunks:
            chunk_buffer = io.BytesIO()
            chunk.export(chunk_buffer, format="wav")
            chunk_buffer.seek(0)
            processed_chunks.append(chunk_buffer)

        print(f"Разделили на {len(processed_chunks)} безопасных частей")
        return processed_chunks

    except Exception as e:
        print(f"Ошибка разделения аудио: {e}")
        with open(filename, 'rb') as f:
            buffer = io.BytesIO(f.read())
        return [buffer]


def recognize_chunk_with_retry(recognizer, audio, max_retries=3, delay=2.0):
    """Отправка чанка в Wit.ai с повторными попытками при таймаутах"""
    for attempt in range(1, max_retries + 1):
        try:
            return recognizer.recognize_wit(audio, key=TOKEN_WIT)
        except sr.RequestError as e:
            if attempt < max_retries:
                print(f"    ⚠️ Таймаут/ошибка сети ({e}). Попытка {attempt}/{max_retries}, повтор через {delay} сек...")
                time.sleep(delay)
            else:
                raise e


def recognize_speech_chunked(filename):
    try:
        # Конвертируем видео/аудио в стандартный WAV перед нарезкой
        wav_filename = convert_to_wav(filename)

        audio_chunks = split_audio_segments(wav_filename)

        if len(audio_chunks) == 0:
            return "Не удалось обработать аудио (тишина или ошибка)"

        recognizer = sr.Recognizer()
        all_texts = []

        for i, chunk_buffer in enumerate(audio_chunks, 1):
            print(f"Обрабатываю часть {i}/{len(audio_chunks)}...")

            try:
                chunk_buffer.seek(0)
                with sr.AudioFile(chunk_buffer) as source:
                    audio = recognizer.record(source)

                text = recognize_chunk_with_retry(recognizer, audio, max_retries=3)

                if text and text.strip():
                    all_texts.append(text)
                    print(f"  Часть {i}: {text[:50]}...")
                else:
                    print(f"  Часть {i}: пустой ответ")

            except sr.UnknownValueError:
                print(f"  Часть {i}: не распознано (шум/тишина)")
            except sr.RequestError as e:
                print(f"  Часть {i}: ошибка API - {e}")
                all_texts.append("[часть текста пропущена]")
            except Exception as e:
                print(f"  Часть {i}: ошибка - {str(e)[:50]}")

        full_text = " ".join(all_texts).strip()

        # Удаляем временные файлы
        if os.path.exists(filename):
            os.remove(filename)
        if os.path.exists(wav_filename) and wav_filename != filename:
            os.remove(wav_filename)

        return full_text if full_text else "Не удалось распознать текст."

    except Exception as e:
        print(f"Общая ошибка recognize_speech: {e}")
        return f"Ошибка обработки: {str(e)[:100]}"


def convert_to_wav(filename):
    """Конвертация любого входящего аудио/видео файла в моно-WAV 16кГц"""
    base, _ = os.path.splitext(filename)
    new_filename = base + '.wav'

    if 'mp4' in filename or filename.endswith('.mp4'):
        video = mp.VideoFileClip(filename)
        video.audio.write_audiofile(
            new_filename,
            fps=16000,
            nbytes=2,
            buffersize=2000,
            codec='pcm_s16le',
            verbose=False,
            logger=None
        )
        video.close()
    else:
        audio = AudioSegment.from_file(filename)
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(16000)
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