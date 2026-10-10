import asyncio
import datetime
import io
import json
import math
import os
import queue
import re
import struct
import sys
import tempfile
import threading
import time
import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav
from ddgs import DDGS
import edge_tts
from groq import Groq
import pyaudio
import pygame
from PIL import Image
import pyautogui
import pytesseract
import requests
import speech_recognition as sr
from features.screen_ocr import capture_screen_text
# Import bộ xử lý PDF từ thư mục features
from features.pdf_handler import extract_text_from_file, get_any_file_path


# 1. ÉP CHUẨN UTF-8 TOÀN BỘ LUỒNG XUẤT DỮ LIỆU
if sys.stdout is not None:
  sys.stdout = io.TextIOWrapper(
      sys.stdout.buffer, encoding="utf-8", errors="ignore"
  )
else:
  sys.stdout = open(os.devnull, "w", encoding="utf-8")

if sys.stderr is not None:
  sys.stderr = io.TextIOWrapper(
      sys.stderr.buffer, encoding="utf-8", errors="ignore"
  )
else:
  sys.stderr = open(os.devnull, "w", encoding="utf-8")

if sys.stdin is None:
  sys.stdin = open(os.devnull, "r", encoding="utf-8")

import config
from features.audio_control import duck_system_volume, restore_system_volume
from features.system_control import (
    execute_command,
    get_full_user_profile,
    get_news,
    is_game_running,
)
from manager_ai import AIManager

try:
    voice_encoder = VoiceEncoder()
    if os.path.exists("owner_voice.npy"):
        OWNER_VOICE_EMBEDDING = np.load("owner_voice.npy")
        print("✅ [JARVIS] Đã tải thành công Hồ sơ vân giọng của sếp!")
    else:
        OWNER_VOICE_EMBEDDING = None
        print("⚠️ [WARN] Chưa có 'owner_voice.npy'. Hãy chạy file train_voice.py trước!")
except Exception as e:
    voice_encoder = None
    OWNER_VOICE_EMBEDDING = None
    print(f"⚠️ [WARN] Không thể tải Voice Encoder: {e}")

def verify_speaker_from_pcm(raw_pcm_data, threshold=0.5):
    """
    So sánh đoạn âm thanh thu từ mic với vân giọng sếp.
    Ngưỡng threshold: 0.50 - 0.60 là chuẩn nhất.
    """
    if OWNER_VOICE_EMBEDDING is None or voice_encoder is None:
        return True # Nếu chưa train giọng thì tạm thời cho qua

    try:
        # Chuyển đổi dữ liệu PCM bytes từ PyAudio sang numpy float32
        audio_int16 = np.frombuffer(raw_pcm_data, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0

        # Trích xuất vector giọng nói từ đoạn âm thanh vừa nghe
        current_embed = voice_encoder.embed_utterance(audio_float32)

        # Tính độ tương đồng Cosine (Cosine Similarity)
        similarity = np.dot(OWNER_VOICE_EMBEDDING, current_embed) / (
            np.linalg.norm(OWNER_VOICE_EMBEDDING) * np.linalg.norm(current_embed)
        )

        print(f"🔍 [XÁC THỰC GIỌNG]: Độ tương đồng = {similarity:.2f} (Cần >= {threshold})")

        return similarity >= threshold
    except Exception as e:
        print(f"⚠️ Lỗi xác thực giọng: {e}")
        return True


# Import GUI
try:
  from jarvis_gui import gui_queue, start_gui
except Exception as e:
  gui_queue = None
  start_gui = None
  print(f"⚠️ Không load được GUI: {e}")

# KHỞI TẠO ÂM THANH & CẤU HÌNH
pygame.mixer.init()
speech_queue = queue.Queue()
IS_SPEAKING = False
recognizer = sr.Recognizer()

# KHỞI TẠO GROQ CLIENT
client = Groq(api_key=config.GROQ_API_KEY)

# DANH SÁCH MODEL KHẢ DỤNG CHUẨN CỦA GROQ
AVAILABLE_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
]


def parse_json_safely(text: str) -> dict:
  """Tự động tìm và bóc tách chuỗi JSON ra khỏi phản hồi của AI, tránh lỗi syntax hay lỗi 400."""
  if not text:
    return {}
  match = re.search(r"\{[\s\S]*\}", text)
  if match:
    try:
      return json.loads(match.group(0))
    except Exception:
      pass
  return {}


