import os
import docx  # Xử lý Word (.docx)
import pymupdf  # Xử lý PDF
import pyperclip
from pptx import Presentation  # Xử lý PowerPoint (.pptx)

SUPPORTED_EXTENSIONS = (
    ".pdf",
    ".docx",
    ".pptx",
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".log",
)


def get_any_file_path(filename_hint: str = "") -> str:
  print("🔍 [FILE] Đang quét tìm file tài liệu...")

  clean_hint = (
      filename_hint.lower()
      .replace("tóm tắt", "")
      .replace("file", "")
      .replace("pdf", "")
      .replace("word", "")
      .replace("powerpoint", "")
      .replace("ppt", "")
      .replace("đọc", "")
      .replace("cho sếp", "")
      .strip()
  )

  # 1. Kiểm tra Clipboard
  try:
    clip_text = pyperclip.paste().strip().strip('"')
    if clip_text.lower().endswith(SUPPORTED_EXTENSIONS) and os.path.exists(
        clip_text
    ):
      if not os.path.basename(clip_text).startswith("Tom_Tat_"):
        print(f"📌 [FILE] Tìm thấy đường dẫn từ Clipboard: {clip_text}")
        return clip_text
  except Exception as e:
    print(f"⚠️ [FILE] Không đọc được Clipboard: {e}")

  search_folders = [
      os.path.expanduser("~/Desktop"),
      os.path.expanduser("~/Downloads"),
  ]

  # 2. Tìm theo từ khóa trong tên file
  if clean_hint:
    for folder in search_folders:
      if os.path.exists(folder):
        for file in os.listdir(folder):
          if (
              clean_hint in file.lower()
              and file.lower().endswith(SUPPORTED_EXTENSIONS)
              and not file.startswith("Tom_Tat_")
          ):  # 🔥 Bỏ qua file tóm tắt cũ
            target = os.path.join(folder, file)
            print(f"📌 [FILE] Tìm thấy file theo tên: {target}")
            return target

  # 3. Lấy file MỚI NHẤT trong Desktop/Downloads (loại trừ các file Tom_Tat_)
  latest_file = None
  latest_time = 0
  for folder in search_folders:
    if os.path.exists(folder):
      for file in os.listdir(folder):
        # 🔥 Không quét các file tóm tắt do JARVIS tạo ra
        if file.lower().endswith(
            SUPPORTED_EXTENSIONS
        ) and not file.startswith("Tom_Tat_"):
          full_path = os.path.join(folder, file)
          mtime = os.path.getmtime(full_path)
          if mtime > latest_time:
            latest_time = mtime
            latest_file = full_path

  if latest_file:
    print(f"📌 [FILE] Chọn file tài liệu mới nhất: {latest_file}")
  return latest_file


def extract_text_from_file(file_path: str) -> str:
  """Trích xuất toàn bộ chữ từ các định dạng PDF, DOCX, PPTX, TXT..."""
  ext = os.path.splitext(file_path)[1].lower()
  text = ""

  try:
    print(
        f"📖 [FILE] Đang đọc nội dung ({ext}): {os.path.basename(file_path)}..."
    )

    # 1. File PDF
    if ext == ".pdf":
      doc = pymupdf.open(file_path)
      for page in doc:
        text += page.get_text() + "\n"

    # 2. File Word (.docx)
    elif ext == ".docx":
      doc = docx.Document(file_path)
      for paragraph in doc.paragraphs:
        if paragraph.text.strip():
          text += paragraph.text + "\n"
      for table in doc.tables:
        for row in table.rows:
          for cell in row.cells:
            if cell.text.strip():
              text += cell.text + " "
          text += "\n"

    # 3. File PowerPoint (.pptx)
    elif ext == ".pptx":
      prs = Presentation(file_path)
      for slide_idx, slide in enumerate(prs.slides, 1):
        slide_text = []
        for shape in slide.shapes:
          if shape.has_text_frame:
            for paragraph in shape.text_frame.paragraphs:
              if paragraph.text.strip():
                slide_text.append(paragraph.text)
        if slide_text:
          text += f"[Trang {slide_idx}]: " + " ".join(slide_text) + "\n"

    # 4. Các file văn bản thuần (.txt, .md, .csv, .json, .log)
    elif ext in (".txt", ".md", ".csv", ".json", ".log"):
      for enc in ["utf-8", "utf-8-sig", "utf-16", "cp1252"]:
        try:
          with open(file_path, "r", encoding=enc) as f:
            text = f.read()
            break
        except (UnicodeDecodeError, Exception):
          continue

    print(
        f"✅ [FILE] Đã trích xuất {len(text.strip())} ký tự chữ thành công!"
    )
    return text.strip()

  except Exception as e:
    print(f"❌ Lỗi đọc file {file_path}: {e}")
    return ""