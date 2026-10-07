from datetime import datetime
import os
import re
import threading
import time
import pygame

# Khởi tạo bộ phát âm thanh pygame
try:
  pygame.mixer.init()
except Exception:
  pass

# 🔥 ĐƯỜNG DẪN FILE NHẠC CHUÔNG MP3 CỦA SẾP (Thay đường dẫn file .mp3 vào đây)
DEFAULT_RINGTONE_PATH = r"alarm_sound.mp3"

# Biến toàn cục quản lý trạng thái phát chuông
is_alarm_ringing = False


def play_alarm_sound(custom_sound_path=None):
  """Phát nhạc chuông MP3 lặp đi lặp lại vô hạn cho tới khi sếp ra lệnh tắt."""
  global is_alarm_ringing
  is_alarm_ringing = True

  sound_file = (
      custom_sound_path
      if (custom_sound_path and os.path.exists(custom_sound_path))
      else DEFAULT_RINGTONE_PATH
  )

  if os.path.exists(sound_file):
    try:
      pygame.mixer.music.load(sound_file)
      # Tham số -1 nghĩa là LẶP LẠI VÔ HẠN cho tới khi gọi stop()
      pygame.mixer.music.play(-1)
      print(f"\n⏰ [BÁO THỨC]: Đang phát chuông {sound_file}...")
    except Exception as e:
      print(f"⚠️ Lỗi phát file nhạc mp3: {e}")
  else:
    print(
      f"⚠️ Không tìm thấy file nhạc MP3 tại '{sound_file}'! Sếp nhớ kiểm tra"
      " lại đường dẫn file nhé."
    )


def stop_alarm():
  """Tắt chuông báo thức ngay lập tức."""
  global is_alarm_ringing
  if is_alarm_ringing:
    try:
      pygame.mixer.music.stop()
    except Exception:
      pass
    is_alarm_ringing = False
    return "Đã tắt chuông báo thức rồi sếp ơi!"
  return "Hiện tại không có báo thức nào đang kêu sếp ạ."


# ==================== LOGIC HẸN GIỜ & BÁO THỨC ====================


def set_timer(minutes, message="Đã hết giờ làm việc!"):
  """Hẹn giờ đếm ngược (Phút)."""

  def timer_thread():
    time.sleep(minutes * 60)
    print(f"\n⏰ [THÔNG BÁO]: {message}")
    play_alarm_sound()

  t = threading.Thread(target=timer_thread, daemon=True)
  t.start()
  return f"Đã hẹn giờ {minutes} phút nữa nhắc sếp!"


def set_alarm(target_time_str):
  """Báo thức theo giờ cố định (VD: 07:30 hoặc 14:00)."""
  try:
    now = datetime.now()
    target_time = datetime.strptime(target_time_str, "%H:%M").time()
    alarm_datetime = datetime.combine(now.date(), target_time)

    # Nếu giờ hẹn đã qua trong ngày -> Hẹn sang ngày hôm sau
    if alarm_datetime <= now:
      alarm_datetime = alarm_datetime.replace(day=now.day + 1)

    delay_seconds = (alarm_datetime - now).total_seconds()

    def alarm_thread():
      time.sleep(delay_seconds)
      print(f"\n⏰ [BÁO THỨC]: Đã đến {target_time_str} rồi sếp ơi!")
      play_alarm_sound()

    t = threading.Thread(target=alarm_thread, daemon=True)
    t.start()
    return f"Đã đặt báo thức lúc {target_time_str} cho sếp rồi ạ!"
  except Exception:
    return "Sếp đọc giờ sai định dạng rồi ạ (Ví dụ chuẩn: 7 giờ 30 hoặc 14 giờ)."


# ==================== XỬ LÝ LỆNH BẮT CÂU THOẠI ====================


def handle_timer_command(text):
  """Nhận diện câu thoại Hẹn giờ / Báo thức / Tắt chuông."""
  cmd = text.lower().strip()
  global is_alarm_ringing

  # 1. BẮT LỆNH TẮT CHUÔNG BÁO THỨC (Nói "Tắt báo thức", "Tắt chuông", "Dừng lại")
  if any(
      kw in cmd
      for kw in [
          "tắt báo thức",
          "tắt chuông",
          "dừng báo thức",
          "dừng chuông",
          "tắt hẹn giờ",
          "im đi",
          "tắt đi",
      ]
  ):
    return stop_alarm()

  # 2. BẮT LỆNH HẸN GIỜ (VD: "Hẹn giờ 15 phút", "Nhắc tôi sau 30 phút")
  elif any(kw in cmd for kw in ["hẹn giờ", "nhắc tôi sau", "đặt giờ"]):
    match = re.search(r"(\d+)\s*(phút|m|tiếng|giờ)", cmd)
    if match:
      num = int(match.group(1))
      unit = match.group(2)
      minutes = num * 60 if unit in ["tiếng", "giờ"] else num
      return set_timer(minutes, message=f"Đã hết {num} {unit} rồi sếp ơi!")

  # 3. BẮT LỆNH BÁO THỨC (VD: "Báo thức lúc 7 giờ 30", "Đặt báo thức 14:00")
  elif "báo thức" in cmd or "thông báo" in cmd:
    match = re.search(r"(\d{1,2})\s*(?:h|:|giờ)\s*(\d{1,2})?", cmd)
    if match:
      hour = int(match.group(1))
      minute = int(match.group(2)) if match.group(2) else 0
      time_str = f"{hour:02d}:{minute:02d}"
      return set_alarm(time_str)

  return None