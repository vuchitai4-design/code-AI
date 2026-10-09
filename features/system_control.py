import json
import os
import re
import subprocess
import time
import urllib.parse
import webbrowser
from ddgs import DDGS
import gc
from bs4 import BeautifulSoup
import requests
import psutil
import pyautogui
import xml.etree.ElementTree as ET
import GPUtil
import sys
import win32com.client

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from features.app_diagnostic import execute_diagnostics_command
from features.file_manager import execute_file_command, clean_downloads_folder, handle_folder_command
from ctypes import POINTER, cast
from features.knowledge_engine import jarvis_knowledge_engine
import pythoncom
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume
import win32con
import win32gui
from features.audio_control import set_volume
from features.clipboard_control import handle_clipboard_command
from features.time_control import handle_timer_command
from features.system_info import get_system_status, check_network_speed
from features.clipboard_control import ask_groq_for_clipboard
from features.window_control import handle_window_command

try:
    from audio_control import ducked_sessions, is_ducked
except ImportError:
    ducked_sessions = {}
    is_ducked = False

try:
    from pytubefix import Search
except ImportError:
    Search = None

from features.zalo_call import (
    accept_zalo_call,
    reject_zalo_call,
)

USERNAME = os.getlogin()
OPERA_PATHS = [
    r"C:\Users\ADMINA\AppData\Local\Programs\Opera GX\launcher.exe",
    rf"C:\Users\{USERNAME}\AppData\Local\Programs\Opera GX\launcher.exe",
]

OPERA_EXEC = None
for path in OPERA_PATHS:
    if os.path.exists(path):
        OPERA_EXEC = path
        break

APPS_CACHE_FILE = "apps_cache.json"

# ==========================================
# BẢNG PRE-PROCESSING SỬA LỖI GIỌNG NÓI (STT)
# ==========================================
STT_CORRECTIONS = {
    "can va": "canva",
    "căn va": "canva",
    "cam ra": "camera",
    "pau ơ seo": "powershell",
    "bao ơ sell": "powershell",
    "power shell": "powershell",
    "window powershell": "powershell",
    "windows powershell": "powershell",
    "clip champ": "clipchamp",
    "clip time": "clipchamp",
    "click time": "clipchamp",
    "clip trang": "clipchamp",
    "clip xăm": "clipchamp",
    "cờ líp trang": "clipchamp",
    "cờ líp xăm": "clipchamp",
}


def normalize_speech_text(text: str) -> str:
  """Sửa lỗi nhận diện từ tiếng Anh phát âm sai sang từ chuẩn (Không phân biệt hoa thường)"""
  text = text.lower().strip()
  for wrong, correct in STT_CORRECTIONS.items():
    # Thêm re.IGNORECASE để đảm bảo bắt trúng 100% dù viết hoa hay thường
    text = re.sub(rf"\b{re.escape(wrong)}\b", correct, text, flags=re.IGNORECASE)
  return text

# ==========================================
# APP DATABASE DỰ PHÒNG CHUẨN
# ==========================================
APP_DATABASE = {
    "ppt": {
        "appid": "Microsoft.Office.POWERPNT.EXE.15",
        "exes": ["POWERPNT.EXE"],
        "aliases": ["powerpoint", "power point", "p p t", "presentation"]
    },
    "word": {
        "appid": "Microsoft.Office.WINWORD.EXE.15",
        "exes": ["WINWORD.EXE"],
        "aliases": ["winword", "microsoft word"]
    },
    "excel": {
        "appid": "Microsoft.Office.EXCEL.EXE.15",
        "exes": ["EXCEL.EXE"],
        "aliases": ["microsoft excel"]
    },
    "vs code": {
        "appid": "Microsoft.VisualStudioCode",
        "exes": ["Code.exe"],
        "aliases": ["vscode", "visual studio code", "code"]
    },
    "cmd": {
        "appid": r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\cmd.exe",
        "exes": ["cmd.exe"],
        "aliases": ["command prompt", "cửa sổ lệnh"]
    },
    "powershell": {
        "appid": r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe",
        "exes": ["powershell.exe", "pwsh.exe"],
        "aliases": ["windows powershell", "power shell"]
    },
    "chrome": {
        "appid": "Chrome",
        "exes": ["chrome.exe"],
        "aliases": ["google chrome"]
    },
    "opera": {
        "appid": "OperaSoftware.OperaGXWebBrowser.1784439916",
        "exes": ["opera.exe", "launcher.exe"],
        "aliases": ["opera gx", "trình duyệt opera"]
    },
    "zalo": {
        "appid": "com.vng.zalo",
        "exes": ["Zalo.exe"],
        "aliases": []
    },
    "máy tính": {
        "appid": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
        "exes": ["CalculatorApp.exe", "Calculator.exe"],
        "aliases": ["calculator", "máy tính tay"]
    },
    "notepad": {
        "appid": "Microsoft.WindowsNotepad_8wekyb3d8bbwe!App",
        "exes": ["Notepad.exe"],
        "aliases": ["ghi chú"]
    },
    "settings": {
        "appid": "windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel",
        "exes": ["SystemSettings.exe"],
        "aliases": ["cài đặt"]
    },
    "file explorer": {
        "appid": "Microsoft.Windows.Explorer",
        "exes": ["explorer.exe"],
        "aliases": ["thư mục", "explorer", "quản lý tệp"]
    },
    "clipchamp": {
        "appid": "Clipchamp.Clipchamp_8wekyb3d8bbwe!App",
        "exes": ["Clipchamp.exe"],
        "aliases": ["clipchamp", "clip trang", "trình chỉnh sửa video", "cắt video"]
    }
}

