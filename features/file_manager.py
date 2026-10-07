import os
import subprocess
from send2trash import send2trash
import re
import shutil
import stat
from pathlib import Path

# Bảng ánh xạ thư mục hệ thống & Ổ đĩa
SYSTEM_FOLDERS = {
    "download": os.path.expanduser("~/Downloads"),
    "downloads": os.path.expanduser("~/Downloads"),
    "tải về": os.path.expanduser("~/Downloads"),
    "desktop": os.path.expanduser("~/Desktop"),
    "màn hình chính": os.path.expanduser("~/Desktop"),
    "document": os.path.expanduser("~/Documents"),
    "documents": os.path.expanduser("~/Documents"),
    "tài liệu": os.path.expanduser("~/Documents"),
    "picture": os.path.expanduser("~/Pictures"),
    "pictures": os.path.expanduser("~/Pictures"),
    "hình ảnh": os.path.expanduser("~/Pictures"),
    "ảnh": os.path.expanduser("~/Pictures"),
    "music": os.path.expanduser("~/Music"),
    "nhạc": os.path.expanduser("~/Music"),
    "c": "C:\\",
    "ổ c": "C:\\",
    "ổ đĩa c": "C:\\",
    "d": "D:\\",
    "ổ d": "D:\\",
    "ổ đĩa d": "D:\\",
}


def handle_folder_command(user_input):
  """Bắt trọn mọi câu lệnh chứa 'folder', 'thư mục', 'tệp'.

  Nếu không thấy folder thì thông báo ngay, tuyệt đối không cho lọt ra ngoài mở
  Edge.
  """
  text_lower = user_input.lower().strip()

  # 1. BỘ LỌC Ý ĐỊNH
  folder_keywords = ["folder", "thư mục", "tệp", "mục"]
  is_folder_intent = any(kw in text_lower for kw in folder_keywords)

  # Nếu không phải lệnh folder thì nhường cho các chức năng khác
  if not is_folder_intent and not text_lower.startswith("mở ổ"):
    return None

  # 2. GỌT SẠCH TỪ RÁC ĐỂ TRÍCH XUẤT TÊN FOLDER
  noise_words = [
      "mở",
      "thư mục",
      "folder",
      "tệp",
      "file",
      "xem",
      "mục",
      "ổ đĩa",
      "ổ",
  ]
  clean_name = text_lower
  for kw in noise_words:
    clean_name = re.sub(r"\b" + re.escape(kw) + r"\b", "", clean_name).strip()

  # 3. NẾU NÓI TRỐNG KHÔNG ("mở folder", "mở tệp", "mở thư mục") -> BẬT FILE EXPLORER
  if not clean_name:
    subprocess.Popen(["explorer"])
    return "Đã mở File Explorer cho sếp!"

  # 4. TRA CỨU BẢNG ÁNH XẠ HỆ THỐNG & Ổ ĐĨA
  SYSTEM_MAP = {
        "download": os.path.expanduser("~/Downloads"),
        "downloads": os.path.expanduser("~/Downloads"),
        "tải về": os.path.expanduser("~/Downloads"),
        "đao loát": os.path.expanduser("~/Downloads"),  # Bắt thêm trường hợp giọng nói nhận diện nhầm
        "tài liệu": os.path.expanduser("~/Documents"),
        "document": os.path.expanduser("~/Documents"),
        "documents": os.path.expanduser("~/Documents"),
        "màn hình chính": os.path.expanduser("~/Desktop"),
        "desktop": os.path.expanduser("~/Desktop"),
        "c": "C:\\",
        "d": "D:\\",
        "e": "E:\\",
    }

  target_path = None
  if clean_name in SYSTEM_MAP:
    target_path = SYSTEM_MAP[clean_name]

  # 5. QUÉT TÌM FOLDER TRÊN CÁC Ổ ĐĨA & THƯ MỤC CÁ NHÂN
  if not target_path:
    search_roots = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Documents"),
        "C:\\",
        "D:\\",
    ]
    for root in search_roots:
      if not os.path.exists(root):
        continue
      try:
        for item in os.listdir(root):
          item_path = os.path.join(root, item)
          # Bắt buộc phải là THƯ MỤC (isdir) và tên có chứa từ khóa sếp đọc
          if os.path.isdir(item_path) and clean_name in item.lower():
            target_path = item_path
            break
      except Exception:
        continue
      if target_path:
        break

  # 6. THỰC THI MỞ FOLDER NẾU TÌM THẤY
  if target_path and os.path.exists(target_path):
    norm_path = os.path.normpath(target_path)
    subprocess.Popen(["explorer", norm_path])
    return f"Đã mở thư mục {clean_name} cho sếp!"

  # 7. LÁ CHẮN AN TOÀN: Nếu đúng là lệnh Mở Folder nhưng không tìm thấy Folder trên máy,
  # Trả về câu thông báo ngay để KHÔNG LỌT LỆNH sang trình duyệt Edge hay App khác!
  return (
      f"Em xác nhận lệnh mở thư mục '{clean_name}', nhưng không tìm thấy"
      " folder này trên máy sếp ạ."
  )