def ensure_mixer():
  """Đảm bảo Pygame Mixer luôn được khởi tạo trước khi phát bất kỳ âm thanh nào."""
  try:
    if not pygame.mixer.get_init():
      pygame.mixer.init()
  except Exception as e:
    print(f"⚠️ [MIXER RE-INIT LỖI]: {e}")


def is_jarvis_speaking():
  if not pygame.mixer.get_init():
    return IS_SPEAKING
  try:
    return IS_SPEAKING or pygame.mixer.music.get_busy()
  except Exception:
    return IS_SPEAKING


def clear_speech_queue():
  with speech_queue.mutex:
    speech_queue.queue.clear()


def clean_text_for_tts(text):
  if not text:
    return ""
  text = re.sub(r"```[\s\S]*?```", "", text)
  text = re.sub(r"[\*#_~`>\[\]\(\)]", "", text)
  text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
  text = re.sub(r"\s+", " ", text).strip()
  return text


async def generate_audio(
    text, voice="vi-VN-NamMinhNeural", output_file="speech.mp3"
):
  clean_text = clean_text_for_tts(text)
  if not clean_text or not any(char.isalnum() for char in clean_text):
    return False

  for attempt in range(2):
    try:
      communicate = edge_tts.Communicate(clean_text, voice)
      await communicate.save(output_file)
      return True
    except Exception as e:
      if attempt == 1:
        print(f"⚠️ [TTS WARN] Bỏ qua đoạn này do nghẽn mạng Edge-TTS: {e}")
      await asyncio.sleep(0.2)
  return False


def speak(text):
  global IS_SPEAKING
  if not text or not text.strip():
    return

  clean_text = clean_text_for_tts(text)
  if not clean_text or not any(char.isalnum() for char in clean_text):
    return

  print(f"🤖 [JARVIS]: {clean_text}")
  output_file = f"speech_{int(time.time()*1000)}.mp3"

  try:
    success = asyncio.run(generate_audio(clean_text, output_file=output_file))

    if success and os.path.exists(output_file):
      ensure_mixer()
      IS_SPEAKING = True

      duck_system_volume(0.15)
      pygame.mixer.music.load(output_file)
      pygame.mixer.music.play()

      while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

      pygame.mixer.music.unload()

  except Exception as e:
    print(f"⚠️ [TTS/SPEAK ERROR]: {e}")

  finally:
    IS_SPEAKING = False
    restore_system_volume()
    if os.path.exists(output_file):
      try:
        os.remove(output_file)
      except Exception:
        pass


def ensure_wake_sound():
  sound_file = "em_day.mp3"
  if os.path.exists(sound_file):
    return

  async def _create():
    try:
      comm = edge_tts.Communicate(
          "Em nghe đây sếp!", voice="vi-VN-NamMinhNeural", rate="+20%"
      )
      await comm.save(sound_file)
    except Exception as e:
      print(f"⚠️ Lỗi tải giọng Edge-TTS: {e}")

  try:
    asyncio.run(_create())
  except Exception as e:
    print(f"⚠️ Không thể khởi tạo file em_day.mp3: {e}")


ensure_wake_sound()


def play_wake_sound_offline():
  try:
    ensure_mixer()
    duck_system_volume(0.15)
    if os.path.exists("em_day.mp3"):
      pygame.mixer.music.load("em_day.mp3")
      pygame.mixer.music.play()
      while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(20)
  except Exception as e:
    print(f"⚠️ Lỗi phát wake sound: {e}")


HOLIDAYS = {
    (1, 1): "ngày Tết Dương lịch",
    (14, 2): "ngày Lễ Tình yêu Valentine",
    (8, 3): "ngày Quốc tế Phụ nữ",
    (30, 4): "ngày Giải phóng miền Nam",
    (1, 5): "ngày Quốc tế Lao động",
    (1, 6): "ngày Quốc tế Thiếu nhi",
    (2, 9): "ngày lễ Quốc khánh",
    (19, 10): "ngày sinh nhật của Sếp",
    (20, 10): "ngày Phụ nữ Việt Nam",
    (20, 11): "ngày Nhà giáo Việt Nam",
    (24, 12): "đêm Giáng sinh",
    (25, 12): "ngày Giáng sinh",
    (31, 12): "đêm Giao thừa",
}


