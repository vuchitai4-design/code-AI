import psutil
import win32con
import win32gui
import win32process

# ==================== HÀM BỔ TRỢ QUÉT CỬA SỔ ====================


def _find_hwnds_by_app_name(target_app):
  """Tìm danh sách ID cửa sổ (HWND) - Đã xử lý chuẩn đét cho File Explorer."""
  if not target_app or not target_app.strip():
    return []

  clean_app = target_app.lower().strip()
  found_hwnds = []

  # Danh sách từ khóa người dùng hay gọi File Explorer
  explorer_keywords = [
      "file explorer",
      "explorer",
      "trình quản lý tệp",
      "quản lý tệp",
  ]
  is_explorer = any(kw in clean_app for kw in explorer_keywords)

  def enum_windows_callback(hwnd, extra):
    if win32gui.IsWindowVisible(hwnd):
      class_name = win32gui.GetClassName(hwnd)

      # 1. 🔥 XỬ LÝ RIÊNG CHO FILE EXPLORER: Chỉ bắt đúng cửa sổ Thư mục (CabinetWClass)
      if is_explorer:
        if class_name in ["CabinetWClass", "ExploreWClass"]:
          found_hwnds.append(hwnd)
        return

      # 2. BỎ QUA TASKBAR VÀ DESKTOP NẾU LÀ CÁC APP KHÁC
      if class_name in ["Shell_TrayWnd", "Progman", "WorkerW"]:
        return

      # 3. SO SÁNH TIÊU ĐỀ CỬA SỔ
      title = win32gui.GetWindowText(hwnd).lower()
      if title and clean_app in title:
        found_hwnds.append(hwnd)
        return

      # 4. SO SÁNH TÊN PROCESS (Bỏ qua explorer.exe để không đụng vào Taskbar)
      try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        proc_name = proc.name().lower()

        if proc_name != "explorer.exe" and clean_app in proc_name:
          found_hwnds.append(hwnd)
      except Exception:
        pass

  win32gui.EnumWindows(enum_windows_callback, None)
  return found_hwnds

  def enum_windows_callback(hwnd, extra):
    if win32gui.IsWindowVisible(hwnd):
      title = win32gui.GetWindowText(hwnd).lower()

      # 1. So sánh tên ứng dụng nằm trong Tiêu đề cửa sổ
      if title and clean_app in title:
        found_hwnds.append(hwnd)
        return

      # 2. So sánh với tên Tiến trình (Process Name - VD: chrome.exe, spotify.exe)
      try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        if clean_app in proc.name().lower():
          found_hwnds.append(hwnd)
      except Exception:
        pass

  win32gui.EnumWindows(enum_windows_callback, None)
  return found_hwnds


# ==================== 3 CHỨC NĂNG CHÍNH ====================


def minimize_window(target_app=None):
  """THU NHỎ CỬA SỔ (App cụ thể hoặc Cửa sổ hiện tại)."""
  try:
    if target_app and target_app.strip():
      hwnds = _find_hwnds_by_app_name(target_app)
      if hwnds:
        for hwnd in hwnds:
          win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        return f"Đã thu nhỏ cửa sổ {target_app} rồi sếp!"
      return f"Em không tìm thấy cửa sổ nào của {target_app} đang mở sếp ơi."
    else:
      hwnd = win32gui.GetForegroundWindow()
      if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        return "Đã thu nhỏ cửa sổ hiện tại rồi sếp!"
      return "Không có cửa sổ nào đang mở sếp ơi."
  except Exception as e:
    print(f"⚠️ Lỗi thu nhỏ cửa sổ: {e}")
    return "Em gặp lỗi khi thu nhỏ cửa sổ rồi sếp."


def maximize_window(target_app=None):
  """PHÓNG TO CỬA SỔ (App cụ thể hoặc Cửa sổ hiện tại)."""
  try:
    if target_app and target_app.strip():
      hwnds = _find_hwnds_by_app_name(target_app)
      if hwnds:
        for hwnd in hwnds:
          win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
          try:
            win32gui.SetForegroundWindow(hwnd)
          except Exception:
            pass
        return f"Đã phóng to cửa sổ {target_app} rồi sếp!"
      return f"Em không tìm thấy cửa sổ nào của {target_app} đang mở sếp ơi."
    else:
      hwnd = win32gui.GetForegroundWindow()
      if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        return "Đã phóng to cửa sổ hiện tại rồi sếp!"
      return "Không có cửa sổ nào đang mở sếp ơi."
  except Exception as e:
    print(f"⚠️ Lỗi phóng to cửa sổ: {e}")
    return "Em gặp lỗi khi phóng to cửa sổ rồi sếp."

# ==================== HÀM ĐIỀU HƯỚNG BẮT CÂU LỆNH ====================


def handle_window_command(text):
  """Hàm nhận diện giọng nói và gọi đúng chức năng tương ứng."""
  text = text.lower().strip()

  # 1. BẮT LỆNH THU NHỎ
  if any(kw in text for kw in ["thu nhỏ", "ẩn cửa sổ", "minimize"]):
    clean_target = text
    for kw in [
        "thu nhỏ",
        "ẩn cửa sổ",
        "cửa sổ",
        "cho em",
        "giùm",
        "hộ",
        "xuống",
        "minimize",
        "app",
        "ứng dụng",
    ]:
      clean_target = clean_target.replace(kw, "").strip()
    target_app = clean_target if clean_target else None
    return minimize_window(target_app)

  # 2. BẮT LỆNH PHÓNG TO
  elif any(kw in text for kw in ["phóng to", "mở to", "to màn hình", "maximize"]):
    clean_target = text
    for kw in [
        "phóng to",
        "mở to",
        "cửa sổ",
        "cho em",
        "giùm",
        "hộ",
        "lên",
        "maximize",
        "to màn hình",
        "app",
        "ứng dụng",
    ]:
      clean_target = clean_target.replace(kw, "").strip()
    target_app = clean_target if clean_target else None
    return maximize_window(target_app)

  return None