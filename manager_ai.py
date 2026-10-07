"""MODULE: manager_ai.py

MÔ TẢ: Bộ điều phối AI tự động chuyển đổi giữa Lite AI (khi chơi game)
và Router phân loại model Groq (Qwen 3.8 27B vs GPT-OSS 120B).
"""

import re
from lite_ai import LiteAI


class AIModelRouter:

  def __init__(self, groq_client):
    self.client = groq_client
    self.MODEL_STANDARD = "qwen/qwen3.8-27b"
    self.MODEL_HEAVY = "openai/gpt-oss-120b"

    # Pattern nhận diện tác vụ cần suy luận / phân tích sâu
    self.HEAVY_PATTERNS = [
        r"phân tích (sâu|chi tiết|toàn diện|lỗ hổng|rủi ro)",
        r"tối ưu (kiến trúc|mã nguồn|code|thuật toán|sql)",
        r"đánh giá (ưu nhược điểm|chiến lược|mô hình)",
        r"suy luận (logic|đa bước|toán học)",
        r"thiết kế (hệ thống|cơ sở dữ liệu|db|schema)",
        r"refactor",
        r"debug",
        r"so sánh sâu",
    ]

  def select_model(self, prompt: str) -> str:
    """Tự động phân tích câu lệnh để chọn model phù hợp."""
    prompt_lower = prompt.lower().strip()

    # 1. Văn bản quá dài (> 1200 ký tự) -> GPT-OSS-120B
    if len(prompt) > 1200:
      print("🎯 [ROUTER] Chuyển sang GPT-OSS-120B (Độ dài văn bản > 1200 ký tự)")
      return self.MODEL_HEAVY

    # 2. Chứa từ khóa phân tích phức tạp -> GPT-OSS-120B
    for pattern in self.HEAVY_PATTERNS:
      if re.search(pattern, prompt_lower):
        print(
            f"🎯 [ROUTER] Chuyển sang GPT-OSS-120B (Phát hiện từ khóa:"
            f" '{pattern}')"
        )
        return self.MODEL_HEAVY

    # 3. Mặc định -> Qwen3.8-27b (Phản hồi nhanh, giao tiếp chuẩn)
    print("🎯 [ROUTER] Sử dụng Qwen3.8-27B (Tác vụ tiêu chuẩn)")
    return self.MODEL_STANDARD


class AIManager:

  def __init__(self, groq_client, boss_name="Sếp"):
    self.groq_client = groq_client
    self.lite_ai = LiteAI(boss_name=boss_name)
    self.router = AIModelRouter(groq_client)
    self.current_mode = "GROQ"  # "GROQ" hoặc "LITE"

  def ask(
      self,
      user_command: str,
      is_game_running: bool,
      chat_history: list,
      speak_func,
      ask_groq_func,
  ):
    """Tự động điều phối yêu cầu người dùng tới đúng Module AI dựa trên trạng thái Game và độ phức tạp."""
    if is_game_running:
      # 🟢 PHÁT HIỆN GAME -> DÙNG LITE AI (OFFLINE)
      if self.current_mode != "LITE":
        print(
            "🎮 [AI MANAGER] Phát hiện Game -> Kích hoạt Lite AI (Offline"
            " Mode)!"
        )
        self.current_mode = "LITE"

      response = self.lite_ai.process_command(user_command)
      speak_func(response)

    else:
      # 🔴 TẮT GAME / KHÔNG GAME -> DÙNG GROQ CLOUD
      if self.current_mode != "GROQ":
        print(
            "🟢 [AI MANAGER] Đã thoát Game -> Kích hoạt lại GROQ AI"
            " (Cloud Stream Mode)!"
        )
        self.current_mode = "GROQ"

      # Tự động chọn model tối ưu dựa trên độ phức tạp
      chosen_model = self.router.select_model(user_command)

      # Truyền model đã chọn vào hàm ask_groq_func
      ask_groq_func(user_command, chat_history, target_model=chosen_model)

      chat_history.append({"role": "user", "content": user_command})
      if len(chat_history) > 4:
        chat_history.pop(0)