from pathlib import Path
import sys

# ==================== FIX IMPORT TỪ THƯ MỤC GỐC JARVIS-V3 ====================
FILE = Path(__file__).resolve()
# FILE.parents[1] nghĩa là lùi lại 1 cấp thư mục (VD: JARVIS-V3/features/clipboard_control.py -> JARVIS-V3)
ROOT = FILE.parents[1]
if str(ROOT) not in sys.path:
  sys.path.append(str(ROOT))

# ==================== IMPORT CLIENT TỪ CONFIG.PY ====================
from config import client  # 🔥 Gọi client từ file config.py ở gốc
import pyperclip

def ask_groq_for_clipboard(prompt):
  """Hàm gọi Groq dành riêng cho Clipboard (chỉ nhận 1 prompt và trả về chuỗi văn bản)."""
  try:
    completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": (
                    "Bạn là một trợ lý dịch thuật và tóm tắt văn bản chính"
                    " xác, tự nhiên."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=800,
    )
    return completion.choices[0].message.content
  except Exception as e:
    print(f"⚠️ Lỗi Groq Clipboard: {e}")
    return "Em gặp lỗi khi xử lý dữ liệu clipboard bằng Groq rồi sếp ơi."
  
# ==================== ĐỌC CLIPBOARD ====================


def get_clipboard_text():
  """Lấy đoạn văn bản sếp vừa Ctrl + C."""
  try:
    text = pyperclip.paste()
    if not text or not text.strip():
      return None, "Bộ nhớ tạm (Clipboard) đang trống sếp ơi."
    return text.strip(), None
  except Exception as e:
    return None, f"Không thể đọc Clipboard: {e}"


# ==================== XỬ LÝ LỆNH CLIPBOARD ====================


def handle_clipboard_command(command_text, ai_process_func):
  """Hàm nhận diện lệnh clipboard.

  - Tự động nhận diện ngôn ngữ (Anh, Trung, Pháp, Ý...) và dịch sang Tiếng
  Việt.
  """
  cmd = command_text.lower().strip()
  content, err = get_clipboard_text()

  if err:
    return err

  # 1. DỊCH CLIPBOARD (TỰ ĐỘNG NHẬN DIỆN NGÔN NGỮ -> TIẾNG VIỆT)
  if any(kw in cmd for kw in ["dịch", "translate"]):
    prompt = f"""Hãy tự động nhận diện ngôn ngữ của đoạn văn bản sau (Ví dụ: Tiếng Anh, Tiếng Trung, Tiếng Pháp, Tiếng Ý...) và dịch toàn bộ nội dung sang Tiếng Việt một cách tự nhiên, chuẩn ngữ cảnh nhất.

Định dạng trả lời gọn gàng:
🌐 [Tên Ngôn Ngữ Phát Hiện Được]:
[Nội dung dịch sang Tiếng Việt]

Văn bản cần dịch:
{content}"""

    return ai_process_func(prompt)

  # 2. TÓM TẮT CLIPBOARD
  elif any(kw in cmd for kw in ["tóm tắt", "tóm gọn", "rút gọn"]):
    prompt = (
        f"Hãy tóm tắt ngắn gọn, rõ ràng văn bản sau đây trong 3-4 ý"
        f" chính:\n\n{content}"
    )
    return ai_process_func(prompt)

  # 3. ĐỌC CLIPBOARD
  elif any(
      kw in cmd
      for kw in ["đọc clipboard", "đọc bộ nhớ tạm", "đọc văn bản vừa copy"]
  ):
    if len(content) > 300:
      return (
          f"Nội dung clipboard khá dài, em đọc trước đoạn đầu nhé:"
          f" {content[:200]}..."
      )
    return f"Nội dung trong clipboard là: {content}"

  return None