import os
import subprocess
import sys

# 1. Tên file chính và tên ứng dụng
MAIN_FILE = "main.py"  # Thay bằng file chạy chính của JARVIS nếu tên khác
APP_NAME = "JARVIS"

# 2. Cài đặt PyInstaller nếu chưa có
try:
  import PyInstaller
except ImportError:
  print("📦 Đang cài đặt PyInstaller...")
  subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])

# 3. Tạo nội dung file spec tối ưu cho JARVIS (Chống lỗi thiếu thư viện Discord)
spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['{MAIN_FILE}'],
    pathex=[],
    binaries=[],
    datas=[
        ('.env', '.'),          # Tự động copy file .env
        ('*.json', '.'),        # Copy các file json cấu hình (nếu có)
    ],
    hiddenimports=[
        'discord',
        'discord.ext.commands',
        'discord.ui',
        'asyncio',
        'aiohttp',
        'typing_extensions'
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True, # Đổi thành False nếu muốn ẩn hoàn toàn cửa sổ CMD khi chạy
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='{APP_NAME}',
)
"""

# Viết file spec
spec_file = f"{APP_NAME}.spec"
with open(spec_file, "w", encoding="utf-8") as f:
  f.write(spec_content)

print(f"✅ Đã tạo cấu hình {spec_file}")
print("🚀 Đang tiến hành đóng gói JARVIS thành EXE...")

# 4. Chạy lệnh Build
subprocess.run([sys.executable, "-m", "PyInstaller", spec_file, "--noconfirm"])

print("\n" + "=" * 50)
print(f"🎉 ĐÓNG GÓI HOÀN TẤT!")
print(f"📁 File exe nằm tại: {os.path.abspath(f'dist/{APP_NAME}/{APP_NAME}.exe')}")
print("=" * 50)