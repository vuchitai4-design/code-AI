"""
MODULE: lite_ai.py
MÔ TẢ: Module AI Siêu Nhẹ (Offline / Local Mode) dành riêng cho GAME MODE.
TÁC DỤNG:
- Xử lý các câu lệnh cơ bản (nhạc, giờ giấc, thông tin sếp, hệ thống) trực tiếp bằng Python.
- Không tiêu tốn CPU/RAM, không gọi API qua mạng (Zero Latency, Zero Network Usage).
- Phản hồi siêu nhanh (< 0.01s) để không ảnh hưởng đến FPS khi sếp chơi game.
"""

import datetime


class LiteAI:

  def __init__(self, boss_name="Sếp"):
    self.boss_name = boss_name

  def process_command(self, user_input: str) -> str:
    """Xử lý câu lệnh của sếp khi đang trong Game Mode."""
    if not user_input or not user_input.strip():
      return "Em nghe chưa rõ, sếp nói lại giúp em nhé!"

    cmd = user_input.lower().strip()

    # 1. HỎI GIỜ / NGÀY THÁNG
    if any(kw in cmd for kw in ["mấy giờ", "giờ mấy", "thời gian"]):
      now = datetime.datetime.now()
      return f"Báo cáo sếp, bây giờ là {now.hour} giờ {now.minute} phút ạ."

    if any(kw in cmd for kw in ["ngày mấy", "hôm nay ngày", "thứ mấy"]):
      now = datetime.datetime.now()
      days = [
          "Thứ Hai",
          "Thứ Ba",
          "Thứ Tư",
          "Thứ Năm",
          "Thứ Sáu",
          "Thứ Bảy",
          "Chủ Nhật",
      ]
      day_name = days[now.weekday()]
      return f"Hôm nay là {day_name}, ngày {now.day} tháng {now.month} năm {now.year} thưa sếp."

    # 2. THÔNG TIN SẾP
    if any(
        kw in cmd
        for kw in ["sếp là ai", "sếp tên gì", "tôi là ai", "thông tin sếp"]
    ):
      return (
          f"Sếp là {self.boss_name}, người đẹp trai và đỉnh cao nhất mà em"
          " từng phục vụ!"
      )

    # 3. TRẠNG THÁI GAME MODE
    if any(kw in cmd for kw in ["bạn là ai", "ai đấy", "chế độ gì"]):
      return (
          "Em là JARVIS phiên bản Lite AI tối ưu cho Game Mode. Em chỉ nhận"
          " lệnh cơ bản để sếp chơi game mượt nhất!"
      )

    # 4. ĐIỀU KHIỂN ÂM NHẠC / ÂM LƯỢNG
    if any(kw in cmd for kw in ["bật nhạc", "mở nhạc", "phát nhạc"]):
      return "Đã mở nhạc cho sếp phiêu trong game nhé!"

    if any(kw in cmd for kw in ["tạm dừng", "dừng nhạc", "tắt nhạc", "stop"]):
      return "Đã tạm dừng nhạc rồi thưa sếp."

    if any(kw in cmd for kw in ["tăng âm lượng", "to lên", "bật to"]):
      return "Đã tăng âm lượng lên rồi ạ."

    if any(kw in cmd for kw in ["giảm âm lượng", "nhỏ lại", "vặn nhỏ"]):
      return "Đã giảm âm lượng cho sếp rồi ạ."

    # 5. CÂU HỎI PHỨC TẠP CẦN AI SUY NGHĨ (Từ chối khéo để tránh lag game)
    return (
        "Em đang chạy Lite AI trong Game Mode nên tạm khóa Groq AI nâng cao"
        " nhé sếp. Tắt game xong sếp hỏi lại em trả lời liền!"
    )