def get_startup_greeting():
  try:
    now = datetime.datetime.now()
    hour, minute = now.hour, now.minute
    day, month, year = now.day, now.month, now.year

    city, temp = "Hà Nội", 30

    try:
      ip_res = requests.get("http://ip-api.com/json/?lang=vi", timeout=4).json()
      if ip_res.get("status") == "success":
        raw_city = ip_res.get("regionName") or ip_res.get("city", "Hà Nội")
        lat, lon = ip_res.get("lat"), ip_res.get("lon")
        city = raw_city.replace("Tỉnh ", "").replace("Thành phố ", "")

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        w_res = requests.get(weather_url, timeout=4).json()
        temp = round(w_res["current_weather"]["temperature"])
    except Exception as e:
      print(f"⚠️ Không lấy được thông tin vị trí/thời tiết: {e}")

    holiday_name = HOLIDAYS.get((day, month))
    if holiday_name:
      short_name = holiday_name.replace("ngày ", "").replace("đêm ", "")
      holiday_text = (
          f" Hôm nay là {holiday_name}, chúc sếp dịp {short_name} vui vẻ!"
      )
    else:
      holiday_text = ""

    return (
        f"Chào sếp, bây giờ là {hour} giờ {minute} phút, ngày {day} tháng"
        f" {month} năm {year}.{holiday_text} Thời tiết hiện tại ở {city} đang là"
        f" {temp} độ C. Chúc sếp một ngày làm việc tốt lành."
    )

  except Exception as e:
    print(f"⚠️ Lỗi tạo câu chào: {e}")
    return "Chào sếp, chúc sếp một ngày làm việc tốt lành."


NOISE_BLACKLIST = [
    "nhạc thế tục",
    "phát trực tiếp",
    "cảm ơn các bạn đã theo dõi",
    "subtitles by",
    "hãy đăng ký kênh",
    "xem tiếp theo",
]


def listen_mic(
    prompt="",
    timeout=3,             # Chờ sếp bắt đầu nói trong 3s
    phrase_limit=10,
    silent=False,
    threshold=0.01,        # Nhạy gấp 3 lần cũ (thu được tiếng nói nhỏ/xa)
    silence_duration=1.0,  # Dừng nói 1s mới ngắt câu (tránh mất từ khi ngập ngừng)
):
    if prompt and not silent:
        print(f"🎤 {prompt}")

    if "gui_queue" in globals() and gui_queue:
        gui_queue.put({"type": "STATE", "value": "USER_SPEAKING"})

    p = pyaudio.PyAudio()
    stream = None
    frames = []
    has_spoken = False

    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024,
        )

        start_time = time.time()
        silence_start = None

        while True:
            try:
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)

                count = len(data) // 2
                if count > 0:
                    shorts = struct.unpack(f"<{count}h", data)
                    sum_squares = sum(s * s for s in shorts)
                    rms = math.sqrt(sum_squares / count)
                    norm_vol = min(1.0, rms / 32767.0)
                else:
                    norm_vol = 0.0

                if "gui_queue" in globals() and gui_queue:
                    gui_queue.put({"type": "VOLUME", "value": norm_vol})

                if norm_vol > threshold:
                    has_spoken = True
                    silence_start = None
                else:
                    if has_spoken and silence_start is None:
                        silence_start = time.time()

                elapsed = time.time() - start_time

                if not has_spoken and elapsed > timeout:
                    break
                if (
                    has_spoken
                    and silence_start
                    and (time.time() - silence_start > silence_duration)
                ):
                    break
                if elapsed > phrase_limit:
                    break

            except Exception:
                break

    finally:
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        p.terminate()

        if "gui_queue" in globals() and gui_queue:
            gui_queue.put({"type": "VOLUME", "value": 0.0})
            gui_queue.put({"type": "STATE", "value": "IDLE"})

    if not has_spoken or not frames:
        return None, None

    raw_audio = b"".join(frames)
    audio_data = sr.AudioData(raw_audio, 16000, 2)

    try:
        text = recognizer.recognize_google(audio_data, language="vi-VN")

        if text:
            clean_text = text.lower().strip()
            if any(noise in clean_text for noise in NOISE_BLACKLIST):
                print(f"⚠️ [LỌC TẠP ÂM]: Đã chặn từ rác -> '{text}'")
                return None, None

        # Trả về cả Text nhận diện và dữ liệu âm thanh thô (raw_audio)
        return text, raw_audio

    except sr.UnknownValueError:
        return None, None
    except sr.RequestError as e:
        print(f"⚠️ Lỗi kết nối Google STT: {e}")
        return None, None
    except Exception:
        return None, None


