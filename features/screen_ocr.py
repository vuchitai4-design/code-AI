import os
import re
import time
import ctypes
from ctypes import wintypes
import torch
import easyocr
from PIL import Image, ImageGrab, ImageOps

# 1. Kích hoạt DPI Awareness chuẩn cho hệ thống đa màn hình (125% + 100%)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
DWMWA_EXTENDED_FRAME_BOUNDS = 9

def find_notepad_hwnd():
    """Tìm chính xác HWND cửa sổ Notepad bằng Class Name hệ thống bất chấp tiêu đề file là gì."""
    hwnds = []
    def enum_windows_callback(hwnd, extra):
        if user32.IsWindowVisible(hwnd):
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            if class_name.value.lower() == "notepad":
                hwnds.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
    return hwnds[0] if hwnds else None

def get_exact_window_bbox(hwnd):
    """Lấy tọa độ điểm ảnh chuẩn xác của Notepad qua DWM API (bỏ viền bóng mờ Win 11)."""
    rect = wintypes.RECT()
    dwmapi.DwmGetWindowAttribute(
        hwnd, 
        DWMWA_EXTENDED_FRAME_BOUNDS, 
        ctypes.byref(rect), 
        ctypes.sizeof(rect)
    )
    return (rect.left, rect.top, rect.right, rect.bottom)

reader = None

def get_ocr_reader():
    """Tự động nhận diện GPU RTX 3060 để chạy CUDA, tự lùi về CPU nếu không tìm thấy GPU."""
    global reader
    if reader is None:
        use_gpu = torch.cuda.is_available()
        gpu_status = "GPU (CUDA)" if use_gpu else "CPU"
        print(f"🔍 [OCR] Khởi tạo EasyOCR bằng {gpu_status}...")
        reader = easyocr.Reader(['vi', 'en'], gpu=use_gpu)
    return reader

def capture_screen_text(target_app_keyword: str = "notepad") -> tuple[str, str]:
    """Chụp chuẩn xác Notepad, đảo màu Dark Mode và gộp chữ thành 1 đoạn văn liền khối."""
    try:
        debug_path = "debug_notepad.png"
        inverted_path = "debug_notepad_inverted.png"

        # 1. Tìm đúng cửa sổ Notepad trên các màn hình
        hwnd = find_notepad_hwnd()
        if not hwnd:
            print("❌ [OCR] Không tìm thấy cửa sổ Notepad nào đang mở!")
            return "", ""

        # Lấy tiêu đề hiển thị thực tế
        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        app_title_found = buff.value or "Notepad"

        print(f"🎯 [OCR] Đã khóa cửa sổ Notepad: '{app_title_found}'")

        # 2. Đưa Notepad lên trên cùng màn hình
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
            time.sleep(0.2)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.3)

        # 3. Chụp đúng vùng Notepad theo tọa độ DWM
        bbox = get_exact_window_bbox(hwnd)
        screenshot = ImageGrab.grab(bbox=bbox, all_screens=True)
        screenshot.save(debug_path)

        # 4. Đảo màu ảnh xử lý Dark Mode (Chuyển nền đen chữ trắng -> nền trắng chữ đen)
        raw_img = Image.open(debug_path).convert('RGB')
        inverted_img = ImageOps.invert(raw_img)
        inverted_img.save(inverted_path)

        # 5. Đưa ảnh vào EasyOCR trích xuất chữ
        ocr = get_ocr_reader()
        results = ocr.readtext(inverted_path, detail=0)

        # 6. GỘP CHỮ THÀNH 1 ĐOẠN VĂN LIỀN MẠCH (Loại bỏ xuống dòng rác)
        raw_text = " ".join(results)
        extracted_text = re.sub(r'\s+', ' ', raw_text).strip()

        print(f"✅ [OCR] Đã trích xuất thành công {len(extracted_text)} ký tự:")
        print(f"----------------------------------------\n{extracted_text}\n----------------------------------------")
        
        return extracted_text, app_title_found

    except Exception as e:
        print(f"❌ [OCR ERROR]: {e}")
        return "", ""

if __name__ == "__main__":
    # Đoạn test chạy trực tiếp file
    capture_screen_text("notepad")