APP_PROCESS_MAP = {
    "access": ["MSACCESS.EXE"],
    "amd software": ["RadeonSoftware.exe", "AMDRadeonSoftware.exe"],
    "ảnh (photos)": ["Photos.exe", "PhotosApp.exe"],
    "bảo mật windows": ["SecHealthUI.exe"],
    "blender": ["blender.exe"],
    "bluestacks": ["HD-Player.exe", "HD-MultiInstanceManager.exe"],
    "camera": ["WindowsCamera.exe"],
    "canva": ["Canva.exe"],
    "capcut": ["CapCut.exe"],
    "command prompt": ["cmd.exe"],
    "cmd": ["cmd.exe"],
    "công cụ cắt": ["SnippingTool.exe", "ScreenClipping.exe"],
    "control panel": ["control.exe"],
    "terminal": ["WindowsTerminal.exe"],
    "discord": ["Discord.exe"],
    "excel": ["EXCEL.EXE"],
    "facebook": ["Facebook.exe"],
    "file explorer": ["explorer.exe"],
    "free download manager": ["fdm.exe"],
    "garena": ["Garena.exe", "GarenaMessenger.exe"],
    "google chrome": ["chrome.exe"],
    "chrome": ["chrome.exe"],
    "minecraft": ["LL.exe", "javaw.exe"],
    "microsoft edge": ["msedge.exe"],
    "edge": ["msedge.exe"],
    "notepad": ["Notepad.exe"],
    "obs studio": ["obs64.exe", "obs32.exe"],
    "obs": ["obs64.exe", "obs32.exe"],
    "opera": ["opera.exe"],
    "powerpoint": ["POWERPNT.EXE"],
    "ppt": ["POWERPNT.EXE"],
    "spotify": ["Spotify.exe"],
    "task manager": ["Taskmgr.exe", "taskmgr.exe"],
    "ultraviewer": ["UltraViewer_Desktop.exe"],
    "visual studio code": ["Code.exe"],
    "vs code": ["Code.exe"],
    "vscode": ["Code.exe"],
    "windows powershell": ["powershell.exe", "pwsh.exe"],
    "powershell": ["powershell.exe", "pwsh.exe"],
    "word": ["WINWORD.EXE"],
    "zalo": ["Zalo.exe"],
}