SYSTEM_PROMPT = """
Bạn là JARVIS - Trợ lý AI cá nhân thế hệ 3 siêu thông minh, trung thành.
Quy tắc trả lời:
- Luôn gọi người dùng là "sếp".
- Trả lời ngắn gọn (1-3 câu), chuẩn văn nói, tự nhiên như người thật.
- Tuyệt đối KHÔNG gạch đầu dòng, KHÔNG đánh số 1, 2, 3.
"""


def check_search_intent(user_input):
  for model_name in AVAILABLE_MODELS:
    try:
      router_prompt = (
          f'Câu hỏi: "{user_input}"\n\n'
          "Phân tích câu hỏi trên:\n"
          "- Trả về 'YES' nếu câu hỏi về tin tức, nhân vật, chức vụ, sự kiện,"
          " lịch sử, thời tiết, thông tin thực tế.\n"
          "- Trả về 'NO' nếu là chào hỏi, trò chuyện phím, nhờ viết code.\n\n"
          "Chỉ trả về đúng 1 từ: YES hoặc NO."
      )
      response = client.chat.completions.create(
          model=model_name,
          messages=[{"role": "user", "content": router_prompt}],
          max_tokens=150,
          temperature=0.0,
      )
      return "YES" in response.choices[0].message.content.strip().upper()
    except Exception:
      continue
  return True


def ask_groq_stream(user_input, chat_history, target_model=None):
  is_search_needed = check_search_intent(user_input)

  if is_search_needed:
    news_data = get_news(user_input)
    if news_data:
      clean_wiki = news_data.replace("[WIKIPEDIA]:", "").strip()
      reply_text = f"Dạ sếp, theo Wikipedia: {clean_wiki}"
      return reply_text

  system_instruction = (
      SYSTEM_PROMPT
      + get_full_user_profile()
      + "\n\nTrả lời ngắn gọn, tự nhiên bằng tiếng Việt."
  )

  messages = [{"role": "system", "content": system_instruction}]
  if chat_history:
    messages.extend(chat_history[-6:])
  messages.append({"role": "user", "content": user_input})

  # Sắp xếp thứ tự ưu tiên: Đưa target_model do Router chọn lên đầu tiên
  models_to_try = AVAILABLE_MODELS
  if target_model:
    models_to_try = [target_model] + [
        m for m in AVAILABLE_MODELS if m != target_model
    ]

  for model_name in models_to_try:
    try:
      print(f"🤖 [GROQ STREAM] Đang xử lý bằng model: {model_name}")
      response = client.chat.completions.create(
          model=model_name,
          messages=messages,
          temperature=0.3,
          max_tokens=400,
          stream=True,
      )

      raw_response = ""
      for chunk in response:
        delta = chunk.choices[0].delta
        content = getattr(delta, "content", "") or ""
        if content:
          raw_response += content

      final_clean = re.sub(
          r"<think>.*?</think>", "", raw_response, flags=re.DOTALL
      ).strip()
      return final_clean

    except Exception as e:
      print(f"⚠️ Model {model_name} báo lỗi stream: {e}")
      continue

  err_msg = "Em gặp lỗi khi xử lý câu hỏi sếp ơi."
  return err_msg


