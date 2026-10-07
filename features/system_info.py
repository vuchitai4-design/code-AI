import psutil
import pyautogui
try:
  import speedtest
except Exception:
  speedtest = None

# Bọc try-except cho GPUtil để tránh sập toàn bộ chương trình
try:
  import GPUtil
except Exception:
  GPUtil = None


# ================= 1. BÁO CÁO CẤU HÌNH HỆ THỐNG =================
def get_system_status():
  """Báo cáo chi tiết CPU, RAM, Ổ C, Pin, GPU và Nhiệt độ."""
  # CPU
  cpu_usage = psutil.cpu_percent(interval=0.5)

  # Nhiệt độ CPU
  cpu_temp_str = ""
  try:
    temps = psutil.sensors_temperatures()
    if temps and "coretemp" in temps:
      cpu_temp_str = f", Nhiệt độ {temps['coretemp'][0].current}°C"
  except Exception:
    pass

  # RAM
  ram = psutil.virtual_memory()
  ram_usage = ram.percent
  ram_used_gb = round(ram.used / (1024**3), 1)
  ram_total_gb = round(ram.total / (1024**3), 1)

  # Dung lượng ổ C
  try:
    disk_c = psutil.disk_usage("C:\\")
    disk_free = round(disk_c.free / (1024**3), 1)
    disk_total = round(disk_c.total / (1024**3), 1)
    disk_str = f"Ổ C còn trống {disk_free} GB trên tổng {disk_total} GB"
  except Exception:
    disk_str = "Không quét được ổ C"

  # PIN
  battery = psutil.sensors_battery()
  if battery:
    plugged = "Đang sạc" if battery.power_plugged else "Đang dùng pin"
    bat_str = f"Pin còn {battery.percent}% ({plugged})"
  else:
    bat_str = "Máy bàn (Không có pin)"

  # GPU (Xử lý an toàn)
  gpu_str = "GPU: Không quét được"
  if GPUtil:
    try:
      gpus = GPUtil.getGPUs()
      if gpus:
        gpu = gpus[0]
        gpu_str = (
            f"GPU {gpu.name}: Dùng {int(gpu.load * 100)}%, Nhiệt độ"
            f" {gpu.temperature}°C"
        )
      else:
        gpu_str = "GPU: Đang rảnh / Onboard"
    except Exception:
      pass

  return (
      f"Tình trạng máy hiện tại:\n"
      f"• CPU: Sử dụng {cpu_usage}%{cpu_temp_str}\n"
      f"• RAM: Sử dụng {ram_usage}% ({ram_used_gb}/{ram_total_gb} GB)\n"
      f"• Dung lượng: {disk_str}\n"
      f"• {bat_str}\n"
      f"• {gpu_str}"
  )


# ================= 2. KIỂM TRA TỐC ĐỘ MẠNG / WIFI =================
def check_network_speed():
  """Đo Ping, Tốc độ Tải về (Download) và Tải lên (Upload)."""
  print("⏳ Đang đo tốc độ mạng, sếp chờ khoảng 10-15 giây...")
  if speedtest is None:
    return (
        "Không thể đo tốc độ mạng lúc này. Sếp kiểm tra lại kết nối Wifi nhé!"
    )
  try:
    st = speedtest.Speedtest()
    st.get_best_server()

    ping = round(st.results.ping, 1)
    download = round(st.download() / 1_000_000, 1)  # Đổi sang Mbps
    upload = round(st.upload() / 1_000_000, 1)  # Đổi sang Mbps

    return (
        f"Tình trạng đường truyền mạng:\n"
        f"• Độ trễ (Ping): {ping} ms\n"
        f"• Tốc độ Download: {download} Mbps\n"
        f"• Tốc độ Upload: {upload} Mbps"
    )
  except Exception as e:
    return (
        "Không thể đo tốc độ mạng lúc này. Sếp kiểm tra lại kết nối Wifi nhé!"
    )