# ==========================================
# CƠ CHẾ DYNAMIC APP INDEXING & CACHING
# ==========================================
def scan_all_windows_apps():
    """
    Quét TOÀN BỘ ứng dụng trên Windows (Bao gồm Win32 .exe + Microsoft Store Apps như Clipchamp):
    1. Dùng PowerShell 'Get-StartApps' quét 100% AppStore & UWP Apps.
    2. Quét thư mục Start Menu (.lnk) để lấy file .exe truyền thống.
    """
    scanned_apps = {}

    # ---------------------------------------------------------
    # BƯỚC 1: QUÉT APP STORE & HỆ THỐNG QUA POWERSHELL (Bắt được Clipchamp, Photos, v.v.)
    # ---------------------------------------------------------
    try:
        ps_command = 'Get-StartApps | ConvertTo-Json -Compress'
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        
        if result.returncode == 0 and result.stdout.strip():
            start_apps = json.loads(result.stdout)
            # Nếu chỉ trả về 1 app dạng dict thì ép thành list
            if isinstance(start_apps, dict):
                start_apps = [start_apps]

            for app in start_apps:
                app_name = app.get("Name", "").strip().lower()
                app_id = app.get("AppID", "").strip()

                if app_name and app_id:
                    # Bỏ qua các đường dẫn uninstall hoặc trợ giúp
                    if "uninstall" in app_name or "remove" in app_name:
                        continue

                    clean_key = re.sub(r'[^\w\s]', '', app_name)
                    scanned_apps[app_name] = {
                        "appid": app_id,
                        "exes": [os.path.basename(app_id)] if app_id.endswith(".exe") else [],
                        "aliases": [clean_key, app_name.replace(" ", "")]
                    }
            print(f"📌 [SYSTEM] PowerShell đã quét thấy {len(scanned_apps)} apps (Store + Win32).")
    except Exception as e:
        print(f"⚠️ Lỗi quét PowerShell Get-StartApps: {e}")

    # ---------------------------------------------------------
    # BƯỚC 2: QUÉT BỔ SUNG START MENU DESKTOP (.LNK)
    # ---------------------------------------------------------
    try:
        pythoncom.CoInitialize()
        shell = win32com.client.Dispatch("WScript.Shell")

        start_menu_paths = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs")
        ]

        for path in start_menu_paths:
            if not os.path.exists(path):
                continue
                
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith(".lnk"):
                        shortcut_path = os.path.join(root, file)
                        try:
                            shortcut = shell.CreateShortCut(shortcut_path)
                            target_path = shortcut.TargetPath
                            
                            if target_path and target_path.lower().endswith(".exe") and os.path.exists(target_path):
                                app_name = os.path.splitext(file)[0].lower().strip()
                                exe_name = os.path.basename(target_path)
                                clean_key = re.sub(r'[^\w\s]', '', app_name)
                                
                                # Cập nhật thông tin chi tiết file .exe nếu tìm thấy
                                scanned_apps[app_name] = {
                                    "appid": target_path,
                                    "exes": [exe_name],
                                    "aliases": [clean_key, app_name.replace(" ", "")]
                                }
                        except Exception:
                            continue
    except Exception as e:
        print(f"⚠️ Lỗi quét Start Menu Shortcuts: {e}")
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

    # ---------------------------------------------------------
    # BƯỚC 3: GHI VÀO APPS_CACHE.JSON
    # ---------------------------------------------------------
    try:
        with open(APPS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(scanned_apps, f, ensure_ascii=False, indent=4)
        print(f"✅ [SYSTEM] Đã lưu tổng cộng {len(scanned_apps)} ứng dụng vào {APPS_CACHE_FILE}!")
    except Exception as e:
        print(f"⚠️ Lỗi ghi file apps_cache.json: {e}")

    return scanned_apps


def load_dynamic_app_database():
    """Tự động nạp danh sách app từ apps_cache.json vào hệ thống"""
    if not os.path.exists(APPS_CACHE_FILE):
        dynamic_apps = scan_all_windows_apps()
    else:
        try:
            with open(APPS_CACHE_FILE, "r", encoding="utf-8") as f:
                dynamic_apps = json.load(f)
        except Exception:
            dynamic_apps = scan_all_windows_apps()

    for app_name, app_info in dynamic_apps.items():
        if app_name not in APP_DATABASE:
            APP_DATABASE[app_name] = app_info
            
        if app_name not in APP_PROCESS_MAP and app_info.get("exes"):
            APP_PROCESS_MAP[app_name] = app_info["exes"]

# Nạp ứng dụng tự động khi module được import
load_dynamic_app_database()


def is_game_running():
    """Kiểm tra FO4 hoặc Minecraft có đang chạy không để tối ưu phần cứng"""
    from config import GAME_PROCESSES

    try:
        for proc in psutil.process_iter(['name']):
            p_name = proc.info['name']
            if p_name and any(
                game.lower() in p_name.lower() for game in GAME_PROCESSES
            ):
                return True, p_name
    except Exception:
        pass
    return False, None


def get_full_user_profile(target="all"):
    """Đọc dữ liệu cá nhân dựa trên hồ sơ json đầy đủ"""
    profile_path = "user_profile.json"
    if not os.path.exists(profile_path):
        return "Dạ, sếp chưa cài đặt thông tin cá nhân của sếp rồi ạ."

    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        hobbies = (
            ", ".join(data.get("hobbies", []))
            if isinstance(data.get("hobbies"), list)
            else data.get("hobbies", "Chưa rõ")
        )
        clubs = (
            ", ".join(data.get("favorite_clubs", []))
            if isinstance(data.get("favorite_clubs"), list)
            else data.get("favorite_clubs", "Chưa rõ")
        )
        color = (
            ", ".join(data.get("favorite_color", []))
            if isinstance(data.get("favorite_color"), list)
            else data.get("favorite_color", "Chưa rõ")
        )

        if target == "name":
            return f"Dạ, tên khai sinh của sếp là {data.get('name', 'Chưa rõ')} ạ."
        elif target == "dob":
            return (
                f"Dạ, ngày tháng năm sinh của sếp là"
                f" {data.get('date_of_birth', 'Chưa rõ')} ạ."
            )
        elif target == "gender":
            return f"Dạ, giới tính khai sinh của sếp là {data.get('gender', 'Chưa rõ')} ạ."
        elif target == "phone":
            return f"Dạ, số điện thoại của sếp là {data.get('phone', 'Chưa rõ')} ạ."
        elif target == "address":
            return f"Dạ, địa chỉ nơi sếp đang ở hiện tại là {data.get('address', 'Chưa rõ')} ạ."
        elif target == "laptop":
            return (
                f"Dạ, tên thiết bị hiện tại sếp đang sử dụng là"
                f" {data.get('name_laptop', 'Chưa rõ')} ạ."
            )
        elif target == "mobile":
            return (
                f"Dạ, tên thiết bị di động của sếp là"
                f" {data.get('name_mobile_phone', 'Chưa rõ')} ạ."
            )
        elif target == "hobbies":
            return f"Dạ, sở thích của sếp bao gồm {hobbies} ạ."
        elif target == "clubs":
            return f"Dạ, đội bóng yêu thích của sếp là {clubs} ạ."
        elif target == "color":
            return f"Dạ, màu sắc yêu thích của sếp là {color} ạ."
        elif target == "notes":
            return f"Dạ, ghi chú cá nhân của sếp: {data.get('notes', 'Hiện tại sếp không có ghi chú')}."

        profile_text = (
            f"Dạ sếp, đây là toàn bộ thông tin cá nhân sếp mà em đã ghi nhớ: "
            f"Tên thật của sếp là {data.get('name', 'Chưa rõ')}. "
            f"Ngày tháng năm sinh: {data.get('date_of_birth', 'Chưa rõ')}. "
            f"Giới tính của sếp là: {data.get('gender', 'Chưa rõ')}. "
            f"Số điện thoại: {data.get('phone', 'Chưa rõ')}. "
            f"Địa chỉ hiện tại nơi sếp ở: {data.get('address', 'Chưa rõ')}. "
            f"Tên thiết bị sếp đang sử dụng: {data.get('name_laptop', 'Chưa rõ')}. "
            f"Tên thiết bị di động của sếp là: {data.get('name_mobile_phone', 'Chưa rõ')}. "
            f"Sở thích của sếp: {hobbies}. "
            f"Đội bóng yêu thích của sếp: {clubs}. "
            f"Màu sếp yêu thích: {color}. "
            f"Ghi chú của sếp: {data.get('notes', 'hiện tại sếp không có ghi chú')}."
        )
        return profile_text

    except Exception:
        return "Dạ, em gặp lỗi khi mở tập tin hồ sơ cá nhân của sếp rồi ạ."


def get_opera_path():
    """Tự động tìm đường dẫn file opera.exe / opera gx trên máy Windows."""
    possible_paths = [
        os.path.expanduser(r"~\AppData\Local\Programs\Opera\opera.exe"),
        os.path.expanduser(r"~\AppData\Local\Programs\Opera GX\opera.exe"),
        r"C:\Program Files\Opera\opera.exe",
        r"C:\Program Files (x86)\Opera\opera.exe",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def search_on_opera(query):
    """Mở Opera và tìm kiếm từ khóa trên Google."""
    if not query or not query.strip():
        return "Sếp chưa nói nội dung cần tìm kiếm trên Opera ạ."

    query_clean = query.strip()
    opera_path = get_opera_path()

    if query_clean.startswith("http://") or query_clean.startswith("https://"):
        search_url = query_clean
    else:
        encoded_query = urllib.parse.quote(query_clean)
        search_url = f"https://www.google.com/search?q={encoded_query}"

    try:
        if opera_path:
            subprocess.Popen([opera_path, search_url])
            return f"Đã tìm kiếm '{query_clean}' trên Opera cho sếp rồi ạ!"
        else:
            webbrowser.open(search_url)
            return (
                f"Em không thấy đường dẫn Opera, nên đã mở tìm kiếm"
                f" '{query_clean}' trên trình duyệt mặc định rồi sếp ạ."
            )

    except Exception as e:
        print(f"⚠️ Lỗi search_on_opera: {e}")
        return "Em gặp lỗi khi tìm kiếm rồi sếp ơi."


def play_yt_music(song_name):
    """Bật bài hát YouTube Music / YouTube trực tiếp trên Opera GX"""
    target_url = None
    if Search:
        try:
            s = Search(song_name)
            if s.results:
                target_url = s.results[0].watch_url
        except Exception:
            pass

    if not target_url:
        query = urllib.parse.quote(song_name)
        target_url = f"https://music.youtube.com/search?q={query}"

    if OPERA_EXEC:
        subprocess.Popen([OPERA_EXEC, target_url])
    else:
        webbrowser.open(target_url)

    return f"Em đã mở bài {song_name} trên youtube cho sếp rồi đây ạ"


def clean_command_target(text):
    """Làm sạch câu lệnh giọng nói, xóa bỏ từ đệm tiếng Việt"""
    filler_words = [
        "ứng dụng", "app", "phần mềm", "cho tôi", "hộ tôi", "giúp tôi", 
        "giúp em", "cho em", "dùm tôi", "ngay", "đi", "lên", "xuống", "với", "xem"
    ]
    result = text.lower().strip()
    for word in filler_words:
        result = re.sub(r'\b' + re.escape(word) + r'\b', '', result)
    return result.strip()


def find_app_entry(input_name):
    """Tìm kiếm app tương ứng trong APP_DATABASE theo tên hoặc từ khóa viết tắt"""
    clean_name = clean_command_target(input_name)
    if not clean_name:
        clean_name = input_name.lower().strip()

    # 1. Tìm khớp chính xác key hoặc alias
    for key, data in APP_DATABASE.items():
        if clean_name == key or clean_name in data.get("aliases", []):
            return key, data

    # 2. Tìm kiếm chứa từ khóa (substring)
    for key, data in APP_DATABASE.items():
        if key in clean_name or any(alias in clean_name for alias in data.get("aliases", [])):
            return key, data

    return clean_name, None


def open_app(app_name):
    """Mở app thông minh: Mở trực tiếp cả Win32 (.exe) lẫn UWP / Microsoft Store Apps"""
    if not app_name or not app_name.strip():
        return "Sếp chưa nói tên ứng dụng cần mở ạ."

    clean_name = clean_command_target(app_name)

    # 1. Xử lý Canva đặc biệt
    if "canva" in clean_name:
        try:
            os.system("start canva://")
            return "Đã mở ứng dụng Canva cho sếp rồi ạ!"
        except Exception:
            webbrowser.open("https://www.canva.com")
            return "Đã mở trang web Canva trên trình duyệt cho sếp ạ!"

    # 2. Xử lý cứng Clipchamp: Dùng AppUserModelID chính xác của Microsoft Store App
    if "clipchamp" in clean_name:
        try:
            clipchamp_appid = "Clipchamp.Clipchamp_8wekyb3d8bbwe!App"
            subprocess.Popen(f'explorer.exe shell:AppsFolder\\{clipchamp_appid}', shell=True)
            return "Em đã mở Clipchamp cho sếp rồi ạ!"
        except Exception as e:
            print(f"⚠️ Lỗi mở Clipchamp: {e}")

    # 3. Tìm app trong Database / Apps Cache
    matched_key, app_data = find_app_entry(app_name)

    # 4. Mở app theo AppID hoặc File Path chuẩn
    if app_data and "appid" in app_data:
        appid = app_data["appid"]
        try:
            if appid.endswith(".exe") and os.path.exists(appid):
                os.startfile(appid)
                return f"Em đã mở {matched_key} cho sếp rồi ạ!"
            else:
                # Chú ý: shell:AppsFolder không được bọc dấu " trong tham số appid
                subprocess.Popen(f'explorer.exe shell:AppsFolder\\{appid}', shell=True)
                return f"Em đã mở {matched_key} cho sếp rồi ạ!"
        except Exception as e:
            print(f"⚠️ Lỗi mở app qua AppID {appid}: {e}")

    # 5. Dự phòng
    try:
        subprocess.Popen(f'explorer.exe shell:AppsFolder\\{matched_key}', shell=True)
        return f"Đang mở {matched_key} cho sếp ạ!"
    except Exception:
        return f"Em không tìm thấy ứng dụng {app_name} trên máy sếp ơi."


def get_news(user_query: str) -> str:
    print(f"[ĐANG TRA CỨU]: '{user_query}'")
    result = jarvis_knowledge_engine(user_query)

    if result:
        print("[TRA CỨU THÀNH CÔNG]")
        return result

    print("[TRA CỨU THẤT BẠI]: Không tìm thấy thông tin phù hợp.")
    return ""


def close_window(target_app=None):
    """Đóng cửa sổ bằng Win32 API."""
    try:
        if target_app and target_app.strip():
            clean_app = target_app.lower().strip()
            explorer_keywords = [
                "file explorer",
                "explorer",
                "thư mục",
                "folder",
                "quản lý tệp",
                "tệp",
            ]

            if any(kw in clean_app for kw in explorer_keywords):
                found_hwnds = []

                def enum_explorer_callback(hwnd, extra):
                    if win32gui.IsWindowVisible(hwnd):
                        class_name = win32gui.GetClassName(hwnd)
                        if class_name in ["CabinetWClass", "ExploreWClass"]:
                            found_hwnds.append(hwnd)

                win32gui.EnumWindows(enum_explorer_callback, None)

                if found_hwnds:
                    for hwnd in found_hwnds:
                        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    return "Đã đóng tất cả thư mục File Explorer cho sếp rồi ạ!"
                else:
                    return "Em không thấy cửa sổ File Explorer nào đang mở sếp ơi."

            found_hwnds = []

            def enum_windows_callback(hwnd, extra):
                if win32gui.IsWindowVisible(hwnd):
                    class_name = win32gui.GetClassName(hwnd)
                    if class_name in ["Shell_TrayWnd", "Progman", "WorkerW", "Button"]:
                        return

                    title = win32gui.GetWindowText(hwnd).lower()
                    if title and clean_app in title:
                        found_hwnds.append(hwnd)

            win32gui.EnumWindows(enum_windows_callback, None)

            if found_hwnds:
                for hwnd in found_hwnds:
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return f"Đã đóng cửa sổ {target_app} cho sếp rồi ạ!"
            else:
                return f"Em không tìm thấy cửa sổ nào của {target_app} đang mở ạ."

        else:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                class_name = win32gui.GetClassName(hwnd)
                if class_name not in ["Shell_TrayWnd", "Progman", "WorkerW"]:
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    return "Đã đóng cửa sổ hiện tại rồi sếp!"

            return "Không có cửa sổ nào để đóng sếp ơi."

    except Exception as e:
        print(f"⚠️ Lỗi close_window: {e}")
        return "Em gặp lỗi khi đóng cửa sổ rồi sếp."


def close_app(app_name):
    """Hàm đóng app mạnh mẽ - Đã fix so sánh Case-insensitive cho PowerShell & các app khác"""
    if not app_name or not app_name.strip():
        return "Sếp chưa nói tên ứng dụng cần đóng ạ."

    raw_clean = clean_command_target(app_name)
    if not raw_clean:
        raw_clean = app_name.lower().strip()

    clean_name = re.sub(r'\s+', ' ', raw_clean).lower()

    # 1. Tìm các file .exe tương ứng trong dictionary
    target_exes = []
    for key, exe_list in APP_PROCESS_MAP.items():
        key_lower = key.lower()
        if key_lower in clean_name or key_lower.replace(" ", "") in clean_name.replace(" ", ""):
            target_exes.extend(exe_list if isinstance(exe_list, list) else [exe_list])

    # 2. Tìm bổ sung trong APP_DATABASE
    for key, data in APP_DATABASE.items():
        key_lower = key.lower()
        if key_lower in clean_name or any(alias in clean_name for alias in data.get("aliases", [])):
            target_exes.extend(data.get("exes", []))

    target_exes = list(set(target_exes))

    if not target_exes:
        exe_guess = clean_name.replace(" ", "")
        if not exe_guess.endswith(".exe"):
            exe_guess += ".exe"
        target_exes = [exe_guess]

    # 3. Thử cưỡng chế tắt trực tiếp bằng CMD
    killed_any = False
    for exe in target_exes:
        try:
            cmd = f'taskkill /F /T /IM "{exe}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0 or "SUCCESS" in result.stdout.upper():
                killed_any = True
        except Exception as e:
            print(f"⚠️ Lỗi taskkill {exe}: {e}")

    if killed_any:
        return f"Đã đóng triệt để {clean_name} cho sếp rồi ạ!"

    # 4. Phương án dự phòng: Dùng psutil
    try:
        psutil_killed = False
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = proc.info['name']
                if pname and any(target.lower() == pname.lower() for target in target_exes):
                    proc.kill()
                    psutil_killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if psutil_killed:
            return f"Đã diệt tiến trình {clean_name} thành công sếp ơi!"

    except Exception as e:
        print(f"⚠️ Lỗi psutil: {e}")

    return f"Em không tìm thấy ứng dụng {clean_name} nào đang chạy sếp ơi."


def execute_single_command(user_text, chat_history=None):
    """Hàm xử lý TỪNG LỆNH ĐƠN (Gồm đầy đủ 20 case hệ thống + Quét lại app)"""
    if chat_history is None:
        chat_history = []
    
    # 0. Chuẩn hóa câu nói đầu vào
    text = normalize_speech_text(user_text)

    # 🛑 LỆNH THÊM MỚI: QUÉT LẠI ỨNG DỤNG MÁY TÍNH
    if any(k in text for k in ["quét lại ứng dụng", "cập nhật ứng dụng", "quét app", "cập nhật app"]):
        scan_all_windows_apps()
        load_dynamic_app_database()
        return "Em đã quét lại toàn bộ phần mềm và ứng dụng Store trên máy cho sếp rồi ạ!"

    # 1. BẮT BẢO NGHĨA LỆNH DỌN / XÓA THƯ MỤC DOWNLOADS
    clean_verbs = [
        "xóa", "xoá", "dọn", "dọn dẹp", "làm sạch", "xóa sạch", 
        "xoá sạch", "xóa hết", "xoá hết", "dọn sạch",
    ]
    dl_keywords = [
        "download", "downloads", "tải về", "thư mục download", 
        "thư mục downloads", "thư mục tải về",
    ]

    if any(v in text for v in clean_verbs) and any(dk in text for dk in dl_keywords):
        return clean_downloads_folder()

    # 2. BỘ XỬ LÝ FILE / THƯ MỤC CHUNG
    file_res = execute_file_command(text)
    if file_res:
        return file_res

    # 3. Lệnh Timer
    timer_res = handle_timer_command(text)
    if timer_res:
        return timer_res

    # 4. Kiểm tra Nhiệt độ (CPU và GPU)
    elif any(
        k in text for k in [
            "nhiệt độ", "máy nóng không", "nhiệt độ cpu", 
            "nhiệt độ gpu", "nhiệt độ máy",
        ]
    ):
        ask_cpu = any(k in text for k in ["cpu", "chip"])
        ask_gpu = any(k in text for k in ["gpu", "card", "đồ họa"])

        cpu_temp = None
        gpu_temp = None

        try:
            import _wmi
            w = _wmi.WMI(namespace="root\\wmi")
            temp_info = w.MSAcpi_ThermalZoneTemperature()
            if temp_info:
                cpu_temp = int((temp_info[0].CurrentTemperature / 10.0) - 273.15)
        except Exception:
            pass

        if cpu_temp is None:
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for key in ["coretemp", "cpu_thermal", "k10temp"]:
                        if key in temps and temps[key]:
                            cpu_temp = int(temps[key][0].current)
                            break
            except Exception:
                pass

        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu_temp = int(gpus[0].temperature)
        except Exception:
            pass

        if ask_cpu:
            if cpu_temp is not None:
                return f"Nhiệt độ CPU hiện tại là {cpu_temp} độ C sếp ơi."
            return "Em chưa lấy được nhiệt độ CPU (Cần chạy Python bằng quyền Administrator) sếp ơi."

        if ask_gpu:
            if gpu_temp is not None:
                return f"Nhiệt độ GPU hiện tại là {gpu_temp} độ C sếp ơi."
            return "Em không đo được nhiệt độ GPU lúc này sếp ơi."

        res = []
        if cpu_temp is not None:
            res.append(f"CPU {cpu_temp}°C")
        if gpu_temp is not None:
            res.append(f"GPU {gpu_temp}°C")

        if res:
            return f"Nhiệt độ hiện tại: {', '.join(res)} sếp ơi."
        return "Em không lấy được thông tin nhiệt độ lúc này (sếp thử chạy app bằng Run as Administrator xem sao)."

    # 5. Kiểm tra RAM
    elif any(k in text for k in ["ram", "bộ nhớ ram"]):
        ram = psutil.virtual_memory()
        free_gb = round(ram.available / (1024**3), 1)
        return f"RAM đang dùng {ram.percent} phần trăm, còn trống {free_gb} gigabyte sếp ơi."

    # 6. Kiểm tra CPU
    elif any(k in text for k in ["cpu", "chip", "mức dùng cpu"]):
        cpu = psutil.cpu_percent(interval=0.5)
        return f"CPU hiện tại đang chạy ở mức {cpu} phần trăm sếp ơi."

    # 7. Kiểm tra Pin
    elif any(k in text for k in ["pin", "mức pin"]):
        battery = psutil.sensors_battery()
        if battery:
            status = "đang sạc" if battery.power_plugged else "dùng pin"
            return f"Pin hiện tại còn {battery.percent} phần trăm, máy đang {status} sếp ơi."

    # 8. Kiểm tra Ổ đĩa
    elif any(k in text for k in ["dung lượng", "ổ c", "trống bao nhiêu"]):
        disk = psutil.disk_usage("C:")
        free_gb = round(disk.free / (1024**3), 1)
        return f"Ổ C hiện tại còn trống {free_gb} gigabyte sếp ơi."

    # 9. Tình trạng tổng quan
    elif any(k in text for k in ["tình trạng máy", "tổng quan", "toàn bộ máy"]):
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        disk_free = round(psutil.disk_usage("C:").free / (1024**3), 1)
        return (
            f"Tình trạng máy hiện tại. CPU sử dụng {cpu} phần trăm, RAM sử dụng"
            f" {ram} phần trăm. Ổ C còn trống {disk_free} gigabyte sếp ơi."
        )

    # 10. Kiểm tra tốc độ mạng / Wifi
    if any(
        k in text for k in [
            "kiểm tra mạng", "đo tốc độ mạng", "tốc độ wifi", 
            "ping bao nhiêu", "mạng mạnh không", "speedtest",
        ]
    ):
        return check_network_speed()

    # 11. Lệnh Clipboard
    if any(
        kw in text for kw in [
            "clipboard", "bộ nhớ tạm", "sao chép", 
            "văn bản vừa chép", "dán",
        ]
    ):
        clip_res = handle_clipboard_command(
            text, ai_process_func=ask_groq_for_clipboard
        )
        if clip_res:
            return clip_res

    # 12. Chẩn đoán sự cố
    diag_res = execute_diagnostics_command(text)
    if diag_res:
        return diag_res

    # 13. Điều khiển Cửa sổ
    win_res = handle_window_command(text)
    if win_res:
        return win_res

    # 14. Hồ sơ cá nhân
    if any(kw in text for kw in ["tên tôi là gì", "tên của tôi", "tên tôi", "tôi tên gì"]):
        return get_full_user_profile("name")
    if any(kw in text for kw in ["sinh ngày mấy", "ngày sinh của tôi", "sinh nhật tôi", "tôi sinh năm bao nhiêu"]):
        return get_full_user_profile("dob")
    if any(kw in text for kw in ["giới tính của tôi", "tôi là nam hay nữ"]):
        return get_full_user_profile("gender")
    if any(kw in text for kw in ["số điện thoại của tôi", "sđt của tôi", "sđt tôi"]):
        return get_full_user_profile("phone")
    if any(kw in text for kw in ["địa chỉ của tôi", "tôi ở đâu", "nhà tôi ở đâu"]):
        return get_full_user_profile("address")
    if any(kw in text for kw in ["tên máy tính", "laptop tên gì", "thiết bị đang sử dụng", "tên laptop"]):
        return get_full_user_profile("laptop")
    if any(kw in text for kw in ["tên điện thoại", "điện thoại di động", "thiết bị di động"]):
        return get_full_user_profile("mobile")
    if any(kw in text for kw in ["sở thích của tôi", "tôi thích gì"]):
        return get_full_user_profile("hobbies")
    if any(kw in text for kw in ["đội bóng tôi thích", "đội bóng yêu thích", "câu lạc bộ tôi"]):
        return get_full_user_profile("clubs")
    if any(kw in text for kw in ["màu tôi thích", "màu yêu thích của tôi"]):
        return get_full_user_profile("color")
    if any(kw in text for kw in ["ghi chú của tôi", "ghi chú cá nhân"]):
        return get_full_user_profile("notes")
    if any(kw in text for kw in ["thông tin cá nhân", "hồ sơ của tôi", "danh tính của tôi", "đọc hết thông tin"]):
        return get_full_user_profile("all")

    # 15. Điều khiển Nhạc
    if any(kw in text for kw in ["tiếp tục phát nhạc", "tiếp tục", "phát tiếp", "bật tiếp"]):
        pyautogui.press("playpause")
        return "Đã tiếp tục phát nhạc cho sếp ạ"

    if any(kw in text for kw in ["ngừng nhạc", "dừng nhạc", "tạm dừng", "dừng phát"]):
        pyautogui.press("playpause")
        return "Đã tạm dừng phát nhạc cho sếp ạ"

    if any(kw in text for kw in ["mở bài", "phát bài", "bật bài", "nghe bài", "tìm bài", "chơi bài"]):
        song = text
        for kw in ["mở bài", "phát bài", "bật bài", "nghe bài", "tìm bài", "chơi bài", "trên youtube", "nhạc"]:
            song = song.replace(kw, "").strip()
        return play_yt_music(song if song else "nhạc hot trend")

    if any(kw in text for kw in ["bài tiếp", "chuyển bài", "qua bài", "bài sau", "next", "bỏ qua bài"]):
        pyautogui.press("nexttrack")
        return "Đã chuyển sang bài tiếp theo cho sếp!"

    # 16. Tin tức
    if any(kw in text for kw in ["tin tức", "thời sự", "điểm tin thời sự", "tin mới nhất"]):
        return get_news(text)

    # 17. Mở / Đóng App
    if any(kw in text for kw in ["mở app", "bật app", "mở ứng dụng", "mở", "bật", "chạy", "open"]):
        if not any(k in text for k in ["mở bài", "mở opera tìm", "mở web", "mở nhạc"]):
            app = text
            for kw in ["mở app", "bật app", "mở ứng dụng", "mở", "bật", "chạy", "open", "cho tôi", "hộ tôi", "giúp tôi", "giùm tôi"]:
                app = app.replace(kw, "").strip()
            if app:
                return open_app(app)

    if any(kw in text for kw in ["đóng app", "tắt app", "đóng ứng dụng", "tắt ứng dụng", "đóng", "tắt"]):
        if not any(kw in text for kw in ["tắt máy", "tắt pc", "tắt nhạc", "tắt âm lượng"]):
            app_to_close = text
            for kw in ["đóng app", "tắt app", "đóng ứng dụng", "tắt ứng dụng", "đóng", "tắt", "cho tôi", "hộ tôi", "giùm tôi"]:
                app_to_close = app_to_close.replace(kw, "").strip()
            if app_to_close:
                return close_app(app_to_close)

    # 18. Chỉnh Âm lượng
    vol_keywords = ["âm lượng", "âm thanh", "volume", "tiếng", "chỉnh", "tăng", "giảm", "nhỏ", "to"]
    digits = re.findall(r"\d+", text)
    if digits and any(kw in text for kw in vol_keywords):
        level = int(digits[0])
        clean_target = text
        for kw in [
            "chỉnh", "tăng", "giảm", "đặt", "âm lượng", "âm thanh", "volume", 
            "tiếng", "lên", "xuống", "về", "bằng", "cho", "phần trăm", "%", 
            "to", "nhỏ", "nhỏ lại", "to lên",
        ]:
            clean_target = clean_target.replace(kw, "").strip()
        clean_target = re.sub(r"\d+", "", clean_target).strip()
        return set_volume(level, clean_target if clean_target else None)

    # 19. Tìm kiếm Opera
    opera_keywords = [
        "tìm kiếm trên opera", "tìm trên opera", "lên opera tìm", 
        "mở opera tìm", "tìm qua opera", "tìm bằng opera",
    ]
    if any(kw in text for kw in opera_keywords):
        clean_query = text
        for kw in opera_keywords + ["về", "cho em", "cho tôi", "giùm", "hộ", "thông tin"]:
            clean_query = clean_query.replace(kw, "").strip()

        if clean_query:
            return search_on_opera(clean_query)
        return "Sếp muốn em tìm nội dung gì trên Opera ạ?"

    # 20. Cuộc gọi Zalo
    if any(k in text for k in ["nghe điện thoại", "trả lời cuộc gọi", "bắt máy", "nghe zalo", "nhận cuộc gọi"]):
        if accept_zalo_call():
            return "Đã bắt máy Zalo cho sếp."
        return "Không tìm thấy nút nghe Zalo sếp ơi."

    elif any(k in text for k in ["từ chối", "bỏ qua cuộc gọi", "đừng nghe", "từ chối zalo"]):
        if reject_zalo_call():
            return "Đã từ chối cuộc gọi Zalo."
        return "Không tìm thấy nút từ chối Zalo sếp ơi."

    # 🔴 Trả về None nếu không trùng lệnh hệ thống nào để backend gọi AI Groq
    return None


def execute_command(user_text, chat_history=None):
    """Hàm chính: Tự động xử lý cả LỆNH ĐƠN và LỆNH KÉP"""
    if chat_history is None:
        chat_history = []

    separators = r'\b(?:và|rồi|sau đó|đồng thời|tiếp theo|với cả)\b|,'
    sub_commands = re.split(separators, user_text, flags=re.IGNORECASE)

    results = []
    for cmd in sub_commands:
        cmd_clean = cmd.strip()
        if cmd_clean:
            res = execute_single_command(cmd_clean, chat_history)
            if res:
                results.append(res)
                time.sleep(0.5)

    if results:
        return " ".join(results)

    return None