# ==========================================
# TOOL XỬ LÝ FILE (TÓM TẮT HOẶC DỊCH FILE PDF/WORD/TXT)
# ==========================================
def tool_process_file(user_command: str = "") -> str:
    """
    Xử lý file tài liệu đa năng cho JARVIS:
    - Phân biệt chính xác giữa TÓM TẮT và DỊCH NGUYÊN VĂN.
    - Chạy Map-Reduce không giới hạn độ dài file (không bị cắt xén 8000 ký tự nữa).
    - Tạo câu trả lời ngắn cho Voice + Tạo file .txt chi tiết mở lên Notepad cho sếp.
    """
    file_path = get_any_file_path(user_command)
    if not file_path:
        return "Em không tìm thấy file tài liệu nào trên Clipboard hay trong thư mục Downloads/Desktop cả sếp ơi."

    original_filename = os.path.basename(file_path)
    base_name = os.path.splitext(original_filename)[0]

    cmd_lower = user_command.lower()
    is_translation = any(
        kw in cmd_lower for kw in ["dịch", "translate", "sang tiếng việt"]
    )

    if is_translation:
        print(f"📄 [JARVIS] Đang DỊCH NGUYÊN VĂN file: {original_filename}...")
        file_prefix = "Ban_Dich_"
        header_title = "BẢN DỊCH NGUYÊN VĂN"
    else:
        print(f"📄 [JARVIS] Đang TÓM TẮT file: {original_filename}...")
        file_prefix = "Tom_Tat_"
        header_title = "BẢN TÓM TẮT"

    # 1. Gọi Map-Reduce xử lý toàn bộ nội dung file (không bị trảm chữ)
    from features.pdf_handler import process_file_with_map_reduce
    detailed_text = process_file_with_map_reduce(
        file_path=file_path,
        client=client,
        available_models=AVAILABLE_MODELS,
        is_translation=is_translation,
        user_command=user_command
    )

    if not detailed_text:
        return f"Không xử lý được file {original_filename} vì không trích xuất được nội dung chữ sếp ơi."

    # 2. Tạo câu thông báo bằng giọng nói (Voice summary ngắn gọn)
    if is_translation:
        voice_text = f"Dạ em đã dịch xong toàn bộ nguyên văn file {original_filename} sang tiếng Việt cho sếp rồi ạ."
    else:
        # Nếu là tóm tắt, bắt AI tạo thêm 1 câu tóm tắt cực ngắn (2-3 câu) để đọc cho sếp nghe
        try:
            summary_voice_res = client.chat.completions.create(
                model=AVAILABLE_MODELS[0],
                messages=[
                    {
                        "role": "user",
                        "content": f"Dựa vào bản tóm tắt sau, hãy viết đúng 2 câu ngắn gọn nhất để đọc thành tiếng cho sếp nghe:\n\n{detailed_text[:3000]}"
                    }
                ],
                max_tokens=150,
                temperature=0.2
            )
            voice_text = summary_voice_res.choices[0].message.content.strip()
        except Exception:
            voice_text = f"Dạ em đã tóm tắt xong toàn bộ file {original_filename} từ đầu đến kết thúc cho sếp rồi ạ."

    # 3. Xuất file kết quả ra Desktop và mở Notepad
    desktop_path = os.path.expanduser("~/Desktop")
    output_file = os.path.join(desktop_path, f"{file_prefix}{base_name}.txt")

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"=== {header_title} FILE: {original_filename} ===\n\n")
            f.write(detailed_text)

        os.system(f'start notepad "{output_file}"')
    except Exception as f_err:
        print(f"⚠️ Không lưu được file txt: {f_err}")

    return voice_text


KNOWN_APPS = [
    "notepad",
    "ghi chú",
    "word",
    "opera",
    "chrome",
    "canva",
    "discord",
    "powerpoint",
    "excel",
    "edge",
    "browser",
    "trình duyệt",
    "zalo",
    "vs code",
    "code",
    "ultraviewer",
    "blender",
    "capcut",
    "bluestacks",
    "spotify",
]


