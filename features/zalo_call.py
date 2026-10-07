import ctypes
import os
import time
import pyautogui

# Ép Windows nhận đúng độ phân giải thật
try:
  ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
  try:
    ctypes.windll.user32.SetProcessDPIAware()
  except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ACCEPT_IMG = os.path.join(BASE_DIR, "zalo_accept.png")
REJECT_IMG = os.path.join(BASE_DIR, "zalo_reject.png")

# 🔥 TOẠ ĐỘ CỐ ĐỊNH POPUP ZALO TRÊN MÁY SẾP
ACCEPT_POS = (2419, 1478)  # Tọa độ nút Nghe
REJECT_POS = (2319, 1478)  # Tọa độ nút Từ chối

is_calling = False

# Triệt tiêu độ trễ mặc định của PyAutoGUI để click trong chớp mắt
pyautogui.PAUSE = 0.000000001


def fast_click_and_restore(target_x, target_y):
  """Lưu vị trí chuột sếp đang di -> Nhảy sang click Zalo -> Bắn chuột về chỗ cũ

  trong ~5ms.

  Ép Zalo Electron phải nhận sự kiện click thật.
  """
  try:
    # 1. Lưu vị trí chuột hiện tại sếp đang chơi game/làm việc
    orig_x, orig_y = pyautogui.position()

    # 2. Thao tác click phần cứng thực tế
    pyautogui.click(target_x, target_y)

    # 3. Trả chuột về lại đúng tọa độ cũ ngay tức khắc
    pyautogui.moveTo(orig_x, orig_y)

    print(
        f"⚡ [ZALO] Bấm thực tế thành công tại ({target_x}, {target_y}) -> Trả"
        f" chuột về ({orig_x}, {orig_y})"
    )
    return True
  except Exception as e:
    print(f"❌ Lỗi click: {e}")
    return False


def click_target(image_path, fallback_pos=None, confidence=0.75):
  target_x, target_y = None, None

  # 1. Thử quét ảnh
  if os.path.exists(image_path):
    try:
      location = pyautogui.locateCenterOnScreen(
          image_path, confidence=confidence, grayscale=True
      )
      if location:
        target_x, target_y = location.x, location.y
    except Exception:
      pass

  # 2. Không quét được ảnh -> Dùng tọa độ cố định
  if target_x is None and target_y is None and fallback_pos:
    target_x, target_y = fallback_pos

  # 3. Thực hiện click thật siêu tốc
  if target_x is not None and target_y is not None:
    return fast_click_and_restore(target_x, target_y)

  return False


def accept_zalo_call(speak_func=None):
  """Chấp nhận cuộc gọi Zalo."""
  global is_calling

  # Bấm xong thực tế rồi mới cất giọng thông báo
  if click_target(ACCEPT_IMG, fallback_pos=ACCEPT_POS):
    is_calling = True
    print("\n📞 [ZALO] Đã bắt máy cuộc gọi thành công!")
    if speak_func:
      speak_func("Dạ, em đã bắt máy Zalo cho sếp rồi ạ.")
    return True
  else:
    if speak_func:
      speak_func("Em không bấm được nút Zalo sếp ơi.")
    return False


def reject_zalo_call(speak_func=None):
  """Từ chối cuộc gọi Zalo."""
  if click_target(REJECT_IMG, fallback_pos=REJECT_POS):
    print("❌ [ZALO] Đã từ chối cuộc gọi!")
    if speak_func:
      speak_func("Dạ, em đã từ chối cuộc gọi Zalo.")
    return True
  return False

