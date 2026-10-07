import json
import re
import subprocess


def get_last_app_crash():
  """Đọc Windows Event Viewer (Log Application - Event ID 1000)

  để tìm vết ứng dụng bị văng/crash mới nhất.
  """
  # Câu lệnh PowerShell quét lấy 1 event crash gần nhất trong hệ thống
  ps_script = """
    Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000} -MaxEvents 1 | 
    Select-Object TimeCreated, Message | 
    ConvertTo-Json
    """
  try:
    result = subprocess.run(
        ["powershell", "-Command", ps_script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    if result.returncode == 0 and result.stdout.strip():
      data = json.loads(result.stdout)

      if isinstance(data, list) and len(data) > 0:
        data = data[0]

      message = data.get("Message", "")

      # Regex bóc tách Tên App, Thư viện .dll gây ra crash và Mã lỗi
      app_match = re.search(
          r"Faulting application name:\s*([^\r\n,]+)", message, re.I
      )
      module_match = re.search(
          r"Faulting module name:\s*([^\r\n,]+)", message, re.I
      )
      code_match = re.search(
          r"Exception code:\s*([^\r\n,]+)", message, re.I
      )

      app_name = (
          app_match.group(1).strip()
          if app_match
          else "Ứng dụng không xác định"
      )
      module_name = (
          module_match.group(1).strip() if module_match else "không rõ file"
      )
      exception_code = (
          code_match.group(1).strip() if code_match else "không rõ"
      )

      return (
          f"Theo nhật ký Windows Event Viewer, vụ crash gần đây nhất là do"
          f" ứng dụng {app_name} gặp sự cố ở file {module_name} (Mã lỗi:"
          f" {exception_code}) sếp ạ."
      )
    else:
      return (
          "Em kiểm tra nhật ký hệ thống thì thấy không có ứng dụng nào bị văng"
          " hay crash gần đây sếp ạ."
      )

  except Exception as e:
    print(f"Lỗi đọc Event Viewer: {e}")
    return "Em gặp lỗi khi mở nhật ký sự kiện Event Viewer của Windows rồi sếp ơi."


def execute_diagnostics_command(user_text):
  """Hàm bắt các câu hỏi về Crash / Bắt bệnh ứng dụng"""
  text = user_text.lower().strip()

  keywords = [
      "sao bị văng",
      "tại sao bị văng",
      "sao văng game",
      "sao văng app",
      "xem crash",
      "kiểm tra crash",
      "lỗi văng",
      "kiểm tra lỗi",
      "sao đơ",
      "sao bị đơ",
      "nhật ký lỗi",
      "event viewer",
      "bị crash",
      "sao tắt ứng dụng",
  ]

  if any(kw in text for kw in keywords):
    return get_last_app_crash()

  return None