# ==========================================
# TOOL DỊCH / GIẢI THÍCH MÀN HÌNH (OCR)
# ==========================================
def tool_explain_screen(user_command: str = "") -> str:
  """Chụp màn hình (App cụ thể hoặc full màn hình) và Dịch nguyên đoạn / Phân tích."""

  cmd_lower = user_command.lower()

  target_app = ""
  for app in KNOWN_APPS:
    if app in cmd_lower:
      target_app = app
      break

  text_content, app_name = capture_screen_text(target_app)

  if not text_content or not text_content.strip():
    return f"Em không tìm thấy chữ nào trong cửa sổ {target_app if target_app else 'màn hình'} cả sếp ơi."

  # --- DÒNG DEBUG IN CHỮ OCR RA TERMINAL ĐỂ BẮT BỆNH ---
  print(f"🔍 [DEBUG OCR READ]:\n{text_content}\n-----------------------------------")

  is_translation_request = any(
      kw in cmd_lower for kw in ["dịch", "translate", "sang tiếng việt"]
  )

  if is_translation_request:
    print(
        f"📸 [JARVIS] Đang DỊCH NGUYÊN VĂN văn bản từ {app_name}"
        f" ({len(text_content)} ký tự)..."
    )
    system_prompt = (
        "Bạn là dịch giả cabin chuyên nghiệp, dịch sát nghĩa 100%.\n"
        "Nhiệm vụ:\n"
        "Dịch CHÍNH XÁC TỪNG CÂU MỘT từ câu đầu tiên đến câu cuối cùng của đoạn"
        " văn bản chính sang tiếng Việt.\n\n"
        "QUY TẮC BẮT BUỘC:\n"
        "1. KHÔNG TÓM TẮT, KHÔNG TỰ Ý ĐỔI NGHĨA (Ví dụ: 'playing badminton' dịch"
        " đúng là 'đánh cầu lông', KHÔNG dịch thành 'tập thể dục'; 'reading"
        " novels' dịch đúng là 'đọc tiểu thuyết', KHÔNG dịch thành 'viết câu"
        " chuyện').\n"
        "2. TUYỆT ĐỐI KHÔNG BỎ SÓT CÂU ĐẦU TIÊN HOẶC BẤT KỲ CÂU NÀO TRONG ĐOẠN"
        " VĂN BẢN CHÍNH.\n"
        "3. Lọc bỏ các từ rác giao diện menu/thanh công cụ (Home, Insert, Layout,"
        " Ribbon, Page, Words...), chỉ lấy và dịch đúng nội dung bài viết/ghi"
        " chú.\n\n"
        "ĐỊNH DẠNG BẮT BUỘC (TUYỆT ĐỐI KHÔNG DÙNG JSON):\n"
        "VOICE: Dạ em đã dịch xong nguyên văn đoạn văn bản cho sếp rồi ạ.\n"
        "===DETAILS===\n"
        "<BẢN DỊCH CHÍNH XÁC SÁT NGHĨA TỪNG CÂU 100% TẠI ĐÂY>"
    )
  else:
    print(f"📸 [JARVIS] Đang ĐỌC & GIẢI THÍCH màn hình từ {app_name}...")
    system_prompt = (
        "Bạn là trợ lý AI thông minh.\n"
        "Nhiệm vụ: Đọc văn bản trên màn hình và giải đáp/sửa lỗi theo yêu cầu"
        " của sếp.\n"
        "Bắt buộc trả về đúng cấu trúc JSON sau:\n"
        "{\n"
        '  "voice_summary": "<Tóm tắt ngắn gọn 2-3 câu quan trọng nhất để đọc'
        ' ra âm thanh>",\n'
        '  "detailed_summary": "<Nội dung giải thích / hướng dẫn chi tiết>"\n'
        "}"
    )

  raw_reply = None
  for model_name in AVAILABLE_MODELS:
    try:
      response = client.chat.completions.create(
          model=model_name,
          messages=[
              {"role": "system", "content": system_prompt},
              {
                  "role": "user",
                  "content": (
                      f"Yêu cầu: {user_command}\n\n[NỘI DUNG CHỮ TRÍCH XUẤT TỪ"
                      f" {app_name}]:\n{text_content[:8000]}"
                  ),
              },
          ],
          temperature=0.1,
          max_tokens=3000,
      )
      raw_reply = response.choices[0].message.content.strip()
      if raw_reply:
        print(f"✅ AI xử lý màn hình thành công qua model: {model_name}")
        break
    except Exception as e:
      print(f"⚠️ Model {model_name} báo lỗi khi OCR: {e}")
      continue

  if not raw_reply:
    return "Em gặp lỗi khi gọi AI xử lý nội dung màn hình sếp ơi."

  # ================= XỬ LÝ TÁCH PHẢN HỒI =================
  if is_translation_request or "===DETAILS===" in raw_reply:
    if "===DETAILS===" in raw_reply:
      parts = raw_reply.split("===DETAILS===")
      voice_part = parts[0].replace("VOICE:", "").strip()
      detailed_text = parts[1].strip()
      voice_text = (
          voice_part
          if voice_part
          else "Dạ em đã dịch xong đoạn văn trên màn hình cho sếp."
      )
    else:
      detailed_text = raw_reply
      voice_text = "Em đã dịch xong nội dung màn hình cho sếp."
  else:
    data = parse_json_safely(raw_reply)
    voice_text = data.get(
        "voice_summary", "Dạ em đã xử lý xong thông tin trên màn hình cho sếp."
    )
    detailed_text = data.get("detailed_summary", raw_reply)

  # ================= GHI FILE & MỞ NOTEPAD =================
  desktop_path = os.path.expanduser("~/Desktop")
  output_file = os.path.join(desktop_path, "Ban_Dich_Man_Hinh_JARVIS.txt")

  try:
    with open(output_file, "w", encoding="utf-8") as f:
      title = (
          "BẢN DỊCH NGUYÊN VĂN MÀN HÌNH"
          if is_translation_request
          else "KẾT QUẢ PHÂN TÍCH MÀN HÌNH"
      )
      f.write(f"=== {title} TỪ: {app_name} ===\n\n")
      f.write(detailed_text)

    os.system(f'start notepad "{output_file}"')
  except Exception as f_err:
    print(f"⚠️ Lỗi mở Notepad: {f_err}")

  return voice_text


