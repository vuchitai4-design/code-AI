import gc
import os
import pythoncom
from ctypes import POINTER, cast
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume

# Bộ nhớ lưu trữ âm lượng gốc
ducked_sessions = {}
is_ducked = False


def get_session_key(session):
  """Lấy ID định danh duy nhất cho từng Session âm thanh."""
  try:
    if session.Process:
      return f"{session.Process.name().lower()}_{session.ProcessId}"
  except Exception:
    pass
  if hasattr(session, "Identifier") and session.Identifier:
    return str(session.Identifier)
  if hasattr(session, "DisplayName") and session.DisplayName:
    return str(session.DisplayName).lower()
  return str(session.ProcessId) if hasattr(session, "ProcessId") else None


def match_app(session, clean_app):
  """Nhận diện app chính xác qua Tên Process, Identifier hoặc DisplayName."""
  # 1. Quét tên Process
  try:
    if session.Process and clean_app in session.Process.name().lower():
      return True
  except Exception:
    pass

  # 2. Quét Identifier (Spotify rất hay nằm ở đây)
  try:
    if (
        hasattr(session, "Identifier")
        and session.Identifier
        and clean_app in str(session.Identifier).lower()
    ):
      return True
  except Exception:
    pass

  # 3. Quét DisplayName
  try:
    if (
        hasattr(session, "DisplayName")
        and session.DisplayName
        and clean_app in str(session.DisplayName).lower()
    ):
      return True
  except Exception:
    pass

  return False


def duck_system_volume(*args, **kwargs):
  """KHI AI CẤT GIỌNG: Giảm âm lượng các app về tối đa 15% (nếu đang >15% thì kéo xuống, nếu <=15% thì giữ nguyên)."""
  global ducked_sessions, is_ducked
  try:
    pythoncom.CoInitialize()
    sessions = AudioUtilities.GetAllSessions()
    current_pid = os.getpid()

    for session in sessions:
      try:
        if session.Process and session.ProcessId == current_pid:
          continue

        sess_key = get_session_key(session)
        if not sess_key:
          continue

        volume = session._ctl.QueryInterface(ISimpleAudioVolume)
        cur_vol = volume.GetMasterVolume()

        # Lưu lại âm lượng thực tế trước khi dìm (nếu chưa lưu)
        if sess_key not in ducked_sessions:
          ducked_sessions[sess_key] = cur_vol

        # 🔥 CHỈ DÌM NẾU > 0.15 (15%), NẾU NHỎ HƠN THÌ GIỮ NGUYÊN MỨC NHỎ ĐÓ
        target_vol = min(cur_vol, 0.15)
        volume.SetMasterVolume(target_vol, None)
        del volume
      except Exception:
        pass

    is_ducked = True
  except Exception as e:
    print(f"⚠️ Lỗi dìm âm thanh: {e}")
  finally:
    sessions = None
    gc.collect()
    try:
      pythoncom.CoUninitialize()
    except Exception:
      pass


def restore_system_volume(*args, **kwargs):
  """KHI AI TẮT GIỌNG: Khôi phục chính xác mức âm lượng cũ / mới chỉnh."""
  global ducked_sessions, is_ducked
  if not ducked_sessions:
    is_ducked = False
    return

  try:
    pythoncom.CoInitialize()
    sessions = AudioUtilities.GetAllSessions()

    for session in sessions:
      try:
        sess_key = get_session_key(session)
        volume = session._ctl.QueryInterface(ISimpleAudioVolume)
        restored = False

        # 1. Khôi phục theo Key chính xác
        if sess_key and sess_key in ducked_sessions:
          volume.SetMasterVolume(ducked_sessions[sess_key], None)
          restored = True

        # 2. Dự phòng cho Opera/Chrome (Multi-process)
        if not restored and session.Process:
          p_name = session.Process.name().lower()
          for saved_key, saved_vol in ducked_sessions.items():
            if saved_key.startswith(p_name):
              volume.SetMasterVolume(saved_vol, None)
              restored = True
              break

        del volume
      except Exception:
        pass

    ducked_sessions.clear()
    is_ducked = False
  except Exception as e:
    print(f"⚠️ Lỗi khôi phục âm thanh: {e}")
  finally:
    sessions = None
    gc.collect()
    try:
      pythoncom.CoUninitialize()
    except Exception:
      pass


def set_volume(level, target_app=None):
  """Chỉnh âm lượng ứng dụng / hệ thống."""
  global ducked_sessions, is_ducked
  try:
    level = max(0, min(100, int(level)))
    float_level = level / 100.0  # VD: 50% -> 0.5
    pythoncom.CoInitialize()

    # 1. CHỈNH ÂM LƯỢNG APP CỤ THỂ
    if (
        target_app
        and target_app.strip()
        and target_app.lower()
        not in ["hệ thống", "máy tính", "master", "loa", "tổng", "pc"]
    ):
      clean_app = target_app.lower().strip()
      sessions = AudioUtilities.GetAllSessions()
      found = False

      for session in sessions:
        try:
          if match_app(session, clean_app):
            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
            sess_key = get_session_key(session)

            # Lưu mức % mới vào bộ nhớ khôi phục
            if sess_key:
              ducked_sessions[sess_key] = float_level

            if session.Process:
              p_name = session.Process.name().lower()
              for k in list(ducked_sessions.keys()):
                if k.startswith(p_name):
                  ducked_sessions[k] = float_level

            # Nếu AI đang nói -> Giữ mức nhỏ nhất giữa mức mới chỉnh và 15%
            # Nếu AI không nói -> Đặt trực tiếp mức float_level
            if is_ducked:
              target_vol = min(float_level, 0.15)
              volume.SetMasterVolume(target_vol, None)
            else:
              volume.SetMasterVolume(float_level, None)

            found = True
            del volume
        except Exception:
          pass

      sessions = None
      gc.collect()

      if found:
        return f"Đã chỉnh âm lượng của {target_app} về {level}% rồi sếp!"
      else:
        return (
            f"Em không thấy {target_app} đang mở hoặc phát âm thanh sếp"
            " ạ."
        )

    # 2. CHỈNH ÂM LƯỢNG HỆ THỐNG
    else:
      devices = AudioUtilities.GetSpeakers()
      interface = devices.Activate(
          IAudioEndpointVolume._iid_, CLSCTX_ALL, None
      )
      volume = cast(interface, POINTER(IAudioEndpointVolume))
      volume.SetMasterVolumeLevelScalar(float_level, None)

      del volume
      devices = None
      gc.collect()
      return f"Đã chỉnh âm lượng hệ thống lên {level}% rồi sếp!"

  except Exception as e:
    print(f"⚠️ Lỗi chỉnh âm lượng: {e}")
    return "Em gặp lỗi khi chỉnh âm lượng rồi sếp ơi."
  finally:
    try:
      pythoncom.CoUninitialize()
    except Exception:
      pass