def clean_downloads_folder():
  """Chuyển tất cả file và thư mục trong Downloads vào Thùng rác (Recycle Bin)."""
  try:
    # Lấy đường dẫn Downloads chuẩn
    downloads_path = Path.home() / "Downloads"

    if not downloads_path.exists():
      return "Em không tìm thấy thư mục Downloads trên máy tính sếp ơi!"

    moved_count = 0
    failed_count = 0

    for item in downloads_path.iterdir():
      try:
        # 🔥 Chuyển vào Thùng rác (Recycle Bin) chứ KHÔNG xóa vĩnh viễn
        send2trash(str(item))
        moved_count += 1
      except Exception as e:
        # File đang được mở/sử dụng bởi phần mềm khác -> Bỏ qua
        failed_count += 1

    if moved_count == 0 and failed_count == 0:
      return "Thư mục Downloads đang trống sẵn rồi sếp ơi!"

    msg = (
        f"Đã chuyển {moved_count} mục trong Downloads vào Thùng rác an"
        " toàn rồi sếp!"
    )
    if failed_count > 0:
      msg += (
          f" (Còn {failed_count} file đang mở nên chưa chuyển vào thùng rác"
          " được)."
      )

    return msg

  except Exception as e:
    print(f"⚠️ Lỗi khi chuyển Downloads vào thùng rác: {e}")
    return "Em gặp lỗi khi dọn dẹp thư mục Downloads rồi sếp ơi."


def delete_item(item_name):
  """Xóa thư mục hoặc file (Tự động khớp đuôi file, chuẩn hóa đường dẫn và đưa vào Thùng rác)"""
  clean_name = item_name.lower().strip()
  search_dirs = [
      os.path.expanduser("~/Desktop"),
      os.path.expanduser("~/Downloads"),
  ]

  target_to_delete = None

  # 1. Tìm file/thư mục khớp tên trên Desktop hoặc Downloads
  for s_dir in search_dirs:
    if not os.path.exists(s_dir):
      continue

    # Kiểm tra đường dẫn trực tiếp trước
    direct_path = os.path.join(s_dir, clean_name)
    if os.path.exists(direct_path):
      target_to_delete = direct_path
      break

    # Quét tìm file khớp tên không tính đuôi (.txt, .docx, .png...)
    for filename in os.listdir(s_dir):
      name_without_ext, _ = os.path.splitext(filename.lower())
      if filename.lower() == clean_name or name_without_ext == clean_name:
        target_to_delete = os.path.join(s_dir, filename)
        break
    if target_to_delete:
      break

  # 2. Xử lý xóa an toàn
  if target_to_delete:
    # Chuẩn hóa đường dẫn tuyệt đối cho Windows
    target_to_delete = os.path.normpath(os.path.abspath(target_to_delete))
    found_name = os.path.basename(target_to_delete)

    try:
      # Bỏ thuộc tính Read-Only nếu có
      os.chmod(target_to_delete, stat.S_IWRITE)

      # Đưa vào Thùng rác
      send2trash(target_to_delete)
      return f"Đã chuyển file '{found_name}' vào Thùng rác cho sếp rồi ạ!"

    except PermissionError:
      return (
          f"Sếp ơi, file '{found_name}' đang được mở trong chương trình khác"
          " (như Notepad/VS Code). Sếp đóng file đó lại rồi bảo em xóa lại"
          " nhé!"
      )
    except Exception as e:
      # Fallback: Nếu send2trash bị lỗi thư viện, thử xóa trực tiếp
      try:
        if os.path.isdir(target_to_delete):
          shutil.rmtree(target_to_delete)
        else:
          os.remove(target_to_delete)
        return f"Đã xóa file '{found_name}' cho sếp rồi ạ!"
      except Exception as err:
        return f"Em không thể xóa file '{found_name}' được. Lỗi hệ thống: {err}"

  return (
      f"Em không tìm thấy file hoặc thư mục tên là '{item_name}' trên Màn hình"
      " chính hay Downloads để xóa ạ."
  )


def search_file(file_keyword, search_dir=None):
  """Tìm kiếm file theo từ khóa và bôi đen trong File Explorer"""
  if not search_dir:
    search_dir = os.path.expanduser("~/Downloads")

  found_files = []
  try:
    for root, dirs, files in os.walk(search_dir):
      for file in files:
        if file_keyword.lower() in file.lower():
          found_files.append(os.path.join(root, file))
          if len(found_files) >= 3:
            break
      if len(found_files) >= 3:
        break

    if found_files:
      first_file = found_files[0]
      subprocess.run(f'explorer /select,"{first_file}"', shell=True)
      return (
          f"Em đã tìm thấy file {os.path.basename(first_file)} cho sếp rồi đây!"
      )
  except Exception as e:
    print(f"Lỗi tìm file: {e}")

  return f"Em không tìm thấy file nào chứa từ khóa '{file_keyword}' sếp ạ."


def create_new_folder(folder_name, base_path=None):
  """Tạo thư mục mới trên Màn hình chính (Desktop)"""
  if not base_path:
    base_path = os.path.expanduser("~/Desktop")

  full_path = os.path.join(base_path, folder_name)
  try:
    os.makedirs(full_path, exist_ok=True)
    return f"Đã tạo thư mục mới tên là {folder_name} trên Màn hình chính!"
  except Exception as e:
    return f"Không thể tạo thư mục, lỗi: {e}"


def empty_recycle_bin():
  """Dọn sạch Thùng Rác Windows"""
  try:
    import ctypes

    ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
    return "Đã dọn sạch Thùng Rác cho sếp rồi ạ!"
  except Exception:
    return "Em không dọn Thùng Rác được rồi sếp ơi."


def execute_file_command(user_text):
  """Hàm điều phối các lệnh Quản lý File"""
  folder_res = handle_folder_command(user_text)
  if folder_res:
    return folder_res
  text = user_text.lower().strip()

  # 1. MỞ THƯ MỤC / Ổ ĐĨA
  if any(
      kw in text
      for kw in [
          "mở thư mục",
          "mở ổ đĩa",
          "mở ổ",
          "vào thư mục",
          "vào ổ đĩa",
          "vào ổ",
      ]
  ):
    folder = text
    for kw in [
        "mở thư mục",
        "mở ổ đĩa",
        "mở ổ",
        "vào thư mục",
        "vào ổ đĩa",
        "vào ổ",
    ]:
      folder = folder.replace(kw, "")
    return handle_folder_command(folder.strip())

  # 2. XÓA THƯ MỤC / XÓA FILE
  if any(
      kw in text
      for kw in [
          "xóa thư mục",
          "xóa file",
          "xóa tập tin",
          "bỏ thư mục",
          "xóa folder",
      ]
  ):
    item = text
    for kw in [
        "xóa thư mục",
        "xóa file",
        "xóa tập tin",
        "bỏ thư mục",
        "xóa folder",
        "tên là",
        "có tên",
    ]:
      item = item.replace(kw, "")
    if item.strip():
      return delete_item(item.strip())

  # 3. TẠO THƯ MỤC MỚI
  if "tạo thư mục mới" in text or "tạo thư mục" in text:
    f_name = (
        text.replace("tạo thư mục mới", "")
        .replace("tạo thư mục", "")
        .replace("tên là", "")
        .strip()
    )
    return create_new_folder(f_name if f_name else "Thư mục mới")

  # 4. TÌM FILE
  if any(kw in text for kw in ["tìm file", "tìm tập tin", "tìm báo cáo"]):
    kw_file = text
    for kw in ["tìm file", "tìm tập tin", "tìm báo cáo", "về", "có tên"]:
      kw_file = kw_file.replace(kw, "")
    return search_file(kw_file.strip())

  # 5. DỌN THÙNG RÁC
  if "dọn thùng rác" in text or "xóa thùng rác" in text or "dọn sạch thùng rác" in text or "xóa sạch thùng rác" in text or "làm rỗng thùng rác" in text or "làm sạch thùng rác" in text:
    return empty_recycle_bin()

  return None