# 6. LUỒNG XỬ LÝ CHÍNH
def jarvis_backend_loop():
  chat_history = []
  last_execution_time = 0
  WAKE_WORDS = [
      "jarvis",
      "gia vis",
      "gia vít",
      "ơi jarvis",
      "jarvis ơi",
      "travi",
      "travis",
      "cháo vịt",
      "trà vinh",
      "davi",
      "david",
      "sếp ơi",
  ]

  ai_manager = AIManager(client, boss_name="Sếp")

  time.sleep(1.5)

  try:
    ensure_mixer()
    if gui_queue:
      gui_queue.put({"type": "STATE", "value": "AI_SPEAKING"})

    welcome_msg = get_startup_greeting()
    speak(welcome_msg)
  except Exception as e:
    print(f"⚠️ [LỖI CÂU CHÀO KHỞI ĐỘNG]: {e}")
  finally:
    if gui_queue:
      gui_queue.put({"type": "STATE", "value": "IDLE"})

  print("\n💤 [CHẾ ĐỘ NGHỈ] Đang lắng nghe từ khóa 'Jarvis'...")

  while True:
    try:
      # 1. LẮNG NGHE TỪ KHÓA KÍCH HOẠT (WAKE WORD)
      text_hear, audio_bytes = listen_mic(timeout=2, phrase_limit=3, silent=True)

      wake_detected = False
      if text_hear and any(wake in text_hear.lower() for wake in WAKE_WORDS):

        # --- BỘ LỌC CHỈ TÍNH GIỌNG SẾP ---
        if audio_bytes and not verify_speaker_from_pcm(
            audio_bytes, threshold=0.5
        ):
          print(
              f"⛔ [TỪ CHỐI]: Phát hiện giọng người lạ ('{text_hear}'). Bỏ"
              " qua!"
          )
          continue
        # ---------------------------------

        print(f"\n👂 [KÍCH HOẠT WAKE WORD]: {text_hear}")
        ensure_mixer()
        play_wake_sound_offline()
        wake_detected = True

      # 🔴 NẾU KHÔNG CÓ TỪ KHÓA KÍCH HOẠT -> BỎ QUA, QUAY LẠI LẮNG NGHE VÒNG MỚI
      if not wake_detected:
        continue

      # 2. CHỈ KHI ĐÃ KÍCH HOẠT WAKE WORD MỚI BẮT ĐẦU NHẬN LỆNH
      if gui_queue:
        gui_queue.put({"type": "STATE", "value": "USER_SPEAKING"})

      user_command, raw_audio = listen_mic(prompt="MỜI SẾP RA LỆNH...")

      if user_command:
        # Kiểm tra vân giọng cho câu lệnh chính
        if raw_audio and not verify_speaker_from_pcm(
            raw_audio, threshold=0.5
        ):
          print("⛔ [TỪ CHỐI]: Không phải giọng của sếp!")
          restore_system_volume()
          if gui_queue:
            gui_queue.put({"type": "STATE", "value": "IDLE"})
          continue

        clean_cmd = user_command.lower()
        if "thoát" in clean_cmd:
          break

        current_time = time.time()
        if current_time - last_execution_time < 1.0:
          restore_system_volume()
          if gui_queue:
            gui_queue.put({"type": "STATE", "value": "IDLE"})
          continue
        last_execution_time = current_time

        print(f"🗣️ [SẾP NÓI]: {user_command}")
        if gui_queue:
          gui_queue.put({"type": "USER_TEXT", "value": user_command})

        cmd_lower = user_command.lower()

        # =========================================================
        # 1. CHỤP MÀN HÌNH / ỨNG DỤNG (OCR)
        # =========================================================
        OCR_EXPLICIT_KEYWORDS = [
            "màn hình",
            "trên màn hình",
            "mã lỗi",
            "chụp màn hình",
            "xem màn hình",
            "đọc màn hình",
            "dịch màn hình",
            "giải thích màn hình",
            "đọc cửa sổ",
            "dịch cửa sổ",
            "xem cửa sổ",
        ]

        is_open_or_close_cmd = any(
            op_kw in cmd_lower
            for op_kw in ["mở", "bật", "tắt", "đóng", "khởi động"]
        )

        is_ocr_trigger = (
            any(kw in cmd_lower for kw in OCR_EXPLICIT_KEYWORDS)
            or (
                any(
                    verb in cmd_lower
                    for verb in [
                        "dịch",
                        "xem",
                        "đọc",
                        "giải thích",
                        "phân tích",
                        "soát lỗi",
                    ]
                )
                and any(app in cmd_lower for app in KNOWN_APPS)
            )
        ) and not is_open_or_close_cmd

        is_file_explicit = any(
            fk in cmd_lower for fk in ["file", "pdf", "tài liệu", "file vừa tải"]
        )

        if is_ocr_trigger and not is_file_explicit:
          if gui_queue:
            gui_queue.put({"type": "STATE", "value": "AI_SPEAKING"})
          ocr_result = tool_explain_screen(user_command)
          speak(ocr_result)

        # =========================================================
        # 2. XỬ LÝ FILE TÀI LIỆU TRỰC TIẾP (PDF, WORD, TXT)
        # =========================================================
        elif any(
            kw in cmd_lower
            for kw in [
                "tóm tắt",
                "dịch file",
                "dịch tài liệu",
                "dịch pdf",
                "đọc file",
                "đọc tài liệu",
                "file vừa tải",
                "file này",
                "pdf",
            ]
        ):
          if gui_queue:
            gui_queue.put({"type": "STATE", "value": "AI_SPEAKING"})
          file_result = tool_process_file(user_command)
          speak(file_result)

        # =========================================================
        # 3. LỆNH HỆ THỐNG (CÓ HỖ TRỢ LỆNH KÉP) HOẶC HỎI ĐÁP AI
        # =========================================================
        else:
          action_result = execute_command(user_command, chat_history)
          if action_result:
            chat_history.clear()
            speak(action_result)
          else:
            if gui_queue:
              gui_queue.put({"type": "STATE", "value": "AI_SPEAKING"})
            ai_manager.ask(
                user_command, False, chat_history, speak, ask_groq_stream
            )

        while is_jarvis_speaking():
          time.sleep(0.1)

      else:
        print("⚠️ Không nhận diện được câu lệnh của sếp.")

      restore_system_volume()
      if gui_queue:
        gui_queue.put({"type": "STATE", "value": "IDLE"})

      print("\n💤 [CHẾ ĐỘ NGHỈ] Đang lắng nghe từ khóa 'Jarvis'...")

    except Exception as e:
      print(f"⚠️ [LUỒNG TỰ PHỤC HỒI]: {e}")
      restore_system_volume()
      if gui_queue:
        gui_queue.put({"type": "STATE", "value": "IDLE"})
      time.sleep(1.0)


# 7. ĐIỂM BẮT ĐẦU CHƯƠNG TRÌNH DUY NHẤT
if __name__ == "__main__":
  print("==========================================")
  print("🤖 JARVIS-V3 ĐÃ BẮT ĐẦU HOẠT ĐỘNG")
  print("==========================================")

  backend_thread = threading.Thread(target=jarvis_backend_loop, daemon=True)
  backend_thread.start()

  if start_gui:
    start_gui()
  else:
    backend